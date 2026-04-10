"""效果回流与反馈闭环：记录资产发布后的效果数据。

Phase 1 扩展：FeedbackRecord / WinningPattern / FailedPattern 用于发布结果闭环。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

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


# ---------------------------------------------------------------------------
# Phase 1 发布结果闭环：沉淀对象
# ---------------------------------------------------------------------------


class FeedbackRecord(BaseModel):
    """单次发布的过程指标反馈，用于证明"系统让内容更好"。"""

    feedback_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    asset_bundle_id: str = ""
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""

    approval_rounds: int = 0
    manual_edits_count: int = 0
    time_to_ready: float = 0.0  # seconds from brief-created to export-ready
    published_at: datetime | None = None
    engagement_proxy: float = 0.0  # normalised 0-1
    feedback_quality: Literal["excellent", "good", "average", "poor", "unknown"] = "unknown"
    notes: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WinningPattern(BaseModel):
    """从高表现资产中提取的可复用模式。"""

    pattern_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    workspace_id: str = ""
    brand_id: str = ""

    pattern_type: Literal["template", "strategy", "hook", "tone", "scene", "cta", "other"] = "other"
    label: str = ""
    description: str = ""
    source_opportunity_ids: list[str] = Field(default_factory=list)
    source_asset_bundle_ids: list[str] = Field(default_factory=list)
    avg_engagement_proxy: float = 0.0
    sample_count: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FailedPattern(BaseModel):
    """从低表现资产中提取的反模式/教训。"""

    pattern_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    workspace_id: str = ""
    brand_id: str = ""

    pattern_type: Literal["template", "strategy", "hook", "tone", "scene", "cta", "other"] = "other"
    label: str = ""
    description: str = ""
    source_opportunity_ids: list[str] = Field(default_factory=list)
    source_asset_bundle_ids: list[str] = Field(default_factory=list)
    avg_engagement_proxy: float = 0.0
    sample_count: int = 0
    root_cause: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
