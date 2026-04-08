"""Brief 编译师 Agent：把机会卡编译成策划友好的 Brief。"""

from __future__ import annotations

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.content_planning.services.brief_compiler import BriefCompiler


class BriefSynthesizerAgent(BaseAgent):
    agent_id = "agent_brief_synthesizer"
    agent_name = "Brief 编译师"
    agent_role = "brief_synthesizer"

    def __init__(self) -> None:
        super().__init__()
        self._compiler = BriefCompiler()

    def run(self, context: AgentContext) -> AgentResult:
        card = context.extra.get("card")
        if card is None:
            return self._make_result(explanation="未找到机会卡，无法编译 Brief", confidence=0.0)

        parsed_note = context.source_notes[0] if context.source_notes else None
        review_summary = context.review_summary or None

        brief = self._compiler.compile(card, parsed_note, review_summary)

        chips = [AgentChip(label="进入策划", action="navigate", params={"page": "planning"})]
        if brief.why_now:
            chips.append(AgentChip(label="查看时机分析", action="scroll", params={"field": "why_now"}))

        explanation_parts = [f"已为机会「{brief.opportunity_title}」编译 Brief"]
        if brief.planning_direction:
            explanation_parts.append(f"策划方向：{brief.planning_direction}")
        if brief.why_now:
            explanation_parts.append(f"时机判断：{brief.why_now}")

        return self._make_result(
            output_object=brief,
            explanation="；".join(explanation_parts),
            confidence=0.8,
            suggestions=chips,
        )

    def explain(self, result: AgentResult) -> str:
        return result.explanation
