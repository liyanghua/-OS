from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.enums import ReviewStatus


class EvidenceRef(BaseModel):
    id: str
    title: str
    summary: str = ""
    source_name: str | None = None
    source_url: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    timestamps: dict[str, str] = Field(default_factory=dict)
    confidence: float = 0.5
    evidence_refs: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING
    raw_text: str = ""
    author: str | None = None
    account: str | None = None
    watchlist_hits: list[str] = Field(default_factory=list)
    raw_source_type: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    platform: str | None = None
    keyword: str | None = None
    rank: int | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
