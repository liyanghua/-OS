"""变体系统：同一资产包的多维度变体管理。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Variant(BaseModel):
    """单个变体。"""

    variant_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_bundle_id: str = ""
    variant_axis: Literal["template", "tone", "scene", "brand", "platform"] = "tone"
    variant_label: str = ""
    asset_snapshot: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VariantSet(BaseModel):
    """变体集合。"""

    variant_set_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    parent_bundle_id: str = ""
    brief_id: str = ""
    strategy_id: str = ""
    plan_id: str = ""
    variants: list[Variant] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
