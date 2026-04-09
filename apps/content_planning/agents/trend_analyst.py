"""趋势分析师 Agent：扫描机会池，标注高优先级机会。"""

from __future__ import annotations

import logging

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent

logger = logging.getLogger(__name__)


class TrendAnalystAgent(BaseAgent):
    agent_id = "agent_trend_analyst"
    agent_name = "趋势分析师"
    agent_role = "trend_analyst"

    def run(self, context: AgentContext) -> AgentResult:
        base_result = self._run_core(context)
        return self._enhance_with_llm(context, base_result)

    def _run_core(self, context: AgentContext) -> AgentResult:
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

    def _enhance_with_llm(self, context: AgentContext, base_result: AgentResult) -> AgentResult:
        if base_result.confidence <= 0.0:
            return base_result
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
            if not llm_router.is_any_available():
                return base_result

            memory_ctx = self._get_memory_context(context.opportunity_id)
            conversation = context.extra.get("conversation_history", "")

            card = context.extra.get("card")
            card_info = ""
            if card:
                card_info = f"机会类型: {getattr(card, 'opportunity_type', '未知')}, " \
                            f"强度分: {getattr(card, 'opportunity_strength_score', 0)}"

            system = "你是趋势分析师。请基于以下初步分析和机会卡信息，提供更深入的市场趋势洞察和竞品对比分析。"
            user_msg = (
                f"初步分析：{base_result.explanation}\n"
                f"机会卡信息：{card_info}\n"
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
            logger.debug("LLM enhancement failed for trend_analyst", exc_info=True)
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
