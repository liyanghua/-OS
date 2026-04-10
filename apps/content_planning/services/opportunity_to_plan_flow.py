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
from apps.content_planning.exceptions import OpportunityNotPromotedError, StageApplyConflictError
from apps.content_planning.gateway.event_bus import emit_object_updated
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
_STALE_KEYS = ("brief", "match", "strategy", "plan", "titles", "body", "image_briefs", "asset_bundle")


class _SessionState:
    """单个 opportunity 的编排中间状态（内存热层）。"""

    __slots__ = (
        "opportunity_id", "brief", "match_result", "strategy",
        "note_plan", "titles", "body", "image_briefs", "asset_bundle",
        "templates", "selected_tpl", "updated_at",
        "pipeline_run_id", "stale_flags",
        "workspace_id", "brand_id", "campaign_id",
        "created_by", "updated_by", "visibility",
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
        self.asset_bundle: AssetBundle | None = None
        self.templates: list = []
        self.selected_tpl = None
        self.updated_at = datetime.now(UTC)
        self.pipeline_run_id: str = uuid.uuid4().hex[:16]
        self.stale_flags: dict[str, bool] = {k: False for k in _STALE_KEYS}
        self.workspace_id = ""
        self.brand_id = ""
        self.campaign_id = ""
        self.created_by = ""
        self.updated_by = ""
        self.visibility = "workspace"

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
            self.asset_bundle = None
            self.stale_flags["titles"] = True
            self.stale_flags["body"] = True
            self.stale_flags["image_briefs"] = True
            self.stale_flags["asset_bundle"] = True
        self.updated_at = datetime.now(UTC)

    def _mark_fresh(self, key: str) -> None:
        self.stale_flags[key] = False


class OpportunityToPlanFlow:
    """统一编排入口：promoted 卡 -> Brief -> 选模板 -> Strategy -> NotePlan -> (可选) 内容生成。"""

    def __init__(
        self,
        adapter: IntelHubAdapter | None = None,
        plan_store: Any | None = None,
        platform_store: Any | None = None,
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
        self._platform_store = platform_store

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
                if persisted.get("asset_bundle"):
                    try:
                        session.asset_bundle = AssetBundle.model_validate(persisted["asset_bundle"])
                    except Exception:
                        pass
                if persisted.get("stale_flags"):
                    session.stale_flags.update(persisted["stale_flags"])
                session.workspace_id = persisted.get("workspace_id") or ""
                session.brand_id = persisted.get("brand_id") or ""
                session.campaign_id = persisted.get("campaign_id") or ""
                session.created_by = persisted.get("created_by") or ""
                session.updated_by = persisted.get("updated_by") or ""
                session.visibility = persisted.get("visibility") or "workspace"
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
            workspace_id=session.workspace_id,
            brand_id=session.brand_id,
            campaign_id=session.campaign_id,
            created_by=session.created_by,
            updated_by=session.updated_by,
            visibility=session.visibility,
            brief=session.brief,
            match_result=session.match_result,
            strategy=session.strategy,
            plan=session.note_plan,
            titles=session.titles,
            body=session.body,
            image_briefs=session.image_briefs,
            asset_bundle=session.asset_bundle,
            pipeline_run_id=session.pipeline_run_id,
            stale_flags=session.stale_flags,
        )

    def _build_lineage(self, session: _SessionState) -> PlanLineage:
        """根据当前 session 状态构建 lineage 快照。"""
        return PlanLineage(
            pipeline_run_id=session.pipeline_run_id,
            source_note_ids=session.brief.source_note_ids if session.brief else [],
            opportunity_id=session.opportunity_id,
            workspace_id=session.workspace_id,
            brand_id=session.brand_id,
            campaign_id=session.campaign_id,
            brief_id=session.brief.brief_id if session.brief else "",
            template_id=session.match_result.primary_template.template_id if session.match_result else "",
            strategy_id=session.strategy.strategy_id if session.strategy else "",
            plan_id=session.note_plan.plan_id if session.note_plan else "",
        )

    def _next_version(self, existing: Any | None, *, attr_name: str = "version") -> int:
        if existing is None:
            return 1
        value = getattr(existing, attr_name, 1)
        if isinstance(value, int) and value >= 1:
            return value + 1
        return 1

    def _apply_context(
        self,
        session: _SessionState,
        model: Any,
        *,
        previous: Any | None = None,
        version_attr: str = "version",
    ) -> Any:
        if hasattr(model, "workspace_id"):
            model.workspace_id = session.workspace_id
        if hasattr(model, "brand_id"):
            model.brand_id = session.brand_id
        if hasattr(model, "campaign_id"):
            model.campaign_id = session.campaign_id
        if hasattr(model, "created_by") and not getattr(model, "created_by", ""):
            model.created_by = session.created_by
        if hasattr(model, "updated_by"):
            model.updated_by = session.updated_by or session.created_by
        if hasattr(model, "visibility"):
            model.visibility = session.visibility
        if hasattr(model, version_attr):
            setattr(model, version_attr, self._next_version(previous, attr_name=version_attr))
        return model

    def _record_usage(self, session: _SessionState, *, event_type: str, object_type: str, object_id: str, units: int = 1) -> None:
        if self._platform_store is None or not session.workspace_id:
            return
        self._platform_store.record_usage(
            workspace_id=session.workspace_id,
            brand_id=session.brand_id,
            campaign_id=session.campaign_id,
            event_type=event_type,
            units=units,
            object_type=object_type,
            object_id=object_id,
            actor_user_id=session.updated_by or session.created_by,
        )

    def _snapshot_version(self, session: _SessionState, object_type: str, obj: Any) -> None:
        """Persist a version snapshot for history/rollback."""
        if self._store is None or obj is None:
            return
        try:
            self._store.append_version(session.opportunity_id, object_type, obj)
        except Exception:
            logger.debug("append_version failed for %s/%s", session.opportunity_id, object_type, exc_info=True)

    def _apply_locks(self, new_obj: Any, old_obj: Any) -> Any:
        """Preserve locked field values from old_obj onto new_obj."""
        if old_obj is None or not hasattr(old_obj, "locks") or old_obj.locks is None:
            return new_obj
        for field_name in old_obj.locks.locked_field_names():
            if hasattr(old_obj, field_name) and hasattr(new_obj, field_name):
                setattr(new_obj, field_name, getattr(old_obj, field_name))
        if hasattr(new_obj, "locks"):
            new_obj.locks = old_obj.locks
        return new_obj

    def _get_stage_object(self, session: _SessionState, stage: str) -> tuple[Any | None, str, str]:
        if stage == "brief":
            return session.brief, "brief", "version"
        if stage == "strategy":
            return session.strategy, "strategy", "strategy_version"
        if stage == "plan":
            return session.note_plan, "plan", "version"
        if stage == "asset":
            return session.asset_bundle, "asset_bundle", "version"
        raise ValueError(f"Unsupported stage: {stage}")

    def _get_field_value(self, obj: Any, field_path: str) -> Any:
        current = obj
        for part in field_path.split("."):
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
        return current

    def _set_field_value(self, obj: Any, field_path: str, value: Any) -> bool:
        parts = field_path.split(".")
        current = obj
        for part in parts[:-1]:
            if current is None:
                return False
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
        if current is None:
            return False
        final = parts[-1]
        if isinstance(current, dict):
            current[final] = value
            return True
        if not hasattr(current, final):
            return False
        setattr(current, final, value)
        return True

    def ensure_stage_object(self, opportunity_id: str, stage: str) -> Any:
        session = self._get_session(opportunity_id)
        obj, _, _ = self._get_stage_object(session, stage)
        if obj is not None:
            return obj
        if stage == "brief":
            return self.build_brief(opportunity_id)
        if stage == "strategy":
            return self.build_strategy(opportunity_id)
        if stage == "plan":
            return self.build_plan(opportunity_id)
        if stage == "asset":
            return self.assemble_asset_bundle(opportunity_id)
        raise ValueError(f"Unsupported stage: {stage}")

    def get_stage_snapshot(self, opportunity_id: str, stage: str) -> dict[str, Any]:
        obj = self.ensure_stage_object(opportunity_id, stage)
        session = self._get_session(opportunity_id)
        _, object_type, version_attr = self._get_stage_object(session, stage)
        object_id_attr = {
            "brief": "brief_id",
            "strategy": "strategy_id",
            "plan": "plan_id",
            "asset": "asset_bundle_id",
        }[stage]
        return {
            "stage": stage,
            "object_type": object_type,
            "object_id": getattr(obj, object_id_attr, ""),
            "version": getattr(obj, version_attr, 1),
            "payload": obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj,
        }

    def build_stage_diff(self, opportunity_id: str, stage: str, proposed_updates: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
        session = self._get_session(opportunity_id)
        obj = self.ensure_stage_object(opportunity_id, stage)
        locked_fields = obj.locks.locked_field_names() if getattr(obj, "locks", None) else []
        changes: list[dict[str, Any]] = []
        blocked: list[str] = []
        for field, value in proposed_updates.items():
            is_blocked = field in locked_fields
            if is_blocked:
                blocked.append(field)
            changes.append(
                {
                    "field": field,
                    "before": self._get_field_value(obj, field),
                    "after": value,
                    "blocked": is_blocked,
                }
            )
        return changes, blocked

    def bind_workspace_context(
        self,
        *,
        opportunity_id: str,
        workspace_id: str,
        user_id: str,
        api_token: str,
        brand_id: str | None = None,
        campaign_id: str | None = None,
        visibility: str = "workspace",
    ) -> dict[str, str]:
        if self._platform_store is None:
            raise ValueError("B2B platform store is not configured")
        membership = self._platform_store.authorize(
            workspace_id=workspace_id,
            user_id=user_id,
            api_token=api_token,
            allowed_roles=("admin", "strategist", "editor", "designer", "reviewer", "viewer"),
        )
        session = self._get_session(opportunity_id)
        queued = self._platform_store.get_queue_entry(workspace_id, opportunity_id)
        session.workspace_id = workspace_id
        session.brand_id = brand_id or (queued.brand_id if queued else "")
        session.campaign_id = campaign_id or (queued.campaign_id if queued else "")
        session.created_by = session.created_by or user_id
        session.updated_by = user_id
        session.visibility = visibility
        self._persist(session, status="draft")
        return {
            "workspace_id": workspace_id,
            "brand_id": session.brand_id,
            "campaign_id": session.campaign_id,
            "role": membership.role,
        }

    # ── 原子操作 ──────────────────────────────────────────────

    def build_brief(
        self,
        opportunity_id: str,
        *,
        council_escalation_notes: str | None = None,
    ) -> OpportunityBrief:
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
        brief.brief_status = "generated"
        brief = self._apply_context(session, brief, previous=session.brief)

        brief = self._apply_locks(brief, session.brief)
        if council_escalation_notes and council_escalation_notes.strip():
            extra = "\n\n【Council 结构化重写输入】\n" + council_escalation_notes.strip()
            base = (brief.why_worth_doing or "").strip()
            brief.why_worth_doing = base + extra if base else extra.strip()
        session.brief = brief
        self._snapshot_version(session, "brief", brief)
        session.invalidate_downstream("match")
        session._mark_fresh("brief")
        self._persist(session, status="generated")
        emit_object_updated(opportunity_id, "brief", brief.brief_id)
        self._record_usage(session, event_type="brief_generated", object_type="brief", object_id=brief.brief_id)
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
            "why_worth_doing", "competitive_angle",
        }
        for key, val in partial.items():
            if key in editable and hasattr(session.brief, key):
                setattr(session.brief, key, val)

        session.brief.brief_status = "reviewed"
        session.brief.updated_at = datetime.now(UTC)
        session.brief.updated_by = session.updated_by or session.created_by
        session.brief.version = self._next_version(session.brief)
        session.invalidate_downstream("match")
        self._persist(session, status="generated")
        emit_object_updated(opportunity_id, "brief", session.brief.brief_id, agent_name="人工编辑")
        return session.brief

    def apply_stage_updates(
        self,
        opportunity_id: str,
        stage: str,
        proposed_updates: dict[str, Any],
        *,
        selected_fields: list[str] | None = None,
        actor_user_id: str = "",
        base_version: int | None = None,
    ) -> dict[str, Any]:
        session = self._get_session(opportunity_id)
        selected = set(selected_fields or proposed_updates.keys())
        applied_fields: list[str] = []
        skipped_fields: list[str] = []

        if stage == "brief":
            if session.brief is None:
                session.brief = self.build_brief(opportunity_id)

            brief = session.brief
            assert brief is not None
            if base_version is not None and brief.version != base_version:
                raise StageApplyConflictError(
                    f"Brief version changed from {base_version} to {brief.version}",
                    stage="brief",
                    stale_flags=dict(session.stale_flags),
                )

            editable = {
                "target_user", "target_scene", "content_goal", "primary_value",
                "visual_style_direction", "avoid_directions", "template_hints",
                "core_motive", "price_positioning", "target_audience",
                "why_worth_doing", "competitive_angle",
            }

            for field, value in proposed_updates.items():
                if field not in selected:
                    continue
                if field not in editable:
                    skipped_fields.append(field)
                    continue
                if brief.locks and brief.locks.is_locked(field):
                    skipped_fields.append(field)
                    continue
                if hasattr(brief, field):
                    setattr(brief, field, value)
                    applied_fields.append(field)

            brief.brief_status = "reviewed"
            brief.updated_at = datetime.now(UTC)
            brief.updated_by = actor_user_id or session.updated_by or session.created_by
            brief.version = self._next_version(brief)
            session.brief = brief
            self._snapshot_version(session, "brief", brief)
            session.invalidate_downstream("match")
            session._mark_fresh("brief")
            self._persist(session, status="generated")
            emit_object_updated(opportunity_id, "brief", brief.brief_id, agent_name="Agent Proposal")
            return {
                "brief": brief.model_dump(mode="json"),
                "payload": brief.model_dump(mode="json"),
                "applied_fields": applied_fields,
                "skipped_fields": skipped_fields,
                "stale_flags": dict(session.stale_flags),
            }

        if stage == "strategy":
            if session.brief is None:
                session.brief = self.build_brief(opportunity_id)
            if session.stale_flags.get("brief"):
                raise StageApplyConflictError(
                    "Brief is stale. Refresh Brief before applying a Strategy proposal.",
                    stage="strategy",
                    stale_flags=dict(session.stale_flags),
                )
            if session.strategy is None:
                session.strategy = self.build_strategy(opportunity_id)

            strategy = session.strategy
            assert strategy is not None
            if base_version is not None and strategy.strategy_version != base_version:
                raise StageApplyConflictError(
                    f"Strategy version changed from {base_version} to {strategy.strategy_version}",
                    stage="strategy",
                    stale_flags=dict(session.stale_flags),
                )

            editable = {
                "positioning_statement",
                "new_hook",
                "new_angle",
                "tone_of_voice",
                "hook_strategy",
                "cta_strategy",
                "scene_emphasis",
                "rationale",
                "keep_elements",
                "replace_elements",
                "enhance_elements",
                "avoid_elements",
                "title_strategy",
                "body_strategy",
                "image_strategy",
                "differentiation_axis",
                "risk_notes",
                "comparison_note",
            }

            for field, value in proposed_updates.items():
                if field not in selected:
                    continue
                if field not in editable:
                    skipped_fields.append(field)
                    continue
                if strategy.locks and strategy.locks.is_locked(field):
                    skipped_fields.append(field)
                    continue
                if hasattr(strategy, field):
                    setattr(strategy, field, value)
                    applied_fields.append(field)

            strategy.strategy_status = "reviewed"
            strategy.updated_at = datetime.now(UTC)
            strategy.updated_by = actor_user_id or session.updated_by or session.created_by
            strategy.strategy_version = self._next_version(strategy)
            session.strategy = strategy
            self._snapshot_version(session, "strategy", strategy)
            session.invalidate_downstream("plan")
            session._mark_fresh("strategy")
            self._persist(session, status="generated")
            emit_object_updated(opportunity_id, "strategy", strategy.strategy_id, agent_name="Agent Proposal")
            return {
                "strategy": strategy.model_dump(mode="json"),
                "payload": strategy.model_dump(mode="json"),
                "applied_fields": applied_fields,
                "skipped_fields": skipped_fields,
                "stale_flags": dict(session.stale_flags),
            }

        if stage == "plan":
            if session.strategy is None:
                session.strategy = self.build_strategy(opportunity_id)
            if session.stale_flags.get("strategy"):
                raise StageApplyConflictError(
                    "Strategy is stale. Refresh Strategy before applying a Plan proposal.",
                    stage="plan",
                    stale_flags=dict(session.stale_flags),
                )
            if session.note_plan is None:
                session.note_plan = self.build_plan(opportunity_id)

            note_plan = session.note_plan
            assert note_plan is not None
            if base_version is not None and note_plan.version != base_version:
                raise StageApplyConflictError(
                    f"Plan version changed from {base_version} to {note_plan.version}",
                    stage="plan",
                    stale_flags=dict(session.stale_flags),
                )

            editable = {
                "note_goal",
                "target_user",
                "target_scene",
                "core_selling_point",
                "theme",
                "tone_of_voice",
                "title_plan.title_axes",
                "title_plan.candidate_titles",
                "title_plan.do_not_use_phrases",
                "body_plan.opening_hook",
                "body_plan.body_outline",
                "body_plan.cta_direction",
                "body_plan.tone_notes",
                "image_plan.priority_axis",
                "image_plan.global_notes",
                "image_plan.image_slots",
                "publish_notes",
            }

            for field, value in proposed_updates.items():
                if field not in selected:
                    continue
                if field not in editable:
                    skipped_fields.append(field)
                    continue
                if note_plan.locks and note_plan.locks.is_locked(field):
                    skipped_fields.append(field)
                    continue
                if self._set_field_value(note_plan, field, value):
                    applied_fields.append(field)
                else:
                    skipped_fields.append(field)

            note_plan.plan_status = "reviewed"
            note_plan.updated_at = datetime.now(UTC)
            note_plan.updated_by = actor_user_id or session.updated_by or session.created_by
            note_plan.version = self._next_version(note_plan)
            session.note_plan = note_plan
            self._snapshot_version(session, "plan", note_plan)
            session.invalidate_downstream("generation")
            session._mark_fresh("plan")
            self._persist(session, status="generated")
            emit_object_updated(opportunity_id, "plan", note_plan.plan_id, agent_name="Agent Proposal")
            return {
                "plan": note_plan.model_dump(mode="json"),
                "payload": note_plan.model_dump(mode="json"),
                "applied_fields": applied_fields,
                "skipped_fields": skipped_fields,
                "stale_flags": dict(session.stale_flags),
            }

        if stage == "asset":
            blocking_keys = ("plan", "titles", "body", "image_briefs")
            if any(session.stale_flags.get(key) for key in blocking_keys):
                raise StageApplyConflictError(
                    "Asset inputs are stale. Refresh Plan / generation objects before applying an Asset proposal.",
                    stage="asset",
                    stale_flags=dict(session.stale_flags),
                )
            if session.asset_bundle is None:
                session.asset_bundle = self.assemble_asset_bundle(opportunity_id)

            bundle = session.asset_bundle
            assert bundle is not None
            if base_version is not None and bundle.version != base_version:
                raise StageApplyConflictError(
                    f"Asset version changed from {base_version} to {bundle.version}",
                    stage="asset",
                    stale_flags=dict(session.stale_flags),
                )

            editable = {
                "title_candidates",
                "body_outline",
                "body_draft",
                "image_execution_briefs",
            }

            for field, value in proposed_updates.items():
                if field not in selected:
                    continue
                if field not in editable:
                    skipped_fields.append(field)
                    continue
                if bundle.locks and bundle.locks.is_locked(field):
                    skipped_fields.append(field)
                    continue
                if self._set_field_value(bundle, field, value):
                    applied_fields.append(field)
                else:
                    skipped_fields.append(field)

            bundle.updated_at = datetime.now(UTC)
            bundle.updated_by = actor_user_id or session.updated_by or session.created_by
            bundle.version = self._next_version(bundle)
            bundle.export_status = "ready" if (bundle.title_candidates and bundle.body_draft) else "draft"
            bundle.approval_status = "pending_review"
            session.asset_bundle = bundle
            self._snapshot_version(session, "asset_bundle", bundle)
            session._mark_fresh("asset_bundle")
            self._persist(session, status="generated")
            emit_object_updated(opportunity_id, "asset_bundle", bundle.asset_bundle_id, agent_name="Agent Proposal")
            return {
                "asset_bundle": bundle.model_dump(mode="json"),
                "payload": bundle.model_dump(mode="json"),
                "applied_fields": applied_fields,
                "skipped_fields": skipped_fields,
                "stale_flags": dict(session.stale_flags),
            }

        raise ValueError(f"Stage apply is not enabled yet for {stage}")

    def apply_council_advisory_draft(
        self,
        opportunity_id: str,
        proposal: dict[str, Any],
        *,
        actor_user_id: str = "",
    ) -> dict[str, Any]:
        """将 Council 共识/下一步/备选方向写入差异化切入（无严格字段 diff 时的草稿通道）。"""
        session = self._get_session(opportunity_id)
        if session.brief is None:
            session.brief = self.build_brief(opportunity_id)
        brief = session.brief
        assert brief is not None
        base_ver = proposal.get("base_version")
        if base_ver is not None and brief.version != int(base_ver):
            raise StageApplyConflictError(
                f"Brief version changed from {base_ver} to {brief.version}",
                stage="brief",
                stale_flags=dict(session.stale_flags),
            )

        parts: list[str] = []
        if proposal.get("summary"):
            parts.append("【共识】\n" + str(proposal["summary"]))
        for a in proposal.get("agreements") or []:
            parts.append("· " + str(a))
        for step in proposal.get("recommended_next_steps") or []:
            parts.append("→ " + str(step))
        for alt in proposal.get("alternatives") or []:
            if isinstance(alt, dict) and alt.get("label"):
                parts.append(f"[{alt['label']}] {alt.get('summary', '')}")
        draft_body = "\n\n".join([p for p in parts if p])
        if not draft_body.strip():
            draft_body = str(proposal.get("summary") or "（Council 草稿）")

        base = (brief.competitive_angle or "").strip()
        block = "\n\n——\n【Council 草稿采纳】\n" + draft_body
        new_angle = (base + block) if base else block.strip()

        return self.apply_stage_updates(
            opportunity_id,
            "brief",
            {"competitive_angle": new_angle},
            selected_fields=["competitive_angle"],
            actor_user_id=actor_user_id,
            base_version=brief.version,
        )

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
        self._record_usage(session, event_type="templates_matched", object_type="template_match", object_id=match_result.primary_template.template_id)
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

        previous_strategy = session.strategy
        strategy = self._strategy_gen.generate(session.brief, mr, selected_tpl)

        lineage = self._build_lineage(session)
        lineage.strategy_id = strategy.strategy_id
        lineage.template_id = selected_tpl.template_id
        strategy.lineage = lineage
        strategy.strategy_status = "generated"
        strategy = self._apply_context(
            session,
            strategy,
            previous=previous_strategy,
            version_attr="strategy_version",
        )

        strategy = self._apply_locks(strategy, previous_strategy)
        session.strategy = strategy
        self._snapshot_version(session, "strategy", strategy)
        session.invalidate_downstream("plan")
        session._mark_fresh("strategy")
        self._persist(session, status="generated")
        emit_object_updated(opportunity_id, "strategy", strategy.strategy_id)
        self._record_usage(session, event_type="strategy_generated", object_type="strategy", object_id=strategy.strategy_id)
        return strategy

    def build_plan(self, opportunity_id: str) -> NewNotePlan:
        session = self._get_session(opportunity_id)
        if session.strategy is None:
            self.build_strategy(opportunity_id)

        assert session.brief is not None
        assert session.strategy is not None
        assert session.match_result is not None
        assert session.selected_tpl is not None

        previous_plan = session.note_plan
        note_plan = self._plan_compiler.compile(
            session.brief, session.strategy, session.match_result, session.selected_tpl,
        )

        lineage = self._build_lineage(session)
        lineage.plan_id = note_plan.plan_id
        note_plan.lineage = lineage
        note_plan.plan_status = "generated"
        note_plan = self._apply_context(session, note_plan, previous=previous_plan)

        note_plan = self._apply_locks(note_plan, previous_plan)
        session.note_plan = note_plan
        self._snapshot_version(session, "plan", note_plan)
        session._mark_fresh("plan")
        self._persist(session, status="generated")
        emit_object_updated(opportunity_id, "plan", note_plan.plan_id)
        self._record_usage(session, event_type="plan_generated", object_type="plan", object_id=note_plan.plan_id)
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
        emit_object_updated(opportunity_id, "titles", session.note_plan.plan_id if session.note_plan else "")
        self._record_usage(session, event_type="titles_generated", object_type="title_generation", object_id=session.note_plan.plan_id)
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
        emit_object_updated(opportunity_id, "body", session.note_plan.plan_id if session.note_plan else "")
        self._record_usage(session, event_type="body_generated", object_type="body_generation", object_id=session.note_plan.plan_id)
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
        emit_object_updated(opportunity_id, "image_briefs", session.note_plan.plan_id if session.note_plan else "")
        self._record_usage(session, event_type="image_briefs_generated", object_type="image_generation", object_id=session.note_plan.plan_id)
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

        self._record_usage(self._get_session(opportunity_id), event_type="note_plan_compiled", object_type="opportunity", object_id=opportunity_id)
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
            "workspace_id": session.workspace_id,
            "brand_id": session.brand_id,
            "campaign_id": session.campaign_id,
            "created_by": session.created_by,
            "updated_by": session.updated_by,
            "visibility": session.visibility,
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
        if session.asset_bundle:
            data["asset_bundle"] = session.asset_bundle.model_dump(mode="json")
        if self._platform_store is not None and session.workspace_id:
            approvals = self._platform_store.list_approvals(session.workspace_id)
            summary: dict[str, dict[str, Any]] = {}
            for record in approvals:
                if record.object_id in {
                    getattr(session.brief, "brief_id", ""),
                    getattr(session.strategy, "strategy_id", ""),
                    getattr(session.note_plan, "plan_id", ""),
                    getattr(session.asset_bundle, "asset_bundle_id", ""),
                }:
                    summary[record.object_type] = record.model_dump(mode="json")
            if summary:
                data["approval_summary"] = {
                    key: {"latest_decision": value["decision"], "reviewer_id": value["reviewer_id"], "notes": value["notes"]}
                    for key, value in summary.items()
                }
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
        if session.asset_bundle is not None and not any(
            session.stale_flags.get(key) for key in ("titles", "body", "image_briefs", "asset_bundle")
        ):
            return session.asset_bundle
        if session.titles is None or session.body is None:
            self._run_generation(opportunity_id)
            session = self._get_session(opportunity_id)

        bundle = AssetAssembler.assemble(
            opportunity_id=opportunity_id,
            plan_id=session.note_plan.plan_id if session.note_plan else "",
            template_id=session.match_result.primary_template.template_id if session.match_result else "",
            template_name=session.match_result.primary_template.template_name if session.match_result else "",
            workspace_id=session.workspace_id,
            brand_id=session.brand_id,
            campaign_id=session.campaign_id,
            created_by=session.created_by,
            updated_by=session.updated_by or session.created_by,
            visibility=session.visibility,
            version=self._next_version(session.asset_bundle),
            titles=session.titles,
            body=session.body,
            image_briefs=session.image_briefs,
            lineage=self._build_lineage(session),
        )
        session.asset_bundle = bundle
        self._snapshot_version(session, "asset_bundle", bundle)
        session._mark_fresh("asset_bundle")
        self._persist(session, status="generated")
        self._record_usage(session, event_type="asset_bundle_assembled", object_type="asset_bundle", object_id=bundle.asset_bundle_id)
        return bundle

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

    def mark_asset_bundle_exported(self, opportunity_id: str) -> AssetBundle:
        session = self._get_session(opportunity_id)
        bundle = session.asset_bundle or self.assemble_asset_bundle(opportunity_id)
        if any(session.stale_flags.get(key) for key in ("plan", "titles", "body", "image_briefs")):
            raise StageApplyConflictError(
                "Asset bundle inputs are stale. Refresh upstream objects before export.",
                stage="asset",
                stale_flags=dict(session.stale_flags),
            )
        if bundle.export_status == "draft":
            raise StageApplyConflictError(
                "Asset bundle is not export-ready yet. Complete titles/body/assets before export.",
                stage="asset",
                stale_flags=dict(session.stale_flags),
            )
        if bundle.approval_status in {"changes_requested", "rejected"}:
            raise StageApplyConflictError(
                f"Asset bundle approval_status={bundle.approval_status} blocks export.",
                stage="asset",
                stale_flags=dict(session.stale_flags),
            )
        bundle.export_status = "exported"
        bundle.updated_at = datetime.now(UTC)
        if session.updated_by:
            bundle.updated_by = session.updated_by
        session.asset_bundle = bundle
        self._persist(session, status="exported")
        self._record_usage(
            session,
            event_type="asset_bundle_exported",
            object_type="asset_bundle",
            object_id=bundle.asset_bundle_id,
        )
        return bundle

    def approve_object(
        self,
        *,
        opportunity_id: str,
        object_type: str,
        decision: str,
        notes: str,
        workspace_id: str,
        user_id: str,
        api_token: str,
    ) -> Any:
        if self._platform_store is None:
            raise ValueError("B2B platform store is not configured")
        membership = self._platform_store.authorize(
            workspace_id=workspace_id,
            user_id=user_id,
            api_token=api_token,
            allowed_roles=("admin", "strategist", "reviewer"),
        )
        session = self._get_session(opportunity_id)
        if session.workspace_id and session.workspace_id != workspace_id:
            raise PermissionError("session belongs to another workspace")
        target: Any | None = None
        target_id = ""
        target_version = 1
        if object_type == "brief":
            if session.brief is None:
                session.brief = self.build_brief(opportunity_id)
            target = session.brief
            target_id = target.brief_id
            target.brief_status = "approved" if decision == "approved" else "reviewed"
            target_version = getattr(target, "version", 1)
        elif object_type == "strategy":
            if session.strategy is None:
                target = self.build_strategy(opportunity_id)
            else:
                target = session.strategy
            target_id = target.strategy_id
            target.strategy_status = "approved" if decision == "approved" else "reviewed"
            target_version = getattr(target, "strategy_version", 1)
        elif object_type == "plan":
            if session.note_plan is None:
                target = self.build_plan(opportunity_id)
            else:
                target = session.note_plan
            target_id = target.plan_id
            target.plan_status = "approved" if decision == "approved" else "reviewed"
            target_version = getattr(target, "version", 1)
        elif object_type == "asset_bundle":
            target = session.asset_bundle or self.assemble_asset_bundle(opportunity_id)
            target_id = target.asset_bundle_id
            target.export_status = "ready" if decision == "approved" else target.export_status
            target_version = getattr(target, "version", 1)
            session.asset_bundle = target
        else:
            raise ValueError(f"unknown object_type: {object_type}")

        target.approval_status = decision
        if hasattr(target, "updated_by"):
            target.updated_by = user_id
        self._persist(session, status="generated")
        approval = self._platform_store.record_approval(
            workspace_id=workspace_id,
            object_type=object_type,
            object_id=target_id,
            object_version=target_version,
            decision=decision,
            reviewer_id=user_id,
            reviewer_role=membership.role,
            notes=notes,
        )
        return approval
