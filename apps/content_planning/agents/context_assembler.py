"""PlanningContextAssembler: 统一上下文组装，三条 AI 入口共用。

解决 run-agent / chat / council 三条路径各自组装上下文、互不通气的问题。
所有 AI 入口统一调用 assemble() 获得 PlanningContext。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from apps.content_planning.agents.base import AgentContext, RequestContextBundle
from apps.content_planning.agents.memory import AgentMemory

logger = logging.getLogger(__name__)


@dataclass
class PlanningContext:
    """统一上下文：Stage 对象 + 上下游摘要 + Council 共识 + 评分短板 + 项目记忆。"""

    opportunity_id: str = ""
    stage: str = ""
    mode: str = "deep"

    # Stage objects
    current_object_summary: str = ""
    upstream_summary: str = ""
    downstream_completeness: dict[str, bool] = field(default_factory=dict)

    # Council history
    recent_council_consensuses: list[str] = field(default_factory=list)

    # Open questions & scoring
    open_questions: list[str] = field(default_factory=list)
    scoring_shortfalls: list[dict[str, Any]] = field(default_factory=list)

    # Project-level memory
    project_memory_context: str = ""
    brand_preferences: str = ""

    # Raw bundle for backward compat
    bundle: RequestContextBundle | None = None


class PlanningContextAssembler:
    """统一上下文组装器 — 从 routes._build_request_context_bundle 提取并增强。"""

    def __init__(self, memory: AgentMemory | None = None) -> None:
        self._memory = memory or AgentMemory()

    def assemble(
        self,
        opportunity_id: str,
        stage: str,
        mode: str = "deep",
        *,
        session: Any = None,
        flow: Any = None,
        bundle: RequestContextBundle | None = None,
    ) -> PlanningContext:
        """组装统一上下文，供 run-agent / chat / council 三入口使用。"""
        ctx = PlanningContext(
            opportunity_id=opportunity_id,
            stage=stage,
            mode=mode,
            bundle=bundle,
        )

        if session is not None:
            ctx.current_object_summary = self._build_current_object_summary(session, stage)
            ctx.upstream_summary = self._build_upstream_summary(session, stage)
            ctx.downstream_completeness = self._check_downstream(session, stage)

        ctx.recent_council_consensuses = self._load_recent_consensuses(opportunity_id, limit=3)
        ctx.open_questions = self._load_open_questions(opportunity_id)
        ctx.scoring_shortfalls = self._load_scoring_shortfalls(opportunity_id, stage)
        ctx.project_memory_context = self._load_project_memory(opportunity_id)
        ctx.brand_preferences = self._load_brand_preferences(opportunity_id)

        return ctx

    def enrich_agent_context(
        self,
        agent_ctx: AgentContext,
        planning_ctx: PlanningContext,
    ) -> AgentContext:
        """将 PlanningContext 注入 AgentContext.extra，供 Agent 使用。"""
        agent_ctx.extra["planning_context"] = {
            "stage": planning_ctx.stage,
            "upstream_summary": planning_ctx.upstream_summary,
            "downstream_completeness": planning_ctx.downstream_completeness,
            "recent_council_consensuses": planning_ctx.recent_council_consensuses,
            "open_questions": planning_ctx.open_questions,
            "scoring_shortfalls": planning_ctx.scoring_shortfalls,
            "project_memory_context": planning_ctx.project_memory_context,
            "brand_preferences": planning_ctx.brand_preferences,
        }
        return agent_ctx

    def build_context_prompt_block(self, planning_ctx: PlanningContext) -> str:
        """将 PlanningContext 格式化为可嵌入 LLM prompt 的文本块。"""
        parts: list[str] = []

        if planning_ctx.current_object_summary:
            parts.append(f"【当前阶段对象】\n{planning_ctx.current_object_summary}")

        if planning_ctx.upstream_summary:
            parts.append(f"【上游阶段摘要】\n{planning_ctx.upstream_summary}")

        dc = planning_ctx.downstream_completeness
        if dc:
            items = [f"  {k}: {'已完成' if v else '待处理'}" for k, v in dc.items()]
            parts.append("【下游完成度】\n" + "\n".join(items))

        if planning_ctx.recent_council_consensuses:
            lines = [f"  - {c[:200]}" for c in planning_ctx.recent_council_consensuses]
            parts.append("【最近 Council 共识】\n" + "\n".join(lines))

        if planning_ctx.open_questions:
            lines = [f"  ? {q}" for q in planning_ctx.open_questions]
            parts.append("【待解决问题】\n" + "\n".join(lines))

        if planning_ctx.scoring_shortfalls:
            lines = [
                f"  - {s.get('dimension', '?')}: {s.get('score', '?')} ({s.get('note', '')})"
                for s in planning_ctx.scoring_shortfalls
            ]
            parts.append("【评分短板】\n" + "\n".join(lines))

        if planning_ctx.project_memory_context:
            parts.append(f"【项目级记忆】\n{planning_ctx.project_memory_context}")

        if planning_ctx.brand_preferences:
            parts.append(f"【品牌偏好】\n{planning_ctx.brand_preferences}")

        return "\n\n".join(parts) if parts else ""

    # ── Private helpers ──

    _STAGE_ORDER = ["opportunity", "brief", "template", "strategy", "plan", "visual", "asset"]

    def _build_current_object_summary(self, session: Any, stage: str) -> str:
        """Summarize the object at the current stage."""
        obj = self._get_stage_object(session, stage)
        if obj is None:
            return f"阶段 {stage} 尚无对象"
        return self._summarize_object(obj, stage)

    def _build_upstream_summary(self, session: Any, stage: str) -> str:
        """Build a summary of all upstream stage objects."""
        idx = self._stage_index(stage)
        parts: list[str] = []
        for i in range(idx):
            upstream_stage = self._STAGE_ORDER[i]
            obj = self._get_stage_object(session, upstream_stage)
            if obj is not None:
                parts.append(f"[{upstream_stage}] {self._summarize_object(obj, upstream_stage)[:200]}")
        return "\n".join(parts) if parts else ""

    def _check_downstream(self, session: Any, stage: str) -> dict[str, bool]:
        """Check which downstream stages have been completed."""
        idx = self._stage_index(stage)
        result: dict[str, bool] = {}
        for i in range(idx + 1, len(self._STAGE_ORDER)):
            ds = self._STAGE_ORDER[i]
            obj = self._get_stage_object(session, ds)
            result[ds] = obj is not None
        return result

    def _load_recent_consensuses(self, opportunity_id: str, limit: int = 3) -> list[str]:
        entries = self._memory.recall(
            opportunity_id=opportunity_id,
            category="discussion_consensus",
            limit=limit,
        )
        return [e.content for e in entries]

    def _load_open_questions(self, opportunity_id: str) -> list[str]:
        entries = self._memory.recall(
            opportunity_id=opportunity_id,
            category="open_question",
            limit=5,
        )
        return [e.content for e in entries]

    def _load_scoring_shortfalls(self, opportunity_id: str, stage: str) -> list[dict[str, Any]]:
        entries = self._memory.recall(
            opportunity_id=opportunity_id,
            category="scoring_shortfall",
            limit=5,
        )
        shortfalls: list[dict[str, Any]] = []
        for e in entries:
            shortfalls.append({
                "dimension": e.tags[0] if e.tags else "unknown",
                "score": e.relevance_score,
                "note": e.content[:200],
            })
        return shortfalls

    def _load_project_memory(self, opportunity_id: str) -> str:
        entries = self._memory.recall(
            opportunity_id=opportunity_id,
            category="project_consensus",
            limit=5,
        )
        if not entries:
            entries = self._memory.recall(
                opportunity_id=opportunity_id,
                category="council_opinion",
                limit=3,
            )
        if not entries:
            return ""
        return "\n".join(f"- {e.content[:200]}" for e in entries)

    def _load_brand_preferences(self, opportunity_id: str) -> str:
        entries = self._memory.recall(
            opportunity_id=opportunity_id,
            category="brand_preference",
            limit=5,
        )
        if not entries:
            return ""
        return "\n".join(f"- {e.content[:200]}" for e in entries)

    def _stage_index(self, stage: str) -> int:
        stage_lower = stage.lower()
        for i, s in enumerate(self._STAGE_ORDER):
            if s in stage_lower or stage_lower in s:
                return i
        return 0

    def _get_stage_object(self, session: Any, stage: str) -> Any:
        _map = {
            "opportunity": "card",
            "brief": "brief",
            "template": "match_result",
            "strategy": "strategy",
            "plan": "note_plan",
            "visual": "image_briefs",
            "asset": "asset_bundle",
        }
        attr = _map.get(stage, stage)
        return getattr(session, attr, None)

    def _summarize_object(self, obj: Any, stage: str) -> str:
        if obj is None:
            return "无"
        if isinstance(obj, dict):
            keys = list(obj.keys())[:8]
            return f"{stage} 对象含字段: {', '.join(keys)}"
        fields_to_show = ["opportunity_title", "content_goal", "target_user",
                          "positioning_statement", "theme", "template_name"]
        parts: list[str] = []
        for f in fields_to_show:
            v = getattr(obj, f, None)
            if v:
                parts.append(f"{f}={str(v)[:80]}")
        if parts:
            return "; ".join(parts)
        return f"{type(obj).__name__} 对象"
