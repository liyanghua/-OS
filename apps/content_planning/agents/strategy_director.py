"""策略总监 Agent：生成改写策略并支持多版本与局部重写。"""

from __future__ import annotations

import logging

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.content_planning.services.strategy_generator import RewriteStrategyGenerator

logger = logging.getLogger(__name__)


class StrategyDirectorAgent(BaseAgent):
    agent_id = "agent_strategy_director"
    agent_name = "策略总监"
    agent_role = "strategy_director"

    def __init__(self) -> None:
        super().__init__()
        self._generator = RewriteStrategyGenerator()

    def run(self, context: AgentContext) -> AgentResult:
        base_result = self._run_core(context)
        if self.is_fast_mode(context):
            return base_result
        return self._enhance_with_llm(context, base_result)

    def _run_core(self, context: AgentContext) -> AgentResult:
        brief = context.brief
        match_result = context.match_result
        template = context.template

        if not all([brief, match_result, template]):
            return self._make_result(explanation="缺少 Brief/匹配结果/模板，无法生成策略", confidence=0.0)

        if isinstance(match_result, dict):
            try:
                from apps.content_planning.schemas.template_match_result import (
                    TemplateMatchEntry,
                    TemplateMatchResult,
                )
                top3 = match_result.get("top3", [])
                entries = [TemplateMatchEntry(**e) for e in top3] if top3 else []
                match_result = TemplateMatchResult(
                    opportunity_id=context.opportunity_id,
                    brief_id=getattr(brief, "brief_id", ""),
                    primary_template=entries[0] if entries else TemplateMatchEntry(),
                    secondary_templates=entries[1:] if len(entries) > 1 else [],
                )
            except Exception:
                return self._make_result(explanation="匹配结果格式异常，无法生成策略", confidence=0.0)

        strategy = self._generator.generate(brief, match_result, template)

        chips = [
            AgentChip(label="更偏种草", action="regenerate", params={"tone_hint": "种草收藏"}),
            AgentChip(label="更偏转化", action="regenerate", params={"tone_hint": "转化"}),
            AgentChip(label="更适合礼赠", action="regenerate", params={"tone_hint": "礼赠"}),
            AgentChip(label="更平价改造", action="regenerate", params={"tone_hint": "平价改造"}),
        ]

        explanation_parts = [f"已生成策略 v{strategy.strategy_version}"]
        if strategy.comparison_note:
            explanation_parts.append(f"与规则版本差异：{strategy.comparison_note}")
        explanation_parts.append(f"定位：{strategy.positioning_statement}")

        return self._make_result(
            output_object=strategy,
            explanation="；".join(explanation_parts),
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
            conversation = context.extra.get("conversation_history", "")

            system = "你是策略总监。请评估以下改写策略，判断定位是否差异化、调性是否一致，并给出改进建议。"
            user_msg = (
                f"当前策略：{base_result.explanation}\n"
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
            logger.debug("LLM enhancement failed for strategy_director", exc_info=True)
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
