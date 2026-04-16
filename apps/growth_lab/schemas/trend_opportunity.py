"""TrendOpportunity — 统一机会对象，承接热点/上升品/竞品变化/跨域灵感。

映射关系：
- 可从 XHSOpportunityCard 通过 adapter 转入
- 作为 Radar 页的核心展示与操作对象
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TrendOpportunity(BaseModel):
    """热点驱动的统一机会对象。"""

    opportunity_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    title: str = ""
    summary: str = ""

    source_platform: str = ""
    source_type: Literal[
        "trend", "rising_product", "competitor_shift",
        "cross_domain_idea", "internal_feedback", "xhs_opportunity",
    ] = "trend"

    freshness_score: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    actionability_score: float = Field(default=0.5, ge=0.0, le=1.0)

    linked_topics: list[str] = Field(default_factory=list)
    linked_people: list[str] = Field(default_factory=list)
    linked_scenarios: list[str] = Field(default_factory=list)

    suggested_actions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_note_ids: list[str] = Field(default_factory=list)

    # 语义富上下文（adapter 从原始卡打包的完整语义字段）
    rich_context: dict = Field(default_factory=dict)

    # 关联到原 XHSOpportunityCard（如适用）
    source_opportunity_id: str | None = None
    source_opportunity_type: str | None = None

    # B2B 上下文
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""

    status: Literal[
        "new", "bookmarked", "promoted", "in_compilation",
        "archived", "rejected",
    ] = "new"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
