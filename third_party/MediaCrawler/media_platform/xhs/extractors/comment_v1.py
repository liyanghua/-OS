"""评论抽取器 v1。

适用于小红书评论 API 返回的评论数据结构。
"""

from __future__ import annotations

from typing import Any


class CommentExtractorV1:
    name = "xhs_comment"
    version = "v1"
    page_type = "comment"
    last_verified_at = "2026-04-02"

    def validate(self, data: dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            return False
        return bool(data.get("id")) and "content" in data

    def extract(self, data: dict[str, Any]) -> dict[str, Any]:
        """标准化评论输出。"""
        user_info = data.get("user_info", {})
        return {
            "comment_id": data.get("id", ""),
            "note_id": data.get("note_id", ""),
            "content": data.get("content", ""),
            "user_id": user_info.get("user_id", ""),
            "nickname": user_info.get("nickname", ""),
            "liked_count": data.get("like_count", "0"),
            "create_time": data.get("create_time", 0),
            "sub_comment_count": data.get("sub_comment_count", 0),
        }
