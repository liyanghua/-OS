"""Lead Agent：总调度，接收人类意图，委派 Sub-Agent，汇总结果。

借鉴 DeerFlow 的 Lead Agent + Sub-Agent 委派模式。
"""

from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.agents.base import (
    AgentChip,
    AgentContext,
    AgentResult,
    BaseAgent,
)
from apps.content_planning.agents.memory import AgentMemory
from apps.content_planning.agents.skill_registry import skill_registry

logger = logging.getLogger(__name__)

_ROLE_KEYWORDS: dict[str, list[str]] = {
    "trend_analyst": ["趋势", "分析", "机会", "竞品", "观望", "深入", "值得"],
    "brief_synthesizer": ["brief", "摘要", "方向", "种草", "转化", "目标", "定位"],
    "template_planner": ["模板", "匹配", "风格", "换个", "template"],
    "strategy_director": ["策略", "改写", "调性", "偏", "更", "钩子", "标题"],
    "visual_director": ["图片", "视觉", "场景", "桌布", "封面", "广告感", "图位"],
    "asset_producer": ["资产", "导出", "变体", "发布", "asset", "打包"],
}

_STAGE_AGENT_MAP: dict[str, str] = {
    "opportunity": "trend_analyst",
    "brief": "brief_synthesizer",
    "template": "template_planner",
    "strategy": "strategy_director",
    "plan": "visual_director",
    "asset": "asset_producer",
}


class LeadAgent(BaseAgent):
    """总调度 Agent：理解人类意图 → 选择最佳 Sub-Agent → 委派执行。"""

    agent_id = "lead_agent_001"
    agent_name = "总调度"
    agent_role = "lead_agent"

    def __init__(self) -> None:
        super().__init__()
        from apps.content_planning.adapters.deerflow_adapter import DeerFlowAdapter
        self._deerflow = DeerFlowAdapter()

    def run(self, context: AgentContext) -> AgentResult:
        """Analyze context and delegate to the best sub-agent."""
        user_message = context.extra.get("user_message", "")
        current_stage = context.extra.get("current_stage", "")
        hint = context.extra.get("hint", "")

        routing = self._route(user_message or hint, current_stage, context)
        target_role = routing["target"]
        extra_agents = routing.get("extra_agents", [])

        sub_agent = self._instantiate(target_role)
        if sub_agent is None:
            return self._make_result(
                explanation=f"无法确定合适的 Agent 角色来处理: {user_message or hint or current_stage}",
                confidence=0.2,
                suggestions=[
                    AgentChip(label="趋势分析", action="trend_analyst"),
                    AgentChip(label="Brief 编译", action="brief_synthesizer"),
                    AgentChip(label="模板匹配", action="template_planner"),
                    AgentChip(label="策略生成", action="strategy_director"),
                    AgentChip(label="图片规划", action="visual_director"),
                    AgentChip(label="资产组包", action="asset_producer"),
                ],
            )

        result = sub_agent.run(context)

        try:
            mem = AgentMemory()
            mem.extract_from_result(
                context.opportunity_id, target_role,
                result.explanation, result.confidence,
            )
        except Exception:
            pass

        suggestions = list(result.suggestions)
        for extra_role in extra_agents:
            from apps.content_planning.adapters.deerflow_adapter import AGENT_DESCRIPTIONS
            label = AGENT_DESCRIPTIONS.get(extra_role, extra_role)
            suggestions.append(AgentChip(
                label=f"也问问 {label.split('：')[0]}" if "：" in label else f"也问问 {extra_role}",
                action=extra_role,
            ))
        suggestions.append(
            AgentChip(label="换个角度分析", action="lead_agent", params={"hint": "换个角度"}),
        )

        explanation = f"[{result.agent_name}] {result.explanation}"
        if routing.get("reasoning"):
            explanation = f"{explanation}\n调度理由：{routing['reasoning']}"

        return self._make_result(
            output_object=result.output_object,
            explanation=explanation,
            confidence=result.confidence,
            suggestions=suggestions,
        )

    def explain(self, result: AgentResult) -> str:
        return result.explanation

    def _route_llm(self, message: str, stage: str, context: AgentContext) -> dict | None:
        """LLM-driven routing via DeerFlowAdapter."""
        try:
            from apps.content_planning.adapters.llm_router import llm_router
            if not llm_router.is_any_available():
                return None

            memory_ctx = self._deerflow.recall_relevant_memory(
                context.opportunity_id, query=message,
            )
            object_summary = self._deerflow.build_object_summary(context)

            resp = self._deerflow.route_with_llm(
                user_message=message,
                stage=stage,
                memory_context=memory_ctx,
                object_summary=object_summary,
            )

            agents = resp.get("target_agents", [])
            if not agents:
                return None

            valid_roles = set(_ROLE_KEYWORDS.keys())
            agents = [a for a in agents if a in valid_roles]
            if not agents:
                return None

            return {
                "target": agents[0],
                "extra_agents": agents[1:],
                "reasoning": resp.get("reasoning", ""),
                "method": "llm",
            }
        except Exception:
            logger.debug("LLM routing failed, will use keyword fallback", exc_info=True)
            return None

    def _route_keyword(self, message: str, stage: str, context: AgentContext) -> str:
        """Keyword-based routing (original logic)."""
        if message:
            scores: dict[str, int] = {}
            msg_lower = message.lower()
            for role, keywords in _ROLE_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in msg_lower)
                if score > 0:
                    scores[role] = score
            if scores:
                return max(scores, key=scores.get)  # type: ignore[arg-type]

        if message:
            matched_skills = skill_registry.find_by_keyword(message)
            if matched_skills:
                return matched_skills[0].agent_role

        if stage and stage in _STAGE_AGENT_MAP:
            return _STAGE_AGENT_MAP[stage]

        if context.asset_bundle:
            return "asset_producer"
        if context.plan:
            return "visual_director"
        if context.strategy:
            return "strategy_director"
        if context.match_result:
            return "template_planner"
        if context.brief:
            return "brief_synthesizer"
        return "trend_analyst"

    def _route(self, message: str, stage: str, context: AgentContext) -> dict:
        """Route using LLM first, falling back to keyword matching."""
        if message:
            llm_result = self._route_llm(message, stage, context)
            if llm_result:
                logger.info("Routing via LLM → %s", llm_result["target"])
                return llm_result

        keyword_target = self._route_keyword(message, stage, context)
        logger.info("Routing via keywords → %s", keyword_target)
        return {"target": keyword_target, "extra_agents": [], "reasoning": "", "method": "keyword"}

    def _instantiate(self, role: str) -> BaseAgent | None:
        """Lazy-instantiate a sub-agent by role."""
        try:
            if role == "trend_analyst":
                from apps.content_planning.agents.trend_analyst import TrendAnalystAgent
                return TrendAnalystAgent()
            elif role == "brief_synthesizer":
                from apps.content_planning.agents.brief_synthesizer import BriefSynthesizerAgent
                return BriefSynthesizerAgent()
            elif role == "template_planner":
                from apps.content_planning.agents.template_planner import TemplatePlannerAgent
                return TemplatePlannerAgent()
            elif role == "strategy_director":
                from apps.content_planning.agents.strategy_director import StrategyDirectorAgent
                return StrategyDirectorAgent()
            elif role == "visual_director":
                from apps.content_planning.agents.visual_director import VisualDirectorAgent
                return VisualDirectorAgent()
            elif role == "asset_producer":
                from apps.content_planning.agents.asset_producer import AssetProducerAgent
                return AssetProducerAgent()
        except Exception:
            logger.exception("Failed to instantiate agent: %s", role)
        return None
