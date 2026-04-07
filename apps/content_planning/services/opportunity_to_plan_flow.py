"""OpportunityToPlanFlow：从 promoted 机会卡到完整内容策划的一站式编排。

v2: 增加会话缓存 + 局部重生成 + 原子操作方法。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from apps.content_planning.adapters.intel_hub_adapter import IntelHubAdapter
from apps.content_planning.exceptions import OpportunityNotPromotedError
from apps.content_planning.schemas.content_generation import (
    BodyGenerationResult,
    ImageBriefGenerationResult,
    TitleGenerationResult,
)
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


class _SessionState:
    """单个 opportunity 的编排中间状态。"""

    __slots__ = (
        "opportunity_id", "brief", "match_result", "strategy",
        "note_plan", "titles", "body", "image_briefs",
        "templates", "selected_tpl", "updated_at",
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

    def invalidate_downstream(self, from_stage: str = "brief") -> None:
        """从某阶段开始失效下游缓存。"""
        stages = ["brief", "match", "strategy", "plan", "generation"]
        idx = stages.index(from_stage) if from_stage in stages else 0
        if idx <= 1:
            self.match_result = None
        if idx <= 2:
            self.strategy = None
        if idx <= 3:
            self.note_plan = None
        if idx <= 4:
            self.titles = None
            self.body = None
            self.image_briefs = None
        self.updated_at = datetime.now(UTC)


class OpportunityToPlanFlow:
    """统一编排入口：promoted 卡 -> Brief -> 选模板 -> Strategy -> NotePlan -> (可选) 内容生成。"""

    def __init__(self, adapter: IntelHubAdapter | None = None) -> None:
        self._adapter = adapter or IntelHubAdapter()
        self._brief_compiler = BriefCompiler()
        self._strategy_gen = RewriteStrategyGenerator()
        self._plan_compiler = NewNotePlanCompiler()
        self._title_gen = TitleGenerator()
        self._body_gen = BodyGenerator()
        self._image_gen = ImageBriefGenerator()
        self._retriever = TemplateRetriever()
        self._cache: dict[str, _SessionState] = {}

    def _get_session(self, opportunity_id: str) -> _SessionState:
        if opportunity_id not in self._cache:
            self._cache[opportunity_id] = _SessionState(opportunity_id)
        return self._cache[opportunity_id]

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
        session.brief = brief
        session.invalidate_downstream("match")
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
            ),
            secondary_templates=[
                TemplateMatchEntry(
                    template_id=m.template_id,
                    template_name=m.template_name,
                    score=m.score,
                    reason=m.reason,
                )
                for m in matches[1:4]
            ],
            rejected_templates=[
                TemplateMatchEntry(
                    template_id=m.template_id,
                    template_name=m.template_name,
                    score=m.score,
                    reason=m.reason,
                )
                for m in matches
                if m.score <= 0
            ],
        )
        session.match_result = match_result
        session.invalidate_downstream("strategy")
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
        session.strategy = strategy
        session.invalidate_downstream("plan")
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
        session.note_plan = note_plan
        return note_plan

    def regenerate_titles(self, opportunity_id: str) -> TitleGenerationResult:
        session = self._get_session(opportunity_id)
        if session.note_plan is None:
            self.build_plan(opportunity_id)
        assert session.note_plan is not None
        assert session.strategy is not None
        result = self._title_gen.generate(session.note_plan, session.strategy)
        session.titles = result
        return result

    def regenerate_body(self, opportunity_id: str) -> BodyGenerationResult:
        session = self._get_session(opportunity_id)
        if session.note_plan is None:
            self.build_plan(opportunity_id)
        assert session.note_plan is not None
        assert session.strategy is not None
        result = self._body_gen.generate(session.note_plan, session.strategy)
        session.body = result
        return result

    def regenerate_image_briefs(self, opportunity_id: str) -> ImageBriefGenerationResult:
        session = self._get_session(opportunity_id)
        if session.note_plan is None:
            self.build_plan(opportunity_id)
        assert session.note_plan is not None
        assert session.strategy is not None
        result = self._image_gen.generate(session.note_plan, session.strategy)
        session.image_briefs = result
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
        data: dict[str, Any] = {"opportunity_id": opportunity_id}
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
        title_result = self.regenerate_titles(opportunity_id)
        body_result = self.regenerate_body(opportunity_id)
        image_result = self.regenerate_image_briefs(opportunity_id)
        return {
            "titles": title_result.model_dump(mode="json"),
            "body": body_result.model_dump(mode="json"),
            "image_briefs": image_result.model_dump(mode="json"),
        }
