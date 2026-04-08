"""模板策划师 Agent：为 Brief 匹配最佳模板候选并解释理由。"""

from __future__ import annotations

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.template_extraction.agent import TemplateMatcher, TemplateRetriever


class TemplatePlannerAgent(BaseAgent):
    agent_id = "agent_template_planner"
    agent_name = "模板策划师"
    agent_role = "template_planner"

    def __init__(self) -> None:
        super().__init__()
        self._retriever = TemplateRetriever()

    def run(self, context: AgentContext) -> AgentResult:
        brief = context.brief
        if brief is None:
            return self._make_result(explanation="未提供 Brief，无法匹配模板", confidence=0.0)

        templates = self._retriever.list_templates()
        if not templates:
            return self._make_result(explanation="模板库为空", confidence=0.0)

        matcher = TemplateMatcher(templates)
        matches = matcher.match_templates(brief=brief, top_k=6)

        if not matches:
            return self._make_result(explanation="无匹配模板", confidence=0.1)

        top3 = matches[:3]
        chips = []
        for m in top3:
            chips.append(
                AgentChip(
                    label=f"选择「{m.template_name}」",
                    action="select_template",
                    params={"template_id": m.template_id},
                )
            )

        explanation_parts = [f"为 Brief 匹配了 {len(matches)} 套模板"]
        for i, m in enumerate(top3):
            explanation_parts.append(f"Top{i + 1}: {m.template_name}（{m.score:.0f}分）— {m.reason}")

        return self._make_result(
            output_object={
                "top3": [
                    {
                        "template_id": m.template_id,
                        "template_name": m.template_name,
                        "score": m.score,
                        "reason": m.reason,
                        "matched_dimensions": getattr(m, "matched_dimensions", None),
                    }
                    for m in top3
                ],
                "total": len(matches),
            },
            explanation="\n".join(explanation_parts),
            confidence=min(top3[0].score / 100, 1.0) if top3 else 0.0,
            suggestions=chips,
        )

    def explain(self, result: AgentResult) -> str:
        return result.explanation
