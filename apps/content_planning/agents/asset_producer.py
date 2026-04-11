"""资产制作人 Agent：生成标题/正文/资产包。"""

from __future__ import annotations

import logging

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.content_planning.services.asset_assembler import AssetAssembler
from apps.content_planning.services.body_generator import BodyGenerator
from apps.content_planning.services.title_generator import TitleGenerator

logger = logging.getLogger(__name__)


class AssetProducerAgent(BaseAgent):
    agent_id = "agent_asset_producer"
    agent_name = "资产制作人"
    agent_role = "asset_producer"

    def __init__(self) -> None:
        super().__init__()
        self._title_gen = TitleGenerator()
        self._body_gen = BodyGenerator()

    def run(self, context: AgentContext) -> AgentResult:
        base_result = self._run_core(context)
        if self.is_fast_mode(context):
            return base_result
        return self._enhance_with_llm(context, base_result)

    def _ensure_prerequisites(self, context: AgentContext) -> tuple:
        """Try to load plan/strategy from flow if not present in context."""
        plan = context.plan
        strategy = context.strategy
        if plan is not None and strategy is not None:
            return plan, strategy
        try:
            from apps.content_planning.api.routes import _get_flow
            flow = _get_flow()
            session = flow._get_session(context.opportunity_id)
            if strategy is None and session.strategy is not None:
                strategy = session.strategy
            if plan is None and session.note_plan is not None:
                plan = session.note_plan
            if strategy is None:
                strategy = flow.build_strategy(context.opportunity_id)
            if plan is None:
                plan = flow.build_plan(context.opportunity_id)
        except Exception:
            logger.debug("Failed to auto-load plan/strategy for asset_producer", exc_info=True)
        return plan, strategy

    def _run_core(self, context: AgentContext) -> AgentResult:
        plan, strategy = self._ensure_prerequisites(context)

        if plan is None or strategy is None:
            missing = []
            if plan is None:
                missing.append("NotePlan")
            if strategy is None:
                missing.append("策略")
            return self._make_result(
                explanation=f"缺少 {' 和 '.join(missing)}，请先完成上游策划流程（Brief → 模板匹配 → 策略 → 计划）后再运行资产制作人。",
                confidence=0.0,
                suggestions=[
                    AgentChip(label="编译 Brief", action="brief_synthesizer"),
                    AgentChip(label="生成策略", action="strategy_director"),
                ],
            )

        titles = self._title_gen.generate(plan, strategy)
        body = self._body_gen.generate(plan, strategy)

        bundle = AssetAssembler.assemble(
            opportunity_id=context.opportunity_id,
            plan_id=getattr(plan, "plan_id", ""),
            titles=titles,
            body=body,
            image_briefs=context.image_briefs,
        )

        chips = [
            AgentChip(label="重生成标题", action="regenerate_titles", params={}),
            AgentChip(label="重生成正文", action="regenerate_body", params={}),
            AgentChip(label="更像原生", action="hint_regen", params={"style": "native"}),
            AgentChip(label="更强钩子", action="hint_regen", params={"style": "hook"}),
        ]

        title_count = len(titles.titles)
        body_len = len(body.body_draft)

        return self._make_result(
            output_object=bundle,
            explanation=f"已生成 {title_count} 条标题候选 + {body_len}字正文草稿，资产包状态：{bundle.export_status}",
            confidence=0.7 if bundle.export_status == "ready" else 0.4,
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

            system = "你是资产制作人。请评估以下资产包产出，分析标题吸引力、正文结构完整性，并给出优化建议。"
            user_msg = (
                f"资产包：{base_result.explanation}\n"
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
            logger.debug("LLM enhancement failed for asset_producer", exc_info=True)
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
