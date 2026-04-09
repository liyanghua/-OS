"""视觉总监 Agent：编排图位方案与图片执行指令。"""

from __future__ import annotations

import logging

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.content_planning.services.image_brief_generator import ImageBriefGenerator
from apps.content_planning.services.new_note_plan_compiler import NewNotePlanCompiler

logger = logging.getLogger(__name__)


class VisualDirectorAgent(BaseAgent):
    agent_id = "agent_visual_director"
    agent_name = "视觉总监"
    agent_role = "visual_director"

    def __init__(self) -> None:
        super().__init__()
        self._plan_compiler = NewNotePlanCompiler()
        self._image_gen = ImageBriefGenerator()

    def run(self, context: AgentContext) -> AgentResult:
        base_result = self._run_core(context)
        return self._enhance_with_llm(context, base_result)

    def _run_core(self, context: AgentContext) -> AgentResult:
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

    def _enhance_with_llm(self, context: AgentContext, base_result: AgentResult) -> AgentResult:
        if base_result.confidence <= 0.0:
            return base_result
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
            if not llm_router.is_any_available():
                return base_result

            memory_ctx = self._get_memory_context(context.opportunity_id)
            conversation = context.extra.get("conversation_history", "")

            system = "你是视觉总监。请分析以下图位方案，给出视觉一致性、场景感、广告感控制方面的建议。"
            user_msg = (
                f"图位方案：{base_result.explanation}\n"
                f"记忆上下文：{memory_ctx or '无'}\n"
                f"对话历史：{conversation or '无'}"
            )

            resp = llm_router.chat([
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=user_msg),
            ], temperature=0.3, max_tokens=800)

            if resp.content:
                base_result.explanation = f"{base_result.explanation}\n\n💡 深度洞察：{resp.content}"
                base_result.confidence = min(base_result.confidence + 0.1, 1.0)
        except Exception:
            logger.debug("LLM enhancement failed for visual_director", exc_info=True)
        return base_result

    def _get_memory_context(self, opportunity_id: str) -> str:
        try:
            from apps.content_planning.agents.memory import AgentMemory
            mem = AgentMemory()
            entries = mem.recall(opportunity_id=opportunity_id, limit=3)
            return "\n".join(f"- {e.content[:100]}" for e in entries) if entries else ""
        except Exception:
            return ""

    def explain(self, result: AgentResult) -> str:
        return result.explanation
