"""VisualStrategyPack — 视觉策略包。

承接 docs/SOP_to_content_plan.md 第 6.4 节。
一次"机会卡 + 卖点 + 商品 + 店铺视觉"上下文经 StrategyCompiler
编译后产出的视觉策略包。包含若干 StrategyCandidate。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


VisualStrategyScene = Literal[
    "taobao_main_image",
    "xhs_cover",
    "detail_first_screen",
    "video_first_frame",
]


class VisualStrategyPackSource(BaseModel):
    opportunity_card_id: str = ""
    selling_point_spec_id: str = ""
    product_id: str = ""
    brand_id: str = ""
    content_plan_id: str = ""


class VisualStrategyPack(BaseModel):
    """编译产出的视觉策略包。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    source: VisualStrategyPackSource = Field(default_factory=VisualStrategyPackSource)

    category: str = ""
    scene: VisualStrategyScene = "taobao_main_image"

    rule_pack_id: str = ""
    context_spec_id: str = ""
    candidate_ids: list[str] = Field(default_factory=list)

    workspace_id: str = ""
    brand_id: str = ""

    status: Literal[
        "compiled",
        "partially_selected",
        "sent_to_visual_workbench",
        "testing",
        "completed",
    ] = "compiled"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
