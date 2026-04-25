"""ContextSpec — 一次策略编译的运行时上下文。

承接 docs/SOP_to_content_plan.md 第 9.6 节。
从 XHSOpportunityCard / SellingPointSpec / BrandProfile / 用户输入
组装出可被 StrategyCompiler 消费的标准化上下文。

注意：MVP 不为 StoreVisualSystem 单独建 schema，
而是把 style/colors/typography/imageTone/avoid 装进
`context_json["storeVisualSystem"]` 字段。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


VisualScene = Literal[
    "taobao_main_image",
    "xhs_cover",
    "detail_first_screen",
    "video_first_frame",
]


class ContextProduct(BaseModel):
    name: str = ""
    category: str = ""
    material: str = ""
    price_band: str = ""
    target_age_range: str = ""
    gender: str = ""
    pattern_theme: str = ""
    claims: list[str] = Field(default_factory=list)
    product_images: list[str] = Field(default_factory=list)


class ContextStoreVisualSystem(BaseModel):
    style: str = ""
    colors: list[str] = Field(default_factory=list)
    typography: str = ""
    image_tone: str = ""
    allowed_elements: list[str] = Field(default_factory=list)
    avoid_elements: list[str] = Field(default_factory=list)
    example_images: list[str] = Field(default_factory=list)


class ContextAudience(BaseModel):
    buyer: str = ""
    user: str = ""
    decision_logic: list[str] = Field(default_factory=list)


class ContextCompetitor(BaseModel):
    common_visuals: list[str] = Field(default_factory=list)
    common_claims: list[str] = Field(default_factory=list)
    differentiation_opportunities: list[str] = Field(default_factory=list)


class ContextPlatform(BaseModel):
    ratio: str = "1:1"
    copy_limit: int = 3
    product_visibility_min: float = 0.6


class ContextSpec(BaseModel):
    """策略编译运行时上下文——StrategyCompiler 的输入。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_type: Literal["opportunity_card", "manual", "selling_point_spec"] = "manual"
    source_id: str = ""
    workspace_id: str = ""
    brand_id: str = ""

    category: str = ""
    scene: VisualScene = "taobao_main_image"

    product: ContextProduct = Field(default_factory=ContextProduct)
    store_visual_system: ContextStoreVisualSystem = Field(default_factory=ContextStoreVisualSystem)
    audience: ContextAudience = Field(default_factory=ContextAudience)
    competitor: ContextCompetitor = Field(default_factory=ContextCompetitor)
    platform: ContextPlatform = Field(default_factory=ContextPlatform)

    selling_point_spec_id: str = ""
    opportunity_card_id: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
