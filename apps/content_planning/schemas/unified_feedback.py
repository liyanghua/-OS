"""V5 统一反馈事实表：合并三条反馈管道为单一数据源。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class UnifiedFeedback(BaseModel):
    """单一事实源：发布后的效果 + 过程指标 + 人工备注。"""

    feedback_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    asset_bundle_id: str = ""
    template_id: str = ""
    strategy_id: str = ""
    plan_id: str = ""
    brief_id: str = ""
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""

    platform: str = "xhs"
    published_note_id: str = ""
    published_at: datetime | None = None

    like_count: int = 0
    collect_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0

    performance_tier: Literal["excellent", "good", "average", "poor", "unknown"] = "unknown"
    engagement_score: float = 0.0

    approval_rounds: int = 0
    manual_edits_count: int = 0
    time_to_ready_seconds: float = 0.0

    human_notes: str = ""
    human_edits_summary: str = ""

    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def compute_engagement_score(self) -> float:
        total = self.like_count + self.collect_count * 2 + self.comment_count * 3 + self.share_count * 4
        if self.view_count > 0:
            self.engagement_score = min(1.0, total / max(self.view_count, 1) * 10)
        elif total > 0:
            self.engagement_score = min(1.0, total / 500)
        return self.engagement_score

    def auto_tier(self) -> str:
        score = self.compute_engagement_score()
        if score >= 0.7:
            self.performance_tier = "excellent"
        elif score >= 0.4:
            self.performance_tier = "good"
        elif score >= 0.15:
            self.performance_tier = "average"
        elif score > 0:
            self.performance_tier = "poor"
        return self.performance_tier
