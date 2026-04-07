"""机会摘要：从 promoted 机会卡中提炼的结构化内容策划锚点。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class OpportunityBrief(BaseModel):
    """结构化的机会摘要，是后续模板选择、策略生成、内容编译的统一入参。"""

    brief_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    source_note_ids: list[str] = Field(default_factory=list)

    opportunity_type: str = ""
    opportunity_title: str = ""
    opportunity_summary: str = ""

    target_user: list[str] = Field(default_factory=list)
    target_scene: list[str] = Field(default_factory=list)
    core_motive: str | None = None
    content_goal: str | None = None
    product_fit: str | None = None

    primary_value: str | None = None
    secondary_values: list[str] = Field(default_factory=list)

    visual_style_direction: list[str] = Field(default_factory=list)
    price_positioning: str | None = None
    platform_expression: str | None = "小红书"

    template_hints: list[str] = Field(default_factory=list)
    avoid_directions: list[str] = Field(default_factory=list)
    proof_from_source: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
