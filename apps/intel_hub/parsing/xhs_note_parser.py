"""小红书笔记解析器 —— raw dict -> XHSNoteRaw -> XHSParsedNote。

负责将 MediaCrawler 原始输出转化为结构化、归一化的笔记对象，
供下游三维提取器使用。
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.intel_hub.schemas.xhs_raw import XHSNoteRaw

logger = logging.getLogger(__name__)


def parse_raw_note(
    raw: dict[str, Any],
    comments: list[dict[str, Any]] | None = None,
) -> XHSNoteRaw:
    """从 MediaCrawler JSONL dict 构建 XHSNoteRaw。"""
    return XHSNoteRaw.from_mediacrawler_dict(raw, comments=comments)


def parse_note(raw_note: XHSNoteRaw) -> XHSParsedNote:
    """从 XHSNoteRaw 构建归一化的 XHSParsedNote。"""
    return XHSParsedNote.from_raw(raw_note)


def load_and_parse_notes(
    content_dir: str | Path,
) -> list[XHSParsedNote]:
    """从 MediaCrawler JSONL 目录加载并解析所有笔记。

    自动关联 search_comments_*.jsonl 到对应笔记。
    """
    content_dir = Path(content_dir)
    if not content_dir.exists():
        logger.warning("content_dir does not exist: %s", content_dir)
        return []

    content_files = sorted(content_dir.glob("search_contents_*.jsonl"))
    comment_files = sorted(content_dir.glob("search_comments_*.jsonl"))

    comment_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cf in comment_files:
        try:
            for line in cf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                nid = item.get("note_id")
                if nid:
                    comment_index[str(nid)].append(item)
        except Exception:
            logger.exception("failed to read comment file: %s", cf)

    if comment_index:
        logger.info(
            "xhs_note_parser: built comment index — %d comments across %d notes",
            sum(len(v) for v in comment_index.values()),
            len(comment_index),
        )

    parsed_notes: list[XHSParsedNote] = []
    seen_ids: set[str] = set()

    for cf in content_files:
        try:
            for line in cf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                note_id = item.get("note_id")
                if not note_id or note_id in seen_ids:
                    continue
                seen_ids.add(note_id)

                comments = comment_index.get(str(note_id), [])
                raw_note = parse_raw_note(item, comments=comments)
                if not raw_note.title_text and not raw_note.body_text:
                    continue
                parsed = parse_note(raw_note)
                parsed_notes.append(parsed)
        except Exception:
            logger.exception("failed to read content file: %s", cf)

    logger.info("xhs_note_parser: parsed %d notes from %s", len(parsed_notes), content_dir)
    return parsed_notes
