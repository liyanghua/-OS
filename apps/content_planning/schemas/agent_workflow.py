"""Agent workflow schemas for staged councils, proposals, and evaluations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Applyability = Literal["direct", "partial", "none"]
CouncilUiDecision = Literal["advisory", "conflicted", "insufficient_context", "applyable"]

from apps.content_planning.schemas.evaluation import DimensionScore

WorkflowStage = Literal["brief", "strategy", "plan", "asset"]
RunMode = Literal["baseline_compiler", "agent_assisted_single", "agent_assisted_council"]
RunStatus = Literal["queued", "running", "completed", "failed", "waiting_human"]
ProposalStatus = Literal["proposed", "applied", "rejected", "blocked"]
DecisionType = Literal["applied", "rejected", "partial_apply"]


class AgentSessionRef(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentTask(BaseModel):
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    stage: WorkflowStage = "brief"
    run_mode: RunMode = "agent_assisted_council"
    task_type: str = "stage_discussion"
    status: RunStatus = "queued"
    session_ref: AgentSessionRef | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentRun(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_id: str = ""
    opportunity_id: str = ""
    stage: WorkflowStage = "brief"
    run_mode: RunMode = "agent_assisted_council"
    status: RunStatus = "queued"
    participant_roles: list[str] = Field(default_factory=list)
    summary: str = ""
    error: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProposalFieldChange(BaseModel):
    field: str = ""
    before: Any = None
    after: Any = None
    blocked: bool = False
    change_type: str = "modify"
    confidence: float = 0.0
    reason: str = ""


class ProposalDiff(BaseModel):
    changes: list[ProposalFieldChange] = Field(default_factory=list)


class StageProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    stage: WorkflowStage = "brief"
    target_object_type: str = ""
    target_object_id: str = ""
    base_version: int = 1
    run_mode: RunMode = "agent_assisted_council"
    summary: str = ""
    proposed_updates: dict[str, Any] = Field(default_factory=dict)
    diff: ProposalDiff = Field(default_factory=ProposalDiff)
    blocked_fields: list[str] = Field(default_factory=list)
    requires_human_confirmation: bool = True
    confidence: float = 0.0
    source_run_id: str = ""
    source_discussion_id: str = ""
    status: ProposalStatus = "proposed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Council Advisory Session 扩展
    council_decision_type: CouncilUiDecision | str = ""
    applyability: Applyability | str = "none"
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    model_decision_hint: str = ""
    target_sub_object_type: str = ""  # brief | strategy | plan | asset，预留跨子对象 Council
    follow_up_of_discussion_id: str = ""
    session_id: str = ""
    consensus_text: str = ""
    fallback_action: dict[str, Any] = Field(default_factory=dict)
    guardrail_warnings: list[str] = Field(default_factory=list)
    blocked_by_guardrail: bool = False
    brand_fit_score: float = 1.0


class ProposalDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    proposal_id: str = ""
    decision: DecisionType = "applied"
    actor_user_id: str = ""
    selected_fields: list[str] = Field(default_factory=list)
    skipped_fields: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentDiscussionRecord(BaseModel):
    discussion_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    stage: WorkflowStage = "brief"
    question: str = ""
    participants: list[str] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    proposal_id: str = ""
    run_id: str = ""
    base_version: int = 1
    status: RunStatus = "completed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    council_decision_type: str = ""
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    follow_up_of_discussion_id: str = ""
    target_sub_object_type: str = ""
    consensus: str = ""
    executive_summary: str = ""
    disagreements_structured: list[dict[str, Any]] = Field(default_factory=list)
    recommended_next_steps_items: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0


class StageScorecard(BaseModel):
    scorecard_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    stage: WorkflowStage = "brief"
    run_mode: RunMode = "agent_assisted_council"
    base_version: int = 1
    overall_score: float = 0.0
    dimensions: list[DimensionScore] = Field(default_factory=list)
    evaluator: str = "rule"
    model_used: str = ""
    explanation: str = ""
    rubric_version: str = ""
    pipeline_run_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
