"""统一资产包：整合标题/正文/图片为可导出对象。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from apps.content_planning.schemas.lineage import PlanLineage
from apps.content_planning.schemas.lock import ObjectLock


class AssetBundle(BaseModel):
    """内容策划最终产物，统一打包标题/正文/图片执行指令。"""

    asset_bundle_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    plan_id: str = ""
    opportunity_id: str = ""
    template_id: str = ""
    template_name: str = ""
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""
    created_by: str = ""
    updated_by: str = ""
    approval_status: Literal["pending_review", "approved", "changes_requested", "rejected"] = "pending_review"
    visibility: Literal["workspace", "brand", "private"] = "workspace"
    version: int = 1
    variant_set_id: str | None = None

    title_candidates: list[dict] = Field(default_factory=list)
    body_outline: list[str] = Field(default_factory=list)
    body_draft: str = ""
    image_execution_briefs: list[dict] = Field(default_factory=list)

    export_status: Literal["draft", "ready", "exported"] = "draft"
    lineage: PlanLineage | None = None
    locks: ObjectLock | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
