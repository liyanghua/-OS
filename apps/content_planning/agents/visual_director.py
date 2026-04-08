"""视觉总监 Agent：编排图位方案与图片执行指令。"""

from __future__ import annotations

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.content_planning.services.image_brief_generator import ImageBriefGenerator
from apps.content_planning.services.new_note_plan_compiler import NewNotePlanCompiler


class VisualDirectorAgent(BaseAgent):
    agent_id = "agent_visual_director"
    agent_name = "视觉总监"
    agent_role = "visual_director"

    def __init__(self) -> None:
        super().__init__()
        self._plan_compiler = NewNotePlanCompiler()
        self._image_gen = ImageBriefGenerator()

    def run(self, context: AgentContext) -> AgentResult:
        plan = context.plan
        strategy = context.strategy

        if plan is None or strategy is None:
            return self._make_result(explanation="缺少 NotePlan 或策略，无法生成图位方案", confidence=0.0)

        image_result = self._image_gen.generate(plan, strategy)

        chips = []
        for sb in image_result.slot_briefs:
            chips.append(
                AgentChip(
                    label=f"重生成第{sb.slot_index}张",
                    action="regenerate_slot",
                    params={"slot_index": sb.slot_index},
                )
            )
        chips.extend(
            [
                AgentChip(label="更有场景感", action="hint_regen", params={"direction": "scene"}),
                AgentChip(label="更少广告感", action="hint_regen", params={"direction": "organic"}),
            ]
        )

        return self._make_result(
            output_object=image_result,
            explanation=f"已生成 {len(image_result.slot_briefs)} 张图位执行指令（模式：{image_result.mode}）",
            confidence=0.7,
            suggestions=chips,
        )

    def explain(self, result: AgentResult) -> str:
        return result.explanation
