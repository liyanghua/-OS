"""Layer 1: 内容解析层 — 把 MediaCrawler 原始笔记 dict 转为 NoteContentFrame。"""

from __future__ import annotations

import logging
from typing import Any

from apps.intel_hub.schemas.content_frame import CommentFrame, NoteContentFrame

logger = logging.getLogger(__name__)


def parse_note_content(raw: dict[str, Any]) -> NoteContentFrame | None:
    """将 mediacrawler_loader 产出的 raw signal dict 解析为 NoteContentFrame。

    如果 raw 不含笔记级信息（如非小红书来源），返回 None。
    """
    payload = raw.get("raw_payload", {})
    note_id = payload.get("note_id") or raw.get("note_id", "")
    if not note_id:
        return None

    title_text = str(raw.get("title") or "")
    body_text = str(raw.get("raw_text") or raw.get("summary") or "")

    tag_list = [str(t).strip() for t in raw.get("tags", []) if str(t).strip()]

    metrics = raw.get("metrics", {})

    comments = _parse_comments(raw.get("comments", []))
    top_comments = _parse_comments(raw.get("top_comments", []))
    neg_comments = _parse_comments(raw.get("neg_comments", []))

    image_list_raw = raw.get("image_list") or payload.get("image_list") or []
    if isinstance(image_list_raw, str):
        image_list_raw = [s.strip() for s in image_list_raw.split(",") if s.strip()]

    return NoteContentFrame(
        note_id=str(note_id),
        note_url=str(raw.get("source_url") or ""),
        author_id=str(raw.get("account") or ""),
        author_name=str(raw.get("author") or ""),
        published_at=str(raw.get("published_at") or ""),
        crawled_at=str(raw.get("captured_at") or ""),
        platform=str(raw.get("platform") or "xiaohongshu"),
        source_type=str(raw.get("raw_source_type") or "mediacrawler_xhs"),
        title_text=title_text,
        body_text=body_text,
        tag_list=tag_list,
        like_count=_safe_int(metrics.get("liked_count")),
        comment_count=_safe_int(metrics.get("comment_count")),
        collect_count=_safe_int(metrics.get("collected_count")),
        share_count=_safe_int(metrics.get("share_count")),
        image_count=len(image_list_raw),
        cover_image=str(image_list_raw[0]) if image_list_raw else "",
        image_list=[str(img) for img in image_list_raw],
        comments=comments,
        top_comments=top_comments,
        neg_comments=neg_comments,
    )


def _parse_comments(raw_comments: Any) -> list[CommentFrame]:
    if not isinstance(raw_comments, list):
        return []
    frames: list[CommentFrame] = []
    for item in raw_comments:
        if not isinstance(item, dict):
            continue
        frames.append(
            CommentFrame(
                comment_id=str(item.get("comment_id") or item.get("id") or ""),
                user_name=str(item.get("user_name") or item.get("nickname") or ""),
                comment_text=str(item.get("comment_text") or item.get("content") or ""),
                like_count=_safe_int(item.get("like_count") or item.get("sub_comment_count")),
                reply_count=_safe_int(item.get("reply_count") or item.get("sub_comment_count")),
            )
        )
    return frames


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
