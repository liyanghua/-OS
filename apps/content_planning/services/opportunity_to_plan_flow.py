"""OpportunityToPlanFlow：从 promoted 机会卡到完整内容策划的一站式编排。

v2: 增加会话缓存 + 局部重生成 + 原子操作方法。
v3: 持久化到 SQLite + lineage 血缘追踪 + stale_flags。
"""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from apps.content_planning.adapters.intel_hub_adapter import IntelHubAdapter
from apps.content_planning.exceptions import OpportunityNotPromotedError
from apps.content_planning.schemas.asset_bundle import AssetBundle
from apps.content_planning.schemas.content_generation import (
    BodyGenerationResult,
    ImageBriefGenerationResult,
    TitleGenerationResult,
)
from apps.content_planning.schemas.lineage import PlanLineage
from apps.content_planning.schemas.note_plan import NewNotePlan
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.schemas.template_match_result import (
    TemplateMatchEntry,
    TemplateMatchResult,
)
from apps.content_planning.services.body_generator import BodyGenerator
from apps.content_planning.services.brief_compiler import BriefCompiler
from apps.content_planning.services.image_brief_generator import ImageBriefGenerator
from apps.content_planning.services.new_note_plan_compiler import NewNotePlanCompiler
from apps.content_planning.services.strategy_generator import RewriteStrategyGenerator
from apps.content_planning.services.title_generator import TitleGenerator
from apps.template_extraction.agent import TemplateMatcher, TemplateRetriever

logger = logging.getLogger(__name__)

_STAGE_ORDER = ["brief", "match", "strategy", "plan", "generation"]
_STALE_KEYS = ("brief", "match", "strategy", "plan", "titles", "body", "image_briefs")


class _SessionState:
    """单个 opportunity 的编排中间状态（内存热层）。"""

    __slots__ = (
        "opportunity_id", "brief", "match_result", "strategy",
        "note_plan", "titles", "body", "image_briefs",
        "templates", "selected_tpl", "updated_at",
        "pipeline_run_id", "stale_flags",
    )

    def __init__(self, opportunity_id: str) -> None:
        self.opportunity_id = opportunity_id
        self.brief: OpportunityBrief | None = None
        self.match_result: TemplateMatchResult | None = None
        self.strategy: RewriteStrategy | None = None
        self.note_plan: NewNotePlan | None = None
        self.titles: TitleGenerationResult | None = None
        self.body: BodyGenerationResult | None = None
        self.image_briefs: ImageBriefGenerationResult | None = None
        self.templates: list = []
        self.selected_tpl = None
        self.updated_at = datetime.now(UTC)
        self.pipeline_run_id: str = uuid.uuid4().hex[:16]
        self.stale_flags: dict[str, bool] = {k: False for k in _STALE_KEYS}

    def invalidate_downstream(self, from_stage: str = "brief") -> None:
        """从某阶段开始失效下游缓存。"""
        idx = _STAGE_ORDER.index(from_stage) if from_stage in _STAGE_ORDER else 0
        if idx <= 1:
            self.match_result = None
            self.stale_flags["match"] = True
        if idx <= 2:
            self.strategy = None
            self.stale_flags["strategy"] = True
        if idx <= 3:
            self.note_plan = None
            self.stale_flags["plan"] = True
        if idx <= 4:
            self.titles = None
            self.body = None
            self.image_briefs = None
            self.stale_flags["titles"] = True
            self.stale_flags["body"] = True
            self.stale_flags["image_briefs"] = True
        self.updated_at = datetime.now(UTC)

    def _mark_fresh(self, key: str) -> None:
        self.stale_flags[key] = False


