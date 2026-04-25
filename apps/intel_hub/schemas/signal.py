from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.enums import ReviewStatus


class Signal(BaseModel):
    id: str
    title: str
    summary: str = ""
    source_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    platform_refs: list[str] = Field(default_factory=list)
    raw_entity_hits: list[str] = Field(default_factory=list)
    canonical_entity_refs: list[str] = Field(default_factory=list)
    timestamps: dict[str, str] = Field(default_factory=dict)
    confidence: float = 0.5
    evidence_refs: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING
    raw_text: str = ""
    source_name: str | None = None
    source_url: str | None = None
    author: str | None = None
    account: str | None = None
    watchlist_hits: list[str] = Field(default_factory=list)
    raw_source_type: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    keyword: str | None = None
    rank: int | None = None
    business_priority_score: float = 0.0
    classification_hint: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    # V2: 多维本体引用（由 Layer 3 本体映射填充）
    scene_refs: list[str] = Field(default_factory=list)
    style_refs: list[str] = Field(default_factory=list)
    need_refs: list[str] = Field(default_factory=list)
    risk_factor_refs: list[str] = Field(default_factory=list)
    material_refs: list[str] = Field(default_factory=list)
    content_pattern_refs: list[str] = Field(default_factory=list)
    visual_pattern_refs: list[str] = Field(default_factory=list)
    audience_refs: list[str] = Field(default_factory=list)
    buying_barrier_refs: list[str] = Field(default_factory=list)
    value_proposition_refs: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)

    # V2.1: 类目透视引擎接入点
    # ``lens_id`` 由 ingestion 阶段根据 keyword 路由填充，
    # ``business_signals`` 透传 Layer 2 的 BusinessSignalFrame.model_dump()，
    # 让下游 projector / CategoryLensEngine 可以读取视觉/评论等字段级信号。
    lens_id: str | None = None
    business_signals: dict[str, Any] | None = None
