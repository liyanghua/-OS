"""Agent 基础设施：基类、上下文、结果。"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

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

    def _make_result(self, **kwargs: Any) -> AgentResult:
        return AgentResult(
            agent_role=self.agent_role,
            agent_name=self.agent_name,
            **kwargs,
        )
