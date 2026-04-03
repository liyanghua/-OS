"""笔记详情抽取器 v1。

适用于 get_note_by_id / get_note_by_id_from_html 返回的笔记数据结构。
"""

from __future__ import annotations

from typing import Any


class NoteDetailExtractorV1:
    name = "xhs_note_detail"
    version = "v1"
    page_type = "note_detail"
    last_verified_at = "2026-04-02"

    EXPECTED_KEYS = {"note_id", "title", "desc", "type"}

    def validate(self, data: dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            return False
        return bool(data.get("note_id")) and any(
            k in data for k in ("title", "desc")
        )

    def extract(self, data: dict[str, Any]) -> dict[str, Any]:
        """标准化笔记详情输出。"""
        return {
            "note_id": data.get("note_id", ""),
            "title": data.get("title", ""),
            "desc": data.get("desc", ""),
            "type": data.get("type", ""),
            "user": data.get("user", {}),
            "image_list": data.get("image_list", []),
            "tag_list": data.get("tag_list", []),
            "liked_count": data.get("liked_count", "0"),
            "collected_count": data.get("collected_count", "0"),
            "comment_count": data.get("comment_count", "0"),
            "share_count": data.get("share_count", "0"),
            "time": data.get("time", 0),
            "last_modify_ts": data.get("last_modify_ts", 0),
            "note_url": data.get("note_url", ""),
        }
