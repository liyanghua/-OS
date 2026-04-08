"""趋势分析师 Agent：扫描机会池，标注高优先级机会。"""

from __future__ import annotations

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent


class TrendAnalystAgent(BaseAgent):
    agent_id = "agent_trend_analyst"
    agent_name = "趋势分析师"
    agent_role = "trend_analyst"

    def run(self, context: AgentContext) -> AgentResult:
        card = context.extra.get("card")
        if card is None:
            return self._make_result(explanation="未找到机会卡", confidence=0.0)

        strength = getattr(card, "opportunity_strength_score", None) or 0.0
        action_rec = getattr(card, "action_recommendation", None) or ""
        insight = getattr(card, "insight_statement", None) or ""

        chips: list[AgentChip] = []
        if strength >= 0.7:
            chips.append(AgentChip(label="值得深入", action="promote", params={"priority": "high"}))
        elif strength >= 0.5:
            chips.append(AgentChip(label="建议观望", action="watch", params={}))
        else:
            chips.append(AgentChip(label="优先级低", action="skip", params={}))

        opp_type = getattr(card, "opportunity_type", "")
        if opp_type in ("visual", "scene"):
            chips.append(AgentChip(label="适合种草", action="hint", params={"goal": "种草收藏"}))
        elif opp_type in ("demand", "product"):
            chips.append(AgentChip(label="适合转化", action="hint", params={"goal": "转化"}))

        explanation_parts = []
        if insight:
            explanation_parts.append(f"洞察：{insight}")
        if action_rec:
            explanation_parts.append(f"建议：{action_rec}")
        explanation_parts.append(f"综合强度分：{strength:.2f}")

        return self._make_result(
            output_object=card,
            explanation="；".join(explanation_parts),
            confidence=min(strength + 0.1, 1.0),
            suggestions=chips,
        )

    def explain(self, result: AgentResult) -> str:
        return result.explanation
