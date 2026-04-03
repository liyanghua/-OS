"""小红书笔记解析层 Schema —— 归一化后的笔记结构。"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.xhs_raw import XHSComment, XHSImageFrame, XHSNoteRaw


class XHSParsedNote(BaseModel):
    """解析后的小红书笔记，包含归一化字段与互动摘要。"""

    raw_note: XHSNoteRaw
    normalized_title: str = ""
    normalized_body: str = ""
    normalized_tags: list[str] = Field(default_factory=list)
    parsed_comments: list[XHSComment] = Field(default_factory=list)
    parsed_images: list[XHSImageFrame] = Field(default_factory=list)
    engagement_summary: dict = Field(default_factory=dict)

    @property
    def note_id(self) -> str:
        return self.raw_note.note_id

    @classmethod
    def from_raw(cls, raw_note: XHSNoteRaw) -> XHSParsedNote:
        norm_title = _normalize_text(raw_note.title_text)
        norm_body = _normalize_text(raw_note.body_text)
        norm_tags = [t.lower().strip() for t in raw_note.tag_list if t.strip()]

        total_engagement = (
            raw_note.like_count
            + raw_note.collect_count
            + raw_note.comment_count
            + raw_note.share_count
        )
        engagement_summary = {
            "total_engagement": total_engagement,
            "like_count": raw_note.like_count,
            "collect_count": raw_note.collect_count,
            "comment_count": raw_note.comment_count,
            "share_count": raw_note.share_count,
            "like_ratio": round(raw_note.like_count / max(total_engagement, 1), 3),
            "comment_ratio": round(raw_note.comment_count / max(total_engagement, 1), 3),
        }

        return cls(
            raw_note=raw_note,
            normalized_title=norm_title,
            normalized_body=norm_body,
            normalized_tags=norm_tags,
            parsed_comments=raw_note.comments,
            parsed_images=raw_note.image_list,
            engagement_summary=engagement_summary,
        )


_TOPIC_TAG_RE = re.compile(r"#[^#]+\[话题\]#")
_EMOJI_RE = re.compile(r"\[[\u4e00-\u9fffA-Za-z]+R?\]")


def _normalize_text(text: str) -> str:
    """去除话题标记、表情符号、多余空白。"""
    text = _TOPIC_TAG_RE.sub("", text)
    text = _EMOJI_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
