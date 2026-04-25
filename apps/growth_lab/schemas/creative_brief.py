"""CreativeBrief — 视觉策略候选编译出的可编辑生图策划案。

承接 docs/SOP_to_content_plan.md 第 6.6 节。
为避免与 apps/content_planning/schemas/opportunity_brief.py 中的
`OpportunityBrief` 混淆，这里使用 `CreativeBrief` 命名。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class BriefCanvas(BaseModel):
    ratio: Literal["1:1", "3:4", "4:5", "16:9", "9:16"] = "1:1"
    platform: str = "taobao_main_image"
    text_area: Literal["left", "right", "top", "bottom", "none"] = "right"
    product_visibility_min: float = 0.6


class BriefScene(BaseModel):
    background: str = ""
    environment: str = ""
    props: list[str] = Field(default_factory=list)
    forbidden_props: list[str] = Field(default_factory=list)


class BriefProduct(BaseModel):
    placement: str = "中心偏右"
    scale: str = "占画面 65-75%"
    angle: str = "俯视"
    visible_features: list[str] = Field(default_factory=list)


class BriefStyle(BaseModel):
    tone: str = ""
    color_palette: list[str] = Field(default_factory=list)
    lighting: str = ""
    texture: str = ""


class BriefPeople(BaseModel):
    enabled: bool = False
    age: str = ""
    gender: str = ""
    action: str = ""
    adult_visible: bool = False


class BriefCopywriting(BaseModel):
    headline: str = ""
    selling_points: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    price_visible: bool = False


class CreativeBrief(BaseModel):
    """可编辑的生图策划案——StrategyCandidate 与 PromptSpec 之间的中间层。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    strategy_candidate_id: str = ""

    canvas: BriefCanvas = Field(default_factory=BriefCanvas)
    scene: BriefScene = Field(default_factory=BriefScene)
    product: BriefProduct = Field(default_factory=BriefProduct)
    style: BriefStyle = Field(default_factory=BriefStyle)
    people: BriefPeople = Field(default_factory=BriefPeople)
    copywriting: BriefCopywriting = Field(default_factory=BriefCopywriting)
    negative: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
