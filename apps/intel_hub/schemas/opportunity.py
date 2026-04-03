"""XHS 专用 OpportunityCard Schema —— 三维结构化流水线的最终决策资产。"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

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
    evidence_refs: list[XHSEvidenceRef] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    suggested_next_step: str = ""
    review_status: str = "pending"
    source_note_ids: list[str] = Field(default_factory=list)
