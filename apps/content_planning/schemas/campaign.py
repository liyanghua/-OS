"""Campaign 级批量生产：一个机会 → 多套方案 → 多个资产包 → 多变体 → 多平台版。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PlatformVersion(BaseModel):
    """平台版本预留。"""

    platform: Literal["xiaohongshu", "ecommerce_main", "sku", "video_script"] = "xiaohongshu"
    platform_label: str = "小红书版"
    adaptation_notes: str = ""


class CampaignPlan(BaseModel):
    """Campaign 级别生产计划。"""

    campaign_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    campaign_name: str = ""
    opportunity_ids: list[str] = Field(default_factory=list)
    target_bundle_count: int = 1
    target_variants_per_bundle: int = 1
    platform_versions: list[PlatformVersion] = Field(
        default_factory=lambda: [PlatformVersion()]
    )
    status: Literal["draft", "in_progress", "completed"] = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CampaignResult(BaseModel):
    """Campaign 执行结果。"""

    campaign_id: str = ""
    total_opportunities: int = 0
    total_bundles: int = 0
    total_variants: int = 0
    completed_bundles: int = 0
    failed_bundles: int = 0
    platform_versions_generated: list[str] = Field(default_factory=list)
