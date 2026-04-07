"""XHS 专用 OpportunityCard Schema —— 三维结构化流水线的最终决策资产。"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from apps.intel_hub.schemas.evidence import XHSEvidenceRef


class XHSOpportunityCard(BaseModel):
    """小红书三维结构化流水线生成的机会卡。"""

    opportunity_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    title: str = ""
    summary: str = ""
    opportunity_type: Literal["visual", "demand", "product", "content", "scene"] = "demand"
    entity_refs: list[str] = Field(default_factory=list)
    scene_refs: list[str] = Field(default_factory=list)
    style_refs: list[str] = Field(default_factory=list)
    need_refs: list[str] = Field(default_factory=list)
    risk_refs: list[str] = Field(default_factory=list)
    visual_pattern_refs: list[str] = Field(default_factory=list)
    content_pattern_refs: list[str] = Field(default_factory=list)
    value_proposition_refs: list[str] = Field(default_factory=list)
    audience_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[XHSEvidenceRef] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    suggested_next_step: list[str] = Field(default_factory=list)
    review_status: str = "pending"

    @field_validator("suggested_next_step", mode="before")
    @classmethod
    def _coerce_next_step(cls, v):  # noqa: N805
        if isinstance(v, str):
            return [v] if v else []
        return v
    source_note_ids: list[str] = Field(default_factory=list)

    # V0.7 检视聚合字段
    review_count: int = 0
    manual_quality_score_avg: float | None = None
    actionable_ratio: float | None = None
    evidence_sufficient_ratio: float | None = None
    composite_review_score: float | None = None
    qualified_opportunity: bool = False
    opportunity_status: str = "pending_review"

    # V0.8 发现层洞察字段
    engagement_insight: str | None = None
    cross_modal_verdict: str | None = None
    insight_statement: str | None = None
