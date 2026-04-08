"""效果回流与反馈闭环：记录资产发布后的效果数据。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PublishedAssetResult(BaseModel):
    """已发布资产的效果回流记录。"""

    result_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    asset_bundle_id: str = ""
    opportunity_id: str = ""

    platform: str = "xhs"
    published_note_id: str = ""
    published_at: datetime | None = None

    like_count: int = 0
    collect_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0

    performance_label: Literal["excellent", "good", "average", "poor", "unknown"] = "unknown"
    feedback_notes: str = ""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EngagementResult(BaseModel):
    """互动效果快照。"""

    total_engagement: int = 0
    collect_like_ratio: float = 0.0
    comment_rate: float = 0.0
    performance_label: str = "unknown"


class TemplateEffectivenessRecord(BaseModel):
    """模板有效性记录，关联回写到模板库。"""

    record_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    template_id: str = ""
    opportunity_id: str = ""
    asset_bundle_id: str = ""
    performance_label: str = "unknown"
    engagement: EngagementResult = Field(default_factory=EngagementResult)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
