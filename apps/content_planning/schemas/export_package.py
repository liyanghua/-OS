"""ExportPackage: 资产包导出封装，带完整 lineage 追溯。

封装 AssetBundle 的导出结果，支持多种格式（JSON/Markdown/图片包），
确保导出物可反查全链路 lineage。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.content_planning.schemas.lineage import PlanLineage


class ExportPackage(BaseModel):
    """资产包导出封装对象。"""

    package_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    asset_bundle_id: str = ""
    opportunity_id: str = ""
    brief_id: str = ""
    strategy_id: str = ""
    plan_id: str = ""
    template_id: str = ""
    variant_ids: list[str] = Field(default_factory=list)

    format: Literal["json", "markdown", "image_package", "full"] = "json"
    export_url: str = ""
    export_data: dict[str, Any] = Field(default_factory=dict)

    lineage: PlanLineage | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str = ""
