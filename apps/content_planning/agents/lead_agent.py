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

    def run(self, context: AgentContext) -> AgentResult:
        """Analyze context and delegate to the best sub-agent."""
        user_message = context.extra.get("user_message", "")
        current_stage = context.extra.get("current_stage", "")
        hint = context.extra.get("hint", "")

        target_role = self._route(user_message or hint, current_stage, context)

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

        # Auto-extract memory from high-confidence results
        try:
            mem = AgentMemory()
            mem.extract_from_result(
                context.opportunity_id, target_role,
                result.explanation, result.confidence,
            )
        except Exception:
            pass

        return self._make_result(
            output_object=result.output_object,
            explanation=f"[{result.agent_name}] {result.explanation}",
            confidence=result.confidence,
            suggestions=result.suggestions + [
                AgentChip(label="换个角度分析", action="lead_agent", params={"hint": "换个角度"}),
            ],
        )

    def explain(self, result: AgentResult) -> str:
        return result.explanation

    def _route(self, message: str, stage: str, context: AgentContext) -> str:
        """Determine which sub-agent to delegate to."""
        if message:
            scores: dict[str, int] = {}
            msg_lower = message.lower()
            for role, keywords in _ROLE_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in msg_lower)
                if score > 0:
                    scores[role] = score
            if scores:
                return max(scores, key=scores.get)  # type: ignore[arg-type]

        # Try skill-based routing
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
