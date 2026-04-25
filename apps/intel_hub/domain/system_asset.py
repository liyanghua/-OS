"""SystemAsset 统一资产模型。

聚合三条主线（图文笔记 / 增长实验 / 套图工作台）的产出，
作为 ``/asset-workspace`` 与 ``/api/system-assets`` 的统一视图。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


SourceLane = Literal["content_note", "growth_lab", "workspace_bundle"]
"""来源主线：图文笔记 / 增长实验室 / 套图工作台。"""

AssetType = Literal[
    "xhs_note",
    "main_image_set",
    "detail_gallery",
    "video",
    "buyer_show",
    "competitor_benchmark",
    "growth_test_card",
    "asset_bundle",
]
"""资产类型枚举。"""

AssetStatus = Literal["draft", "ready", "published", "archived"]


class SystemAsset(BaseModel):
    """系统资产单元。

    - ``source_ref`` 视来源不同：
        - content_note: 机会卡 ``opportunity_id``
        - growth_lab: 卖点 ``spec_id`` 或 asset card_id
        - workspace_bundle: ``workspace_project_id`` / ``plan_id``
    - ``lineage`` 用于跳转回 brief / strategy / visual_pattern / test_id 等。
    """

    asset_id: str
    source_lane: SourceLane
    source_ref: str = ""
    lens_id: str | None = None
    asset_type: AssetType
    title: str
    thumbnails: list[str] = Field(default_factory=list)
    status: AssetStatus = "draft"
    lineage: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)

    def primary_link(self) -> str:
        """返回该资产的首要可跳转链接（用于 UI）。"""
        if self.source_lane == "content_note":
            if self.lineage.get("planning_url"):
                return str(self.lineage["planning_url"])
            return f"/content-planning/assets/{self.source_ref}" if self.source_ref else "/asset-workspace"
        if self.source_lane == "growth_lab":
            if self.lineage.get("asset_graph_url"):
                return str(self.lineage["asset_graph_url"])
            return "/growth-lab/assets"
        if self.source_lane == "workspace_bundle":
            if self.lineage.get("workspace_url"):
                return str(self.lineage["workspace_url"])
            return "/growth-lab/workspace"
        return "/asset-workspace"
