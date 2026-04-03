from __future__ import annotations

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.enums import ReviewStatus, WatchlistType


class Watchlist(BaseModel):
    id: str
    watchlist_type: WatchlistType
    title: str
    summary: str = ""
    source_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    timestamps: dict[str, str] = Field(default_factory=dict)
    confidence: float = 1.0
    evidence_refs: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING
    keywords: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    priority: float = 0.5
