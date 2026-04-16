"""SellingPointSpec — 独立的卖点对象，从机会编译而来。

卖点不再隐藏在 Brief 里，而是独立可操作的一级对象。
支持多平台表达映射（货架/抖音/小红书/口播）。
包含 ExpertAnnotation，支持专家经验注入与沉淀。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExpertAnnotation(BaseModel):
    """专家批注——可注入当前编译并沉淀为未来编译参考。"""

    annotation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    spec_id: str = ""
    field_name: str = ""
    annotation_type: Literal["insight", "correction", "risk", "template"] = "insight"
    content: str = ""
    annotator: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PlatformExpressionSpec(BaseModel):
    """单平台表达规格。"""

    platform: str = ""
    expression_type: Literal[
        "shelf", "first3s", "spoken", "standard_play",
    ] = "shelf"
    headline: str = ""
    sub_copy: str = ""
    visual_direction: str = ""
    tone: str = ""
    notes: str = ""


class SellingPointSpec(BaseModel):
    """结构化卖点对象——卖点编译器的核心产出。"""

    spec_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_opportunity_ids: list[str] = Field(default_factory=list)

    core_claim: str = ""
    supporting_claims: list[str] = Field(default_factory=list)
    target_people: list[str] = Field(default_factory=list)
    target_scenarios: list[str] = Field(default_factory=list)
    differentiation_notes: str = ""
    risk_notes: str = ""

    # 多平台表达
    shelf_expression: PlatformExpressionSpec | None = None
    first3s_expression: PlatformExpressionSpec | None = None
    spoken_expression: PlatformExpressionSpec | None = None
    standard_play_expression: PlatformExpressionSpec | None = None

    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # B2B 上下文
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""

    status: Literal[
        "draft", "compiled", "reviewed", "approved", "archived",
    ] = "draft"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
