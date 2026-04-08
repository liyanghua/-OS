"""机会摘要：从 promoted 机会卡中提炼的结构化内容策划锚点。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from apps.content_planning.schemas.lineage import PlanLineage


class OpportunityBrief(BaseModel):
    """结构化的机会摘要，是后续模板选择、策略生成、内容编译的统一入参。"""

    brief_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    source_note_ids: list[str] = Field(default_factory=list)
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""
    created_by: str = ""
    updated_by: str = ""
    approval_status: Literal["pending_review", "approved", "changes_requested", "rejected"] = "pending_review"
    visibility: Literal["workspace", "brand", "private"] = "workspace"
    version: int = 1

    brief_status: Literal["draft", "generated", "reviewed", "approved"] = "draft"

    opportunity_type: str = ""
    opportunity_title: str = ""
    opportunity_summary: str = ""

    target_user: list[str] = Field(default_factory=list)
    target_scene: list[str] = Field(default_factory=list)
    core_motive: str | None = None
    content_goal: str | None = None
    product_fit: str | None = None

    target_audience: str | None = None
    evidence_summary: str | None = None
    constraints: list[str] = Field(default_factory=list)
    suggested_direction: str | None = None

    primary_value: str | None = None
    secondary_values: list[str] = Field(default_factory=list)

    visual_style_direction: list[str] = Field(default_factory=list)
    price_positioning: str | None = None
    platform_expression: str | None = "小红书"

    template_hints: list[str] = Field(default_factory=list)
    avoid_directions: list[str] = Field(default_factory=list)
    proof_from_source: list[str] = Field(default_factory=list)

    # V0.8 策划层洞察字段
    why_worth_doing: str | None = None
    competitive_angle: str | None = None
    engagement_proof: str | None = None
    cross_modal_confidence_label: str | None = None

    # V2.0 策划深度字段
    why_now: str | None = None
    differentiation_view: str | None = None
    proof_blocks: list[dict] | None = None
    planning_direction: str | None = None

    lineage: PlanLineage | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
