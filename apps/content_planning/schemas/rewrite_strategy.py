"""改写策略：将 OpportunityBrief + 模板匹配结果翻译为可执行的内容改造方向。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from apps.content_planning.schemas.lineage import PlanLineage
from apps.content_planning.schemas.lock import ObjectLock


class RewriteStrategy(BaseModel):
    """从"用哪个模板"到"具体怎么改"的关键翻译层。"""

    strategy_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    brief_id: str = ""
    template_id: str = ""
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""
    created_by: str = ""
    updated_by: str = ""
    approval_status: Literal["pending_review", "approved", "changes_requested", "rejected"] = "pending_review"
    lifecycle_status: Literal[
        "new", "reviewed", "promoted", "in_planning", "ready", "approved", "exported", "published"
    ] = "new"
    visibility: Literal["workspace", "brand", "private"] = "workspace"

    strategy_status: Literal["draft", "generated", "reviewed", "approved"] = "draft"

    positioning_statement: str = ""
    new_hook: str = ""
    new_angle: str = ""
    tone_of_voice: str = ""

    hook_strategy: str = ""
    cta_strategy: str = ""
    scene_emphasis: list[str] = Field(default_factory=list)
    rationale: str = ""

    keep_elements: list[str] = Field(default_factory=list)
    replace_elements: list[str] = Field(default_factory=list)
    enhance_elements: list[str] = Field(default_factory=list)
    avoid_elements: list[str] = Field(default_factory=list)

    title_strategy: list[str] = Field(default_factory=list)
    body_strategy: list[str] = Field(default_factory=list)
    image_strategy: list[str] = Field(default_factory=list)

    differentiation_axis: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)

    # V2.0 对比与版本字段
    strategy_version: int = 1
    comparison_note: str | None = None
    editable_blocks: list[str] | None = None

    lineage: PlanLineage | None = None
    locks: ObjectLock | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
