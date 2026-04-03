"""搜索结果页抽取器 v1。

适用于小红书 /api/sns/web/v1/search/notes 返回的搜索结果数据结构。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class SearchExtractorV1:
    name = "xhs_search"
    version = "v1"
    page_type = "search"
    last_verified_at = "2026-04-02"

    REQUIRED_FIELDS = {"items", "has_more"}

    def validate(self, data: dict[str, Any]) -> bool:
        return isinstance(data, dict) and self.REQUIRED_FIELDS.issubset(data.keys())

    def extract(self, data: dict[str, Any]) -> dict[str, Any]:
        """从搜索 API 响应中抽取候选笔记列表。"""
        items = data.get("items", [])
        candidates = []
        for item in items:
            model_type = item.get("model_type", "")
            if model_type in ("rec_query", "hot_query"):
                continue
            candidates.append({
                "note_id": item.get("id", ""),
                "xsec_source": item.get("xsec_source", ""),
                "xsec_token": item.get("xsec_token", ""),
                "model_type": model_type,
            })
        return {
            "has_more": data.get("has_more", False),
            "candidates": candidates,
        }
