"""Council v2：会话对象、可观测性与结构化分歧（对齐 docs/council_upgrade_v2.md）。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CouncilParticipantRole = Literal["specialist", "synthesizer", "lead"]


class CouncilParticipantSpec(BaseModel):
    """Council 参与者（元数据，非单条发言）。"""

    agent_id: str = ""
    display_name: str = ""
    role_type: CouncilParticipantRole | str = "specialist"


class CouncilSession(BaseModel):
    """顶层 Council 会话对象（与 HTTP 返回 `session` 对齐）。"""

    session_id: str = ""
    stage_type: str = ""
    target_object_type: str = ""
    target_object_id: str = ""
    target_object_version: int | str = 1
    opportunity_id: str = ""
    question: str = ""
    run_mode: str = "agent_assisted_council"
    participants: list[CouncilParticipantSpec] = Field(default_factory=list)
    status: str = "completed"
    decision_type: str = ""
    applyability: str = "none"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    timing_ms: int = 0
    timing_breakdown: dict[str, int] = Field(default_factory=dict)


class CouncilAgentObs(BaseModel):
    """单个 specialist 可观测性。"""

    agent_id: str = ""
    used_llm: bool = False
    degraded: bool = False
    model: str = ""
    timing_ms: int = 0
    output_quality: str = "ok"


class CouncilSynthesisObs(BaseModel):
    """综合阶段可观测性。"""

    used_llm: bool = False
    degraded: bool = False
    timing_ms: int = 0
    output_quality: str = "ok"


class CouncilModelSummary(BaseModel):
    specialist_model: str = ""
    synthesis_model: str = ""
    llm_available: bool = False


class CouncilObservability(BaseModel):
    """HTTP 返回 observability 块。"""

    trace_id: str = ""
    session_id: str = ""
    model_summary: CouncilModelSummary = Field(default_factory=CouncilModelSummary)
    agents: list[CouncilAgentObs] = Field(default_factory=list)
    synthesis: CouncilSynthesisObs = Field(default_factory=CouncilSynthesisObs)


class DisagreementStructured(BaseModel):
    """结构化分歧（可选 agents 维度）。"""

    topic: str = ""
    agents_for: list[str] = Field(default_factory=list)
    agents_against: list[str] = Field(default_factory=list)
    reason_summary: str = ""


class RecommendedStepItem(BaseModel):
    """强类型下一步建议。"""

    action_type: str = "note"  # apply_as_draft | turn_into_variant | ask_follow_up | note
    label: str = ""
    target_field: str = ""


class ProposalFallbackAction(BaseModel):
    """无严格 diff 时的回退动作提示。"""

    type: str = "apply_as_draft"
    target_field: str = ""
    content: str = ""


def new_alternative_id() -> str:
    return f"alt_{uuid.uuid4().hex[:10]}"

