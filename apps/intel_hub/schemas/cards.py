from __future__ import annotations

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.enums import CardKind, ReviewDecisionSource, ReviewStatus


class IntelCard(BaseModel):
    id: str
    card_type: CardKind
    title: str
    summary: str = ""
    source_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    platform_refs: list[str] = Field(default_factory=list)
    timestamps: dict[str, str] = Field(default_factory=dict)
    confidence: float = 0.5
    evidence_refs: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING
    review_notes: str = ""
    reviewer: str | None = None
    reviewed_at: str | None = None
    review_decision_source: ReviewDecisionSource | None = None
    feedback_tags: list[str] = Field(default_factory=list)
    trigger_signals: list[str] = Field(default_factory=list)
    dedupe_key: str = ""
    merged_signal_ids: list[str] = Field(default_factory=list)
    merged_evidence_refs: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    impact_hint: str = ""
    business_priority_score: float = 0.0


class OpportunityCard(IntelCard):
    card_type: CardKind = CardKind.OPPORTUNITY


class RiskCard(IntelCard):
    card_type: CardKind = CardKind.RISK
