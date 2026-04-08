"""统一资产包：整合标题/正文/图片为可导出对象。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from apps.content_planning.schemas.lineage import PlanLineage


class AssetBundle(BaseModel):
    """内容策划最终产物，统一打包标题/正文/图片执行指令。"""

    asset_bundle_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    plan_id: str = ""
    opportunity_id: str = ""
    template_id: str = ""
    template_name: str = ""

    title_candidates: list[dict] = Field(default_factory=list)
    body_outline: list[str] = Field(default_factory=list)
    body_draft: str = ""
    image_execution_briefs: list[dict] = Field(default_factory=list)

    export_status: Literal["draft", "ready", "exported"] = "draft"
    lineage: PlanLineage | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
