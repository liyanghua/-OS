"""Agent Middleware Chain: DeerFlow-inspired pre/post processing pipeline.

Each middleware wraps Agent execution, processing state before and after.
Middleware runs in a fixed order: Guardrail -> Summarization -> Memory ->
Lifecycle -> Persist.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Callable

from apps.content_planning.agents.base import AgentContext, AgentResult

logger = logging.getLogger(__name__)


class BaseMiddleware(ABC):
    """Base class for all middleware in the Agent execution pipeline."""

    name: str = "base"
    enabled: bool = True

    @abstractmethod
    def before(self, context: AgentContext, agent_role: str) -> AgentContext:
        """Pre-processing: modify context before Agent runs."""
        return context

    @abstractmethod
    def after(self, context: AgentContext, result: AgentResult, agent_role: str) -> AgentResult:
        """Post-processing: modify result after Agent runs."""
        return result

    def should_run(self, context: AgentContext) -> bool:
        return self.enabled


class GuardrailMiddleware(BaseMiddleware):
    """Check content against brand guardrails before and after Agent execution."""

    name = "guardrail"

    def before(self, context: AgentContext, agent_role: str) -> AgentContext:
        return context

    def after(self, context: AgentContext, result: AgentResult, agent_role: str) -> AgentResult:
        if result.output_object is None:
            return result
        try:
            from apps.content_planning.services.guardrail_checker import GuardrailChecker
            checker = GuardrailChecker()
            text_to_check = result.explanation
            if hasattr(result.output_object, "positioning_statement"):
                text_to_check += " " + getattr(result.output_object, "positioning_statement", "")
            brand_id = context.extra.get("brand_id", "")
            if brand_id and text_to_check.strip():
                violations = checker.check(text_to_check, brand_id=brand_id)
                if violations:
                    result.explanation += f"\n⚠️ Guardrail 警告: {len(violations)} 项违规"
                    result.confidence = max(result.confidence - 0.1, 0.0)
        except Exception:
            logger.debug("GuardrailMiddleware check failed", exc_info=True)
        return result


class SummarizationMiddleware(BaseMiddleware):
    """Auto-summarize long context to prevent token overflow."""

    name = "summarization"
    max_context_chars: int = 8000

    def before(self, context: AgentContext, agent_role: str) -> AgentContext:
        total_chars = self._estimate_context_size(context)
        if total_chars > self.max_context_chars:
            context.middleware_log.append(f"summarization: compressed {total_chars} -> ~{self.max_context_chars} chars")
            if context.source_notes and len(context.source_notes) > 3:
                context.source_notes = context.source_notes[:3]
        return context

    def after(self, context: AgentContext, result: AgentResult, agent_role: str) -> AgentResult:
        return result

    def _estimate_context_size(self, context: AgentContext) -> int:
        size = 0
        for note in context.source_notes:
            size += len(str(note))
        size += len(str(context.review_summary))
        size += len(str(context.extra))
        return size


class MemoryMiddleware(BaseMiddleware):
    """Auto-extract and inject memory around Agent execution."""

    name = "memory"

    def before(self, context: AgentContext, agent_role: str) -> AgentContext:
        try:
            from apps.content_planning.agents.memory import AgentMemory
            mem = AgentMemory()
            memory_ctx = mem.inject_context(context.opportunity_id, agent_role, limit=3)
            if memory_ctx:
                context.extra.setdefault("memory_context", memory_ctx)
        except Exception:
            logger.debug("MemoryMiddleware inject failed", exc_info=True)
        return context

    def after(self, context: AgentContext, result: AgentResult, agent_role: str) -> AgentResult:
        if context.config.get("execution_mode") == "fast":
            return result
        try:
            from apps.content_planning.agents.memory import AgentMemory
            mem = AgentMemory()
            mem.extract_from_result(
                context.opportunity_id, agent_role,
                result.explanation, result.confidence,
            )
        except Exception:
            logger.debug("MemoryMiddleware extract failed", exc_info=True)
        return result


class LifecycleMiddleware(BaseMiddleware):
    """Push lifecycle_status forward as Agents complete stages."""

    name = "lifecycle"

    _ROLE_TO_STATUS: dict[str, str] = {
        "brief_synthesizer": "in_planning",
        "strategy_director": "in_planning",
        "plan_compiler": "in_planning",
        "asset_producer": "ready",
    }

    def before(self, context: AgentContext, agent_role: str) -> AgentContext:
        return context

    def after(self, context: AgentContext, result: AgentResult, agent_role: str) -> AgentResult:
        target_status = self._ROLE_TO_STATUS.get(agent_role)
        if target_status is None or result.output_object is None:
            return result
        obj = result.output_object
        if hasattr(obj, "lifecycle_status"):
            obj.lifecycle_status = target_status
            context.middleware_log.append(f"lifecycle: {agent_role} -> {target_status}")
        return result


class PersistMiddleware(BaseMiddleware):
    """Persist session state after each Agent step."""

    name = "persist"

    def __init__(self, plan_store: Any = None) -> None:
        self._store = plan_store

    def before(self, context: AgentContext, agent_role: str) -> AgentContext:
        return context

    def after(self, context: AgentContext, result: AgentResult, agent_role: str) -> AgentResult:
        if self._store is None:
            return result
        try:
            self._store.save_session(
                context.opportunity_id,
                session_status="agent_middleware",
                brief=context.brief,
                match_result=context.match_result,
                strategy=context.strategy,
                plan=context.plan,
                image_briefs=context.image_briefs,
                asset_bundle=context.asset_bundle,
                pipeline_run_id=context.run_id,
            )
            context.middleware_log.append(f"persist: saved after {agent_role}")
        except Exception:
            logger.debug("PersistMiddleware save failed", exc_info=True)
        return result


class MiddlewareChain:
    """Ordered middleware chain that wraps Agent execution."""

    def __init__(self, middlewares: list[BaseMiddleware] | None = None) -> None:
        self._middlewares = middlewares or []

    def add(self, middleware: BaseMiddleware) -> None:
        self._middlewares.append(middleware)

    def execute(
        self,
        context: AgentContext,
        agent_role: str,
        agent_fn: Callable[[AgentContext], AgentResult],
    ) -> AgentResult:
        """Run the middleware chain around agent_fn."""
        for mw in self._middlewares:
            if mw.should_run(context):
                context = mw.before(context, agent_role)

        result = agent_fn(context)

        for mw in reversed(self._middlewares):
            if mw.should_run(context):
                result = mw.after(context, result, agent_role)

        return result

    async def aexecute(
        self,
        context: AgentContext,
        agent_role: str,
        agent_fn: Callable[[AgentContext], AgentResult],
    ) -> AgentResult:
        """Async version -- middleware itself is sync, but wraps an agent that may be sync."""
        for mw in self._middlewares:
            if mw.should_run(context):
                context = mw.before(context, agent_role)

        result = agent_fn(context)

        for mw in reversed(self._middlewares):
            if mw.should_run(context):
                result = mw.after(context, result, agent_role)

        return result

    @classmethod
    def default_chain(cls, *, plan_store: Any = None) -> MiddlewareChain:
        """Build the standard middleware chain."""
        return cls([
            GuardrailMiddleware(),
            SummarizationMiddleware(),
            MemoryMiddleware(),
            LifecycleMiddleware(),
            PersistMiddleware(plan_store=plan_store),
        ])
