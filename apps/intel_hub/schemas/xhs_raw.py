"""小红书笔记原始层 Schema —— 直接映射 MediaCrawler JSONL 字段。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class XHSComment(BaseModel):
    """单条小红书评论。"""

    comment_id: str = ""
    note_id: str = ""
    content: str = ""
    nickname: str = ""
    user_id: str = ""
    like_count: int = 0
    sub_comment_count: int = 0
    parent_comment_id: str = "0"
    ip_location: str | None = None
    create_time: int | None = None


class XHSImageFrame(BaseModel):
    """单张笔记图片。"""

    url: str
    index: int = 0
    is_cover: bool = False


class XHSNoteRaw(BaseModel):
    """小红书笔记原始结构，直接映射 MediaCrawler 输出字段。"""

    note_id: str
    note_url: str = ""
    author_id: str = ""
    author_name: str = ""
    published_at: str | None = None
    crawled_at: str | None = None
    title_text: str = ""
    body_text: str = ""
    tag_list: list[str] = Field(default_factory=list)
    like_count: int = 0
    comment_count: int = 0
    collect_count: int = 0
    share_count: int = 0
    image_count: int = 0
    cover_image: str = ""
    image_list: list[XHSImageFrame] = Field(default_factory=list)
    comments: list[XHSComment] = Field(default_factory=list)
    top_comments: list[XHSComment] = Field(default_factory=list)
    platform: str = "xiaohongshu"
    source_type: str = "mediacrawler_xhs"
    source_keyword: str = ""
    note_type: str = ""
    ip_location: str = ""

    @classmethod
    def from_mediacrawler_dict(
        cls,
        raw: dict[str, Any],
        comments: list[dict[str, Any]] | None = None,
    ) -> XHSNoteRaw:
        """从 MediaCrawler JSONL dict 构建 XHSNoteRaw。"""
        note_id = str(raw.get("note_id", ""))
        title = str(raw.get("title") or "")
        body = str(raw.get("desc") or "")

        tag_str = str(raw.get("tag_list") or "")
        tags = [t.strip() for t in tag_str.split(",") if t.strip()]
        extra_tags = re.findall(r"#([^#\[]+)\[话题\]#", body)
        seen = {t.lower() for t in tags}
        for et in extra_tags:
            if et.strip().lower() not in seen:
                tags.append(et.strip())
                seen.add(et.strip().lower())

        img_str = str(raw.get("image_list") or "")
        img_urls = [u.strip() for u in img_str.split(",") if u.strip()]
        _CDN_RE = re.compile(
            r"https?://sns-webpic-qc\.xhscdn\.com/\d+/[0-9a-f]+/(.+)"
        )
        images: list[XHSImageFrame] = []
        for i, url in enumerate(img_urls):
            m = _CDN_RE.match(url)
            if m:
                url = f"https://sns-img-bd.xhscdn.com/{m.group(1)}"
            images.append(XHSImageFrame(url=url, index=i, is_cover=(i == 0)))

        note_url = str(raw.get("note_url") or "")
        if not note_url and note_id:
            note_url = f"https://www.xiaohongshu.com/explore/{note_id}"

        parsed_comments: list[XHSComment] = []
        raw_comments = comments or []
        for c in raw_comments:
            if not isinstance(c, dict):
                continue
            parsed_comments.append(
                XHSComment(
                    comment_id=str(c.get("comment_id", "")),
                    note_id=str(c.get("note_id", note_id)),
                    content=str(c.get("content", "")),
                    nickname=str(c.get("nickname", "")),
                    user_id=str(c.get("user_id", "")),
                    like_count=_safe_int(c.get("like_count")),
                    sub_comment_count=_safe_int(c.get("sub_comment_count")),
                    parent_comment_id=str(c.get("parent_comment_id", "0")),
                    ip_location=c.get("ip_location") or None,
                    create_time=_safe_int(c.get("create_time")) or None,
                )
            )
        top_comments = sorted(parsed_comments, key=lambda c: c.like_count, reverse=True)[:5]

        return cls(
            note_id=note_id,
            note_url=note_url,
            author_id=str(raw.get("user_id", "")),
            author_name=str(raw.get("nickname", "")),
            published_at=_ts_to_iso(raw.get("time")),
            crawled_at=_ts_to_iso(raw.get("last_modify_ts")),
            title_text=title,
            body_text=body,
            tag_list=tags,
            like_count=_safe_int(raw.get("liked_count")),
            comment_count=_safe_int(raw.get("comment_count")),
            collect_count=_safe_int(raw.get("collected_count")),
            share_count=_safe_int(raw.get("share_count")),
            image_count=len(images),
            cover_image=images[0].url if images else "",
            image_list=images,
            comments=parsed_comments,
            top_comments=top_comments,
            platform="xiaohongshu",
            source_type="mediacrawler_xhs",
            source_keyword=str(raw.get("source_keyword", "")),
            note_type=str(raw.get("type", "")),
            ip_location=str(raw.get("ip_location", "")),
        )


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _ts_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return str(value).strip() if isinstance(value, str) else None
    if ts <= 0:
        return None
    if ts > 1e12:
        ts = ts / 1000.0
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
