"""计划编译 Agent：在策略确认后编译 NewNotePlan。"""

from __future__ import annotations

import logging

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.content_planning.services.new_note_plan_compiler import NewNotePlanCompiler

logger = logging.getLogger(__name__)


class PlanCompilerAgent(BaseAgent):
    agent_id = "agent_plan_compiler"
    agent_name = "计划编译师"
    agent_role = "plan_compiler"

    def __init__(self) -> None:
        super().__init__()
        self._compiler = NewNotePlanCompiler()

    def run(self, context: AgentContext) -> AgentResult:
        base_result = self._run_core(context)
        if self.is_fast_mode(context):
            return base_result
        return self._enhance_with_llm(context, base_result)

    def _run_core(self, context: AgentContext) -> AgentResult:
        brief = context.brief
        strategy = context.strategy
        match_result = context.match_result
        template = context.template

        if not all([brief, strategy, match_result, template]):
            return self._make_result(
                explanation="缺少 Brief/策略/匹配结果/模板，无法编译内容计划",
                confidence=0.0,
            )

        plan = self._compiler.compile(brief, strategy, match_result, template)

        chips = [
            AgentChip(label="查看计划详情", action="navigate", params={"page": "plan"}),
            AgentChip(label="重新编译", action="recompile", params={}),
        ]

        section_count = len(getattr(plan, "sections", []))
        return self._make_result(
            output_object=plan,
            explanation=f"已编译内容计划，包含 {section_count} 个章节",
            confidence=0.75,
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

            system = "你是计划编译师。请评估以下内容计划的完整性和逻辑连贯性，给出优化建议。"
            user_msg = (
                f"计划编译结果：{base_result.explanation}\n"
                f"记忆上下文：{memory_ctx or '无'}"
            )

            resp = llm_router.chat([
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=user_msg),
            ], temperature=0.3, max_tokens=600)

            if resp.content:
                base_result.explanation = f"{base_result.explanation}\n\n💡 深度洞察：{resp.content}"
                base_result.confidence = min(base_result.confidence + 0.1, 1.0)
        except Exception:
            logger.debug("LLM enhancement failed for plan_compiler", exc_info=True)
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
