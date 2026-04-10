"""Agent 基础设施：基类、上下文、结果。"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Callable

from pydantic import BaseModel, Field


class AgentChip(BaseModel):
    """AI 建议快捷操作。"""

    label: str = ""
    action: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class AgentContext(BaseModel):
    """Agent 运行上下文。"""

    opportunity_id: str = ""
    brief: Any | None = None
    strategy: Any | None = None
    plan: Any | None = None
    match_result: Any | None = None
    template: Any | None = None
    titles: Any | None = None
    body: Any | None = None
    image_briefs: Any | None = None
    asset_bundle: Any | None = None
    source_notes: list[Any] = Field(default_factory=list)
    review_summary: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class RequestContextBundle(BaseModel):
    """Per-request shared context assembled once in routes and reused downstream."""

    card: Any | None = None
    source_notes: list[Any] = Field(default_factory=list)
    review_summary: dict[str, Any] = Field(default_factory=dict)
    template: Any | None = None
    memory_context: str = ""
    object_summary: str = ""


class AgentResult(BaseModel):
    """Agent 运行结果。"""

    result_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_role: str = ""
    agent_name: str = ""
    output_object: Any | None = None
    explanation: str = ""
    confidence: float = 0.5
    suggestions: list[AgentChip] = Field(default_factory=list)
    comparison_with_previous: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentMessage(BaseModel):
    """多轮对话中的单条消息。"""

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: str = "user"  # user / agent / system
    content: str = ""
    agent_role: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentThread(BaseModel):
    """Agent 多轮对话线程，绑定到 opportunity_id。"""

    thread_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    messages: list[AgentMessage] = Field(default_factory=list)
    active_agent: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_user_message(self, content: str, **meta: Any) -> AgentMessage:
        msg = AgentMessage(role="user", content=content, metadata=meta)
        self.messages.append(msg)
        return msg

    def add_agent_message(self, content: str, agent_role: str = "", **meta: Any) -> AgentMessage:
        msg = AgentMessage(role="agent", content=content, agent_role=agent_role, metadata=meta)
        self.messages.append(msg)
        return msg

    def recent(self, limit: int = 10) -> list[AgentMessage]:
        return self.messages[-limit:]

    def context_summary(self) -> str:
        """Build a text summary of recent conversation for LLM context."""
        lines = []
        for m in self.recent(8):
            prefix = "用户" if m.role == "user" else (m.agent_role or "Agent")
            lines.append(f"[{prefix}]: {m.content}")
        return "\n".join(lines)


class BaseAgent(ABC):
    """所有 Agent 的抽象基类。"""

    agent_id: str
    agent_name: str
    agent_role: str

    def __init__(self) -> None:
        if not hasattr(self, "agent_id"):
            self.agent_id = uuid.uuid4().hex[:12]

    @abstractmethod
    def run(self, context: AgentContext) -> AgentResult:
        ...

    @abstractmethod
    def explain(self, result: AgentResult) -> str:
        ...

    def run_turn(self, context: AgentContext, thread: AgentThread) -> AgentResult:
        """Multi-turn execution with conversation history.

        Default implementation adds conversation context to extra and delegates to run().
        Subclasses can override for richer multi-turn behavior.
        """
        context.extra["conversation_history"] = thread.context_summary()
        context.extra["turn_count"] = len([m for m in thread.messages if m.role == "user"])
        return self.run(context)

    def execution_mode(self, context: AgentContext) -> str:
        return str(
            context.extra.get("mode")
            or context.extra.get("execution_mode")
            or "deep"
        ).strip().lower()

    def is_fast_mode(self, context: AgentContext) -> bool:
        return self.execution_mode(context) == "fast"

    def request_context_bundle(self, context: AgentContext) -> RequestContextBundle | None:
        raw = context.extra.get("request_context_bundle")
        if raw is None:
            return None
        if isinstance(raw, RequestContextBundle):
            return raw
        if isinstance(raw, dict):
            try:
                return RequestContextBundle.model_validate(raw)
            except Exception:
                return None
        return None

    def resolve_memory_context(
        self,
        context: AgentContext,
        *,
        fallback: Callable[[], str] | None = None,
    ) -> str:
        bundle = self.request_context_bundle(context)
        if bundle is not None and bundle.memory_context:
            return bundle.memory_context
        if fallback is not None:
            return fallback()
        return ""

    def resolve_object_summary(
        self,
        context: AgentContext,
        *,
        fallback: Callable[[], str] | None = None,
    ) -> str:
        bundle = self.request_context_bundle(context)
        if bundle is not None and bundle.object_summary:
            return bundle.object_summary
        if fallback is not None:
            return fallback()
        return ""

    def _make_result(self, **kwargs: Any) -> AgentResult:
        return AgentResult(
            agent_role=self.agent_role,
            agent_name=self.agent_name,
            **kwargs,
        )
