from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.enums import CardKind, InsightType, OpportunityType, ReviewDecisionSource, ReviewStatus, RiskType, TargetRole


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
    target_roles: list[str] = Field(default_factory=list)


class OpportunityCard(IntelCard):
    card_type: CardKind = CardKind.OPPORTUNITY
    opportunity_type: OpportunityType | None = None


class RiskCard(IntelCard):
    card_type: CardKind = CardKind.RISK
    risk_type: RiskType | None = None
    severity: str | None = None
    suggested_mitigations: list[str] = Field(default_factory=list)


class InsightCard(IntelCard):
    card_type: CardKind = CardKind.INSIGHT
    insight_type: InsightType | None = None
    linked_opportunities: list[str] = Field(default_factory=list)
    linked_risks: list[str] = Field(default_factory=list)


class VisualPatternAsset(IntelCard):
    card_type: CardKind = CardKind.VISUAL_PATTERN
    pattern_name: str = ""
    description: str = ""
    applicable_scene_refs: list[str] = Field(default_factory=list)
    applicable_style_refs: list[str] = Field(default_factory=list)
    supporting_note_ids: list[str] = Field(default_factory=list)
    supporting_image_refs: list[str] = Field(default_factory=list)
    click_potential: float = 0.0
    conversion_potential: float = 0.0
    misuse_risks: list[str] = Field(default_factory=list)


class DemandSpecAsset(IntelCard):
    card_type: CardKind = CardKind.DEMAND_SPEC
    demand_name: str = ""
    target_category_refs: list[str] = Field(default_factory=list)
    target_audience_refs: list[str] = Field(default_factory=list)
    target_scene_refs: list[str] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    optional_features: list[str] = Field(default_factory=list)
    risk_constraints: list[str] = Field(default_factory=list)
