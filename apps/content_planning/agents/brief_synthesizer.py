"""Brief 编译师 Agent：把机会卡编译成策划友好的 Brief。"""

from __future__ import annotations

import logging

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.content_planning.services.brief_compiler import BriefCompiler

logger = logging.getLogger(__name__)


class BriefSynthesizerAgent(BaseAgent):
    agent_id = "agent_brief_synthesizer"
    agent_name = "Brief 编译师"
    agent_role = "brief_synthesizer"

    def __init__(self) -> None:
        super().__init__()
        self._compiler = BriefCompiler()

    def run(self, context: AgentContext) -> AgentResult:
        base_result = self._run_core(context)
        if self.is_fast_mode(context):
            return base_result
        return self._enhance_with_llm(context, base_result)

    def _run_core(self, context: AgentContext) -> AgentResult:
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

    def _enhance_with_llm(self, context: AgentContext, base_result: AgentResult) -> AgentResult:
        if base_result.confidence <= 0.0:
            return base_result
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
            if not llm_router.is_any_available():
                return base_result

            memory_ctx = self.resolve_memory_context(
                context,
                fallback=lambda: self._get_memory_context(context.opportunity_id),
            )
            conversation = context.extra.get("conversation_history", "")

            system = "你是 Brief 编译师。请审核以下 Brief 编译结果，给出优化建议：用户定位是否精准、策划方向是否有差异化。"
            user_msg = (
                f"当前 Brief：{base_result.explanation}\n"
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
            logger.debug("LLM enhancement failed for brief_synthesizer", exc_info=True)
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
