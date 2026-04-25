"""FeedbackRecord — 视觉策略图片的专家评分与业务指标记录。

承接 docs/SOP_to_content_plan.md 第 6.8 节。
MVP 仅落库（不更新规则权重），Phase 5 才接 weight_updater。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


FeedbackDecision = Literal["enter_test_pool", "revise", "reject", "winner"]


class ExpertScore(BaseModel):
    first_glance: float = Field(default=0.0, ge=0.0, le=10.0)
    audience_fit: float = Field(default=0.0, ge=0.0, le=10.0)
    function_clarity: float = Field(default=0.0, ge=0.0, le=10.0)
    style_fit: float = Field(default=0.0, ge=0.0, le=10.0)
    differentiation: float = Field(default=0.0, ge=0.0, le=10.0)
    generation_quality: float = Field(default=0.0, ge=0.0, le=10.0)
    overall: float = Field(default=0.0, ge=0.0, le=10.0)


class BusinessMetrics(BaseModel):
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    favorites: int = 0
    add_to_cart: int = 0
    conversion_rate: float = 0.0


class FeedbackRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    image_variant_id: str = ""
    strategy_candidate_id: str = ""
    rule_ids: list[str] = Field(default_factory=list)

    expert_score: ExpertScore = Field(default_factory=ExpertScore)
    business_metrics: BusinessMetrics = Field(default_factory=BusinessMetrics)

    decision: FeedbackDecision = "enter_test_pool"
    comments: str = ""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RuleWeightHistory(BaseModel):
    """规则权重变更历史——v0.1 仅由 expert_score 触发。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    rule_id: str = ""
    old_weight: float = 0.0
    new_weight: float = 0.0
    delta: float = 0.0
    reason: str = ""
    feedback_record_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
