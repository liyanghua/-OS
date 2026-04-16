"""MainImageVariant — 主图裂变版本对象。

围绕货架主图做拆解、变量控制、版本生成、测试计划。
变量维度：模特/构图/场景/字卡/色彩/风格。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class VariantVariable(BaseModel):
    """单个裂变变量及其取值。"""

    dimension: Literal[
        "model_face", "hair_style", "hair_color",
        "composition", "close_up_detail",
        "scene_background", "benefit_card",
        "color_style", "stimulation_level",
    ] = "composition"
    label: str = ""
    value: str = ""
    locked: bool = False


class ImageVariantSpec(BaseModel):
    """结构化图片变体规格——传给生成引擎的完整指令。"""

    spec_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    variables: list[VariantVariable] = Field(default_factory=list)
    base_prompt: str = ""
    negative_prompt: str = ""
    style_tags: list[str] = Field(default_factory=list)
    reference_image_urls: list[str] = Field(default_factory=list)
    size: str = "1024*1024"
    provider_hint: str = "auto"
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_prompt_text(self) -> str:
        """将变量组合拼成 prompt 增强段。"""
        parts = [self.base_prompt]
        for v in self.variables:
            if v.value and not v.locked:
                parts.append(f"{v.label}: {v.value}")
        return ", ".join(p for p in parts if p)


class MainImageVariant(BaseModel):
    """主图裂变版本——Main Image Lab 的核心产出对象。"""

    variant_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_selling_point_id: str = ""
    source_asset_ids: list[str] = Field(default_factory=list)
    source_opportunity_id: str = ""

    platform: str = ""
    sku_id: str = ""
    store_id: str = ""

    key_variables: list[VariantVariable] = Field(default_factory=list)
    image_variant_spec: ImageVariantSpec | None = None
    visual_pattern_refs: list[str] = Field(default_factory=list)

    # 生成结果
    generated_image_url: str = ""
    generation_provider: str = ""
    generation_elapsed_ms: int = 0
    generation_prompt_sent: str = ""

    expected_goal: str = ""
    quality_score: float | None = None

    # B2B 上下文
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""

    status: Literal[
        "draft", "generating", "generated", "selected",
        "in_test", "archived",
    ] = "draft"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