class OpportunityToPlanFlow:
    """统一编排入口：promoted 卡 -> Brief -> 选模板 -> Strategy -> NotePlan -> (可选) 内容生成。"""

    def __init__(
        self,
        adapter: IntelHubAdapter | None = None,
        plan_store: Any | None = None,
    ) -> None:
        self._adapter = adapter or IntelHubAdapter()
        self._brief_compiler = BriefCompiler()
        self._strategy_gen = RewriteStrategyGenerator()
        self._plan_compiler = NewNotePlanCompiler()
        self._title_gen = TitleGenerator()
        self._body_gen = BodyGenerator()
        self._image_gen = ImageBriefGenerator()
        self._retriever = TemplateRetriever()
        self._cache: dict[str, _SessionState] = {}
        self._store = plan_store

    def _get_session(self, opportunity_id: str) -> _SessionState:
        if opportunity_id in self._cache:
            return self._cache[opportunity_id]

        if self._store is not None:
            persisted = self._store.load_session(opportunity_id)
            if persisted is not None:
                session = _SessionState(opportunity_id)
                session.pipeline_run_id = persisted.get("pipeline_run_id") or session.pipeline_run_id
                if persisted.get("brief"):
                    try:
                        session.brief = OpportunityBrief.model_validate(persisted["brief"])
                    except Exception:
                        pass
                if persisted.get("match_result"):
                    try:
                        session.match_result = TemplateMatchResult.model_validate(persisted["match_result"])
                    except Exception:
                        pass
                if persisted.get("strategy"):
                    try:
                        session.strategy = RewriteStrategy.model_validate(persisted["strategy"])
                    except Exception:
                        pass
                if persisted.get("plan"):
                    try:
                        session.note_plan = NewNotePlan.model_validate(persisted["plan"])
                    except Exception:
                        pass
                if persisted.get("titles"):
                    try:
                        session.titles = TitleGenerationResult.model_validate(persisted["titles"])
                    except Exception:
                        pass
                if persisted.get("body"):
                    try:
                        session.body = BodyGenerationResult.model_validate(persisted["body"])
                    except Exception:
                        pass
                if persisted.get("image_briefs"):
                    try:
                        session.image_briefs = ImageBriefGenerationResult.model_validate(persisted["image_briefs"])
                    except Exception:
                        pass
                if persisted.get("stale_flags"):
                    session.stale_flags.update(persisted["stale_flags"])
                self._cache[opportunity_id] = session
                return session

        session = _SessionState(opportunity_id)
        self._cache[opportunity_id] = session
        return session

    def _persist(self, session: _SessionState, status: str = "draft") -> None:
        """将会话写入持久层。"""
        if self._store is None:
            return
        self._store.save_session(
            session.opportunity_id,
            session_status=status,
            brief=session.brief,
            match_result=session.match_result,
            strategy=session.strategy,
            plan=session.note_plan,
            titles=session.titles,
            body=session.body,
            image_briefs=session.image_briefs,
            pipeline_run_id=session.pipeline_run_id,
            stale_flags=session.stale_flags,
        )

    def _build_lineage(self, session: _SessionState) -> PlanLineage:
        """根据当前 session 状态构建 lineage 快照。"""
        return PlanLineage(
            pipeline_run_id=session.pipeline_run_id,
            source_note_ids=session.brief.source_note_ids if session.brief else [],
            opportunity_id=session.opportunity_id,
            brief_id=session.brief.brief_id if session.brief else "",
            template_id=session.match_result.primary_template.template_id if session.match_result else "",
            strategy_id=session.strategy.strategy_id if session.strategy else "",
            plan_id=session.note_plan.plan_id if session.note_plan else "",
        )

    # ── 原子操作 ──────────────────────────────────────────────

    def build_brief(self, opportunity_id: str) -> OpportunityBrief:
        card = self._adapter.get_card(opportunity_id)
        if card is None:
            raise ValueError(f"机会卡 {opportunity_id} 未找到")
        if card.opportunity_status != "promoted":
            raise OpportunityNotPromotedError(opportunity_id, card.opportunity_status)

        source_notes = self._adapter.get_source_notes(card.source_note_ids)
        parsed_note = source_notes[0] if source_notes else None
        review_summary = self._adapter.get_review_summary(opportunity_id)

        brief = self._brief_compiler.compile(card, parsed_note, review_summary)

        session = self._get_session(opportunity_id)
        lineage = self._build_lineage(session)
        lineage.source_note_ids = list(card.source_note_ids)
        lineage.brief_id = brief.brief_id
        brief.lineage = lineage

        session.brief = brief
        session.invalidate_downstream("match")
        session._mark_fresh("brief")
        self._persist(session, status="generated")
        return brief

    def update_brief(self, opportunity_id: str, partial: dict[str, Any]) -> OpportunityBrief:
        """局部更新 Brief 字段，失效下游缓存。"""
        session = self._get_session(opportunity_id)
        if session.brief is None:
            session.brief = self.build_brief(opportunity_id)

        editable = {
            "target_user", "target_scene", "content_goal", "primary_value",
            "visual_style_direction", "avoid_directions", "template_hints",
            "core_motive", "price_positioning", "target_audience",
        }
        for key, val in partial.items():
            if key in editable and hasattr(session.brief, key):
                setattr(session.brief, key, val)

        session.brief.brief_status = "reviewed"
        session.brief.updated_at = datetime.now(UTC)
        session.invalidate_downstream("match")
        self._persist(session, status="generated")
        return session.brief

    def match_templates(
        self,
        opportunity_id: str,
        *,
        top_k: int = 6,
    ) -> TemplateMatchResult:
        session = self._get_session(opportunity_id)
        if session.brief is None:
            session.brief = self.build_brief(opportunity_id)

        templates = self._retriever.list_templates()
        if not templates:
            raise ValueError("模板库为空，无法匹配")
        session.templates = templates

        matcher = TemplateMatcher(templates)
        matches = matcher.match_templates(brief=session.brief, top_k=top_k)

        primary = matches[0] if matches else None
        if primary is None:
            raise ValueError("无可用模板匹配结果")

        match_result = TemplateMatchResult(
            opportunity_id=session.brief.opportunity_id,
            brief_id=session.brief.brief_id,
            primary_template=TemplateMatchEntry(
                template_id=primary.template_id,
                template_name=primary.template_name,
                score=primary.score,
                reason=primary.reason,
                matched_dimensions=primary.matched_dimensions,
            ),
            secondary_templates=[
                TemplateMatchEntry(
                    template_id=m.template_id,
                    template_name=m.template_name,
                    score=m.score,
                    reason=m.reason,
                    matched_dimensions=m.matched_dimensions,
                )
                for m in matches[1:4]
            ],
            rejected_templates=[
                TemplateMatchEntry(
                    template_id=m.template_id,
                    template_name=m.template_name,
                    score=m.score,
                    reason=m.reason,
                    matched_dimensions=m.matched_dimensions,
                )
                for m in matches
                if m.score <= 0
            ],
        )
        session.match_result = match_result
        session.invalidate_downstream("strategy")
        session._mark_fresh("match")
        self._persist(session, status="generated")
        return match_result

    def build_strategy(
        self,
        opportunity_id: str,
        *,
        template_id: str | None = None,
    ) -> RewriteStrategy:
        session = self._get_session(opportunity_id)
        if session.brief is None:
            session.brief = self.build_brief(opportunity_id)
        if session.match_result is None:
            self.match_templates(opportunity_id)

        mr = session.match_result
        assert mr is not None

        if template_id:
            all_tpls = [mr.primary_template] + mr.secondary_templates
            chosen = next((t for t in all_tpls if t.template_id == template_id), None)
            if chosen is not None:
                mr.primary_template = chosen
        else:
            template_id = mr.primary_template.template_id

        selected_tpl = self._retriever.get_template(template_id or mr.primary_template.template_id)
        if selected_tpl is None:
            raise ValueError(f"模板 {template_id} 加载失败")
        session.selected_tpl = selected_tpl

        strategy = self._strategy_gen.generate(session.brief, mr, selected_tpl)

        lineage = self._build_lineage(session)
        lineage.strategy_id = strategy.strategy_id
        lineage.template_id = selected_tpl.template_id
        strategy.lineage = lineage

        session.strategy = strategy
        session.invalidate_downstream("plan")
        session._mark_fresh("strategy")
        self._persist(session, status="generated")
        return strategy

    def build_plan(self, opportunity_id: str) -> NewNotePlan:
        session = self._get_session(opportunity_id)
        if session.strategy is None:
            self.build_strategy(opportunity_id)

        assert session.brief is not None
        assert session.strategy is not None
        assert session.match_result is not None
        assert session.selected_tpl is not None

        note_plan = self._plan_compiler.compile(
            session.brief, session.strategy, session.match_result, session.selected_tpl,
        )

        lineage = self._build_lineage(session)
        lineage.plan_id = note_plan.plan_id
        note_plan.lineage = lineage

        session.note_plan = note_plan
        session._mark_fresh("plan")
        self._persist(session, status="generated")
        return note_plan

    def regenerate_titles(self, opportunity_id: str) -> TitleGenerationResult:
        session = self._get_session(opportunity_id)
        if session.note_plan is None:
            self.build_plan(opportunity_id)
        assert session.note_plan is not None
        assert session.strategy is not None
        result = self._title_gen.generate(session.note_plan, session.strategy)
        result.lineage = self._build_lineage(session)
        session.titles = result
        session._mark_fresh("titles")
        self._persist(session, status="generated")
        return result

    def regenerate_body(self, opportunity_id: str) -> BodyGenerationResult:
        session = self._get_session(opportunity_id)
        if session.note_plan is None:
            self.build_plan(opportunity_id)
        assert session.note_plan is not None
        assert session.strategy is not None
        result = self._body_gen.generate(session.note_plan, session.strategy)
        result.lineage = self._build_lineage(session)
        session.body = result
        session._mark_fresh("body")
        self._persist(session, status="generated")
        return result

    def regenerate_image_briefs(self, opportunity_id: str) -> ImageBriefGenerationResult:
        session = self._get_session(opportunity_id)
        if session.note_plan is None:
            self.build_plan(opportunity_id)
        assert session.note_plan is not None
        assert session.strategy is not None
        result = self._image_gen.generate(session.note_plan, session.strategy)
        result.lineage = self._build_lineage(session)
        session.image_briefs = result
        session._mark_fresh("image_briefs")
        self._persist(session, status="generated")
        return result

    # ── 编排操作（兼容旧 API） ─────────────────────────────────

    def build_note_plan(
        self,
        opportunity_id: str,
        *,
        with_generation: bool = False,
        preferred_template_id: str | None = None,
    ) -> dict[str, Any]:
        """完整编排流程，兼容旧 generate-note-plan API。"""
        brief = self.build_brief(opportunity_id)

        self.match_templates(opportunity_id)
        session = self._get_session(opportunity_id)

        if preferred_template_id:
            self.build_strategy(opportunity_id, template_id=preferred_template_id)
        else:
            self.build_strategy(opportunity_id)

        note_plan = self.build_plan(opportunity_id)

        result: dict[str, Any] = {
            "brief": brief.model_dump(mode="json"),
            "match_result": session.match_result.model_dump(mode="json") if session.match_result else {},
            "strategy": session.strategy.model_dump(mode="json") if session.strategy else {},
            "note_plan": note_plan.model_dump(mode="json"),
        }

        if with_generation:
            result["generated"] = self._run_generation(opportunity_id)

        return result

    def compile_note_plan(
        self,
        opportunity_id: str,
        *,
        with_generation: bool = True,
        preferred_template_id: str | None = None,
    ) -> dict[str, Any]:
        """编排型一键全链路，返回所有中间产物。"""
        return self.build_note_plan(
            opportunity_id,
            with_generation=with_generation,
            preferred_template_id=preferred_template_id,
        )

    def get_session_data(self, opportunity_id: str) -> dict[str, Any]:
        """返回当前会话缓存的所有中间产物（用于 UI 渲染）。"""
        session = self._get_session(opportunity_id)
        data: dict[str, Any] = {
            "opportunity_id": opportunity_id,
            "pipeline_run_id": session.pipeline_run_id,
            "stale_flags": dict(session.stale_flags),
        }
        if session.brief:
            data["brief"] = session.brief.model_dump(mode="json")
        if session.match_result:
            data["match_result"] = session.match_result.model_dump(mode="json")
        if session.strategy:
            data["strategy"] = session.strategy.model_dump(mode="json")
        if session.note_plan:
            data["note_plan"] = session.note_plan.model_dump(mode="json")
        if session.titles:
            data["titles"] = session.titles.model_dump(mode="json")
        if session.body:
            data["body"] = session.body.model_dump(mode="json")
        if session.image_briefs:
            data["image_briefs"] = session.image_briefs.model_dump(mode="json")
        return data

    def _run_generation(self, opportunity_id: str) -> dict[str, Any]:
        """三路并行生成（使用线程池隔离 LLM 调用）。某一路失败不影响其他。"""
        results: dict[str, Any] = {}
        errors: dict[str, str] = {}

        def _gen_titles() -> TitleGenerationResult:
            return self.regenerate_titles(opportunity_id)

        def _gen_body() -> BodyGenerationResult:
            return self.regenerate_body(opportunity_id)

        def _gen_images() -> ImageBriefGenerationResult:
            return self.regenerate_image_briefs(opportunity_id)

        with ThreadPoolExecutor(max_workers=3) as pool:
            title_future = pool.submit(_gen_titles)
            body_future = pool.submit(_gen_body)
            image_future = pool.submit(_gen_images)

        try:
            title_result = title_future.result(timeout=60)
            results["titles"] = title_result.model_dump(mode="json")
        except Exception as exc:
            errors["titles"] = str(exc)
            results["titles"] = {}

        try:
            body_result = body_future.result(timeout=60)
            results["body"] = body_result.model_dump(mode="json")
        except Exception as exc:
            errors["body"] = str(exc)
            results["body"] = {}

        try:
            image_result = image_future.result(timeout=60)
            results["image_briefs"] = image_result.model_dump(mode="json")
        except Exception as exc:
            errors["image_briefs"] = str(exc)
            results["image_briefs"] = {}

        if errors:
            results["_generation_errors"] = errors
            logger.warning("部分生成失败: %s", errors)

        return results

    def assemble_asset_bundle(self, opportunity_id: str) -> AssetBundle:
        """从会话中间产物组装资产包。"""
        from apps.content_planning.services.asset_assembler import AssetAssembler

        session = self._get_session(opportunity_id)
        if session.titles is None or session.body is None:
            self._run_generation(opportunity_id)
            session = self._get_session(opportunity_id)

        return AssetAssembler.assemble(
            opportunity_id=opportunity_id,
            plan_id=session.note_plan.plan_id if session.note_plan else "",
            template_id=session.match_result.primary_template.template_id if session.match_result else "",
            template_name=session.match_result.primary_template.template_name if session.match_result else "",
            titles=session.titles,
            body=session.body,
            image_briefs=session.image_briefs,
            lineage=self._build_lineage(session),
        )

    def batch_compile(self, opportunity_ids: list[str]) -> dict[str, Any]:
        """批量编译多个 promoted 卡。"""
        succeeded: list[dict] = []
        failed: list[dict] = []
        for oid in opportunity_ids:
            try:
                self.compile_note_plan(oid, with_generation=True)
                bundle = self.assemble_asset_bundle(oid)
                succeeded.append(bundle.model_dump(mode="json"))
            except Exception as exc:
                failed.append({"opportunity_id": oid, "error": str(exc)})
        return {"succeeded": succeeded, "failed": failed, "total": len(opportunity_ids)}
