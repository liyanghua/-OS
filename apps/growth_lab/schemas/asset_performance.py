"""AssetPerformanceCard / PatternTemplate — 资产图谱核心对象。

让素材和结果形成复利：标签化、高表现沉淀、模式库、复用推荐。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AssetPerformanceCard(BaseModel):
    """带业绩绑定的资产卡——Asset Graph 的核心展示单元。"""

    asset_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    asset_type: Literal[
        "main_image_template", "first3s_hook",
        "viral_clip", "selling_point_template",
        "high_performer", "failure_case",
    ] = "high_performer"

    source_platform: str = ""
    source_variant_id: str = ""
    source_test_task_id: str = ""

    linked_selling_points: list[str] = Field(default_factory=list)
    linked_patterns: list[str] = Field(default_factory=list)
    linked_scenarios: list[str] = Field(default_factory=list)

    best_metrics: dict[str, Any] = Field(default_factory=dict)
    usage_count: int = 0
    reusable: bool = True
    reuse_directions: list[str] = Field(default_factory=list)

    tags: list[str] = Field(default_factory=list)
    image_url: str = ""
    video_url: str = ""
    description: str = ""

    # B2B 上下文
    workspace_id: str = ""
    brand_id: str = ""

    status: Literal["active", "archived", "template"] = "active"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PatternTemplate(BaseModel):
    """模式模板——从高表现资产中沉淀的可复用模板。"""

    template_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    template_type: Literal[
        "main_image", "close_up", "benefit_card",
        "high_ctr_combo", "first3s_hook", "opening_line",
        "platform_migration",
    ] = "main_image"
    name: str = ""
    description: str = ""
    pattern_spec: dict[str, Any] = Field(default_factory=dict)
    source_asset_ids: list[str] = Field(default_factory=list)
    avg_performance: dict[str, float] = Field(default_factory=dict)
    usage_count: int = 0

    workspace_id: str = ""
    brand_id: str = ""

    status: Literal["draft", "published", "archived"] = "draft"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReuseRecommendation(BaseModel):
    """复用推荐——为当前卖点/场景推荐可复用资产。"""

    recommendation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    target_selling_point_id: str = ""
    recommended_asset_id: str = ""
    recommended_template_id: str = ""
    match_reason: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
