from __future__ import annotations

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.enums import ReviewStatus


class ReviewUpdateRequest(BaseModel):
    review_status: ReviewStatus
    review_notes: str = ""
    reviewer: str = Field(min_length=1)
    feedback_tags: list[str] = Field(default_factory=list)
