"""模板策划师 Agent：为 Brief 匹配最佳模板候选并解释理由。"""

from __future__ import annotations

import logging

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.template_extraction.agent import TemplateMatcher, TemplateRetriever

logger = logging.getLogger(__name__)


class TemplatePlannerAgent(BaseAgent):
    agent_id = "agent_template_planner"
    agent_name = "模板策划师"
    agent_role = "template_planner"

    def __init__(self) -> None:
        super().__init__()
        self._retriever = TemplateRetriever()

    def run(self, context: AgentContext) -> AgentResult:
        base_result = self._run_core(context)
        if self.is_fast_mode(context):
            return base_result
        return self._enhance_with_llm(context, base_result)

    def _run_core(self, context: AgentContext) -> AgentResult:
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

            system = "你是模板策划师。请分析以下模板匹配结果，解释为何这些模板适合当前 Brief，并给出使用建议。"
            user_msg = (
                f"匹配结果：{base_result.explanation}\n"
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
            logger.debug("LLM enhancement failed for template_planner", exc_info=True)
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
