"""MediaCrawler 原生输出加载器。

读取 MediaCrawler 产出的 JSON / JSONL / SQLite 文件，
将笔记级记录映射为 intel_hub 统一 raw signal dict。

V2: 自动关联 search_comments_*.jsonl 到对应笔记，
    将评论列表写入 raw dict 的 ``comments`` 字段，
    供下游 content_parser / signal_extractor 使用。

支持的输出结构：
- JSONL: data/xhs/jsonl/search_contents_*.jsonl  (每行一条笔记)
- JSONL: data/xhs/jsonl/search_comments_*.jsonl  (每行一条评论, note_id 关联)
- JSON:  data/xhs/json/search_contents_*.json    (数组)
- SQLite: database/sqlite_tables.db              (xhs_note 表)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".jsonl", ".json", ".db"}
_COMMENT_FILE_RE = re.compile(r"search_comments", re.IGNORECASE)
_XHS_SIGNED_CDN_RE = re.compile(
    r"https?://sns-webpic-qc\.xhscdn\.com/\d+/[0-9a-f]+/(.+)"
)


def load_mediacrawler_records(
    output_path: str | Path,
    platform: str = "xiaohongshu",
) -> list[dict[str, Any]]:
    """读取 MediaCrawler 原生输出，返回 raw signal dict 列表。

    ``output_path`` 可以是：
    - 包含 .jsonl / .json 文件的目录
    - 单个 .jsonl / .json / .db 文件

    目录模式下自动关联 ``search_comments_*.jsonl`` 到对应笔记。
    """
    path = Path(output_path)
    if not path.exists():
        logger.warning("mediacrawler output path does not exist: %s", path)
        return []

    records: list[dict[str, Any]] = []

    if path.is_file():
        records.extend(_load_from_file(path, platform))
    elif path.is_dir():
        all_files = sorted(
            (f for f in path.rglob("*") if f.is_file() and f.suffix in SUPPORTED_SUFFIXES),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        comment_files = [f for f in all_files if _is_comment_file(f)]
        content_files = [f for f in all_files if not _is_comment_file(f)]

        comment_index = _build_comment_index(comment_files)
        if comment_index:
            logger.info(
                "mediacrawler_loader: built comment index — %d comments across %d notes from %d files",
                sum(len(v) for v in comment_index.values()),
                len(comment_index),
                len(comment_files),
            )

        for file_path in content_files:
            records.extend(_load_from_file(file_path, platform, comment_index=comment_index))

    logger.info("mediacrawler_loader: loaded %d records from %s", len(records), path)
    return records


def _is_comment_file(file_path: Path) -> bool:
    return bool(_COMMENT_FILE_RE.search(file_path.stem))


def _build_comment_index(comment_files: list[Path]) -> dict[str, list[dict[str, Any]]]:
    """从 search_comments_*.jsonl 构建 {note_id: [comment_dict, ...]} 索引。"""
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for file_path in comment_files:
        if file_path.suffix.lower() != ".jsonl":
            continue
        try:
            for line in file_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict):
                    continue
                note_id = item.get("note_id")
                if not note_id:
                    continue
                index[str(note_id)].append(item)
        except Exception:
            logger.exception("failed to read comment file: %s", file_path)
    return dict(index)


def _load_from_file(
    file_path: Path,
    platform: str,
    *,
    comment_index: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    suffix = file_path.suffix.lower()
    if suffix == ".jsonl":
        return _load_jsonl(file_path, platform, comment_index=comment_index)
    if suffix == ".json":
        return _load_json(file_path, platform, comment_index=comment_index)
    if suffix == ".db":
        return _load_sqlite(file_path, platform, comment_index=comment_index)
    return []


def _load_jsonl(
    file_path: Path,
    platform: str,
    *,
    comment_index: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    source_type = "mediacrawler_jsonl"
    try:
        for line_num, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("skip bad json at %s:%d", file_path, line_num)
                continue
            if not isinstance(item, dict) or not item.get("note_id"):
                continue
            mapped = _map_note_to_raw_signal(item, source_type, platform, str(file_path), comment_index=comment_index)
            if mapped:
                records.append(mapped)
    except Exception:
        logger.exception("failed to read jsonl: %s", file_path)
    return records


def _load_json(
    file_path: Path,
    platform: str,
    *,
    comment_index: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    source_type = "mediacrawler_json"
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict) or not item.get("note_id"):
                continue
            mapped = _map_note_to_raw_signal(item, source_type, platform, str(file_path), comment_index=comment_index)
            if mapped:
                records.append(mapped)
    except Exception:
        logger.exception("failed to read json: %s", file_path)
    return records


def _load_sqlite(
    file_path: Path,
    platform: str,
    *,
    comment_index: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    source_type = "mediacrawler_sqlite"
    try:
        conn = sqlite3.connect(str(file_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='xhs_note'")
        if not cursor.fetchone():
            conn.close()
            return records

        cursor.execute("SELECT * FROM xhs_note")
        for row in cursor.fetchall():
            item = dict(row)
            mapped = _map_note_to_raw_signal(item, source_type, platform, str(file_path), comment_index=comment_index)
            if mapped:
                records.append(mapped)
        conn.close()
    except Exception:
        logger.exception("failed to read sqlite: %s", file_path)
    return records


def _map_note_to_raw_signal(
    note: dict[str, Any],
    source_type: str,
    platform: str,
    file_path: str,
    *,
    comment_index: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any] | None:
    """将 MediaCrawler 原生笔记 dict 映射为 intel_hub raw signal dict。"""
    note_id = note.get("note_id")
    if not note_id:
        return None

    title = str(note.get("title") or note.get("desc", "")[:120] or "").strip()
    if not title:
        return None

    desc = str(note.get("desc") or "")
    source_url = str(note.get("note_url") or "")
    if not source_url and note_id:
        source_url = f"https://www.xiaohongshu.com/explore/{note_id}"

    published_at = _ts_to_iso(note.get("time"))
    captured_at = _ts_to_iso(note.get("last_modify_ts"))

    liked = _safe_int(note.get("liked_count"))
    collected = _safe_int(note.get("collected_count"))
    comment_count = _safe_int(note.get("comment_count"))
    shared = _safe_int(note.get("share_count"))
    engagement = liked + collected + comment_count + shared

    tag_str = str(note.get("tag_list") or "")
    tags = [t.strip() for t in tag_str.split(",") if t.strip()] if tag_str else []

    keyword = str(note.get("source_keyword") or "").strip() or None

    image_list_str = str(note.get("image_list") or "")
    image_list = [
        _to_persistent_image_url(url.strip())
        for url in image_list_str.split(",")
        if url.strip()
    ] if image_list_str else []

    raw_comments: list[dict[str, Any]] = []
    if comment_index:
        raw_comments = comment_index.get(str(note_id), [])

    result: dict[str, Any] = {
        "title": title,
        "summary": desc[:200] if desc else "",
        "raw_text": desc,
        "source_url": source_url,
        "source_name": "小红书",
        "platform": platform,
        "published_at": published_at,
        "captured_at": captured_at,
        "author": str(note.get("nickname") or ""),
        "account": str(note.get("user_id") or ""),
        "metrics": {
            "liked_count": liked,
            "collected_count": collected,
            "comment_count": comment_count,
            "share_count": shared,
            "engagement": engagement,
        },
        "keyword": keyword,
        "tags": tags,
        "watchlist_hits": [],
        "raw_source_type": source_type,
        "raw_payload": {
            "note_id": note_id,
            "note_type": note.get("type"),
            "ip_location": note.get("ip_location"),
        },
        "raw_payload_path": file_path,
        "image_list": image_list,
        "comments": raw_comments,
    }
    return result


def _ts_to_iso(value: Any) -> str | None:
    """将 unix 时间戳（秒或 13 位毫秒）转为 ISO 8601 字符串。"""
    if value is None:
        return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    if ts <= 0:
        return None
    if ts > 1e12:
        ts = ts / 1000.0
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _to_persistent_image_url(url: str) -> str:
    """将小红书带签名的 CDN URL 转为不过期的持久化 URL。

    签名格式: http://sns-webpic-qc.xhscdn.com/{timestamp}/{sig}/{id}!{params}
    持久格式: https://sns-img-bd.xhscdn.com/{id}!{params}
    """
    m = _XHS_SIGNED_CDN_RE.match(url)
    if m:
        return f"https://sns-img-bd.xhscdn.com/{m.group(1)}"
    return url


def _safe_int(value: Any) -> int:
    """安全将字符串/数字转 int，失败返回 0。"""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
