"""机会卡人工检视反馈 Schema。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class OpportunityReview(BaseModel):
    """单条人工检视反馈。"""

    review_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str
    reviewer: str
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    manual_quality_score: int = Field(ge=1, le=10)
    is_actionable: bool
    evidence_sufficient: bool
    review_notes: str | None = None
