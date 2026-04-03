"""小红书 MediaCrawler 数据加载器。

支持三种数据源格式:
1. capture_dir: review_intel xhs_capture 产出的 events.jsonl
2. store_jsonl: MediaCrawler 原生 store 产出的 jsonl 文件
3. store_sqlite: MediaCrawler SQLite 存储（xhs_note + xhs_note_comment 表）
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_xhs_raw_signals(source_configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """读取所有配置的 XHS 数据源，返回评论级 raw dict 列表。"""
    records: list[dict[str, Any]] = []
    for src in source_configs:
        src_type = src.get("type", "")
        src_path = Path(src.get("path", ""))
        if not src_path.exists():
            continue
        if src_type == "capture_dir":
            records.extend(_load_from_capture_dir(src_path))
        elif src_type == "store_jsonl":
            records.extend(_load_from_store_jsonl(src_path))
        elif src_type == "store_sqlite":
            records.extend(_load_from_store_sqlite(src_path))
    return records


def _load_from_capture_dir(capture_root: Path) -> list[dict[str, Any]]:
    """从 review_intel capture 目录加载，扫描所有 job 子目录下的 events.jsonl。"""
    records: list[dict[str, Any]] = []
    if not capture_root.is_dir():
        return records

    job_dirs = sorted(capture_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for job_dir in job_dirs:
        if not job_dir.is_dir():
            continue
        events_path = job_dir / "raw" / "events.jsonl"
        if not events_path.is_file():
            continue

        manifest = _read_manifest(job_dir / "manifest.json")
        keyword = _extract_keyword_from_manifest(manifest)

        for line in events_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            record = _map_raw_review_event(event, keyword=keyword, file_path=str(events_path))
            if record:
                records.append(record)
    return records


def _load_from_store_jsonl(store_dir: Path) -> list[dict[str, Any]]:
    """从 MediaCrawler 的 jsonl store 目录加载评论文件。"""
    records: list[dict[str, Any]] = []
    if not store_dir.is_dir():
        return records

    jsonl_files = sorted(
        [f for f in store_dir.rglob("*.jsonl") if "comment" in f.stem.lower()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not jsonl_files:
        jsonl_files = sorted(
            store_dir.rglob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    for jsonl_path in jsonl_files[:5]:
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            record = _map_store_comment(item, file_path=str(jsonl_path))
            if record:
                records.append(record)
    return records


def _load_from_store_sqlite(store_dir: Path) -> list[dict[str, Any]]:
    """从 MediaCrawler SQLite 存储加载笔记和评论数据。"""
    records: list[dict[str, Any]] = []
    if not store_dir.is_dir():
        return records

    db_files = sorted(store_dir.rglob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for db_path in db_files[:3]:
        try:
            records.extend(_read_xhs_sqlite(db_path))
        except Exception:
            continue
    return records


def _read_xhs_sqlite(db_path: Path) -> list[dict[str, Any]]:
    """读取 MediaCrawler 的 SQLite 数据库，联表查询笔记 + 评论。"""
    records: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }

        note_map: dict[str, dict[str, Any]] = {}
        if "xhs_note" in tables:
            for row in conn.execute("SELECT * FROM xhs_note").fetchall():
                note = dict(row)
                note_map[note.get("note_id", "")] = note

        if "xhs_note_comment" in tables:
            for row in conn.execute("SELECT * FROM xhs_note_comment").fetchall():
                comment = dict(row)
                note_id = comment.get("note_id", "")
                note = note_map.get(note_id, {})
                record = _map_sqlite_comment(comment, note, file_path=str(db_path))
                if record:
                    records.append(record)
    return records


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

def _map_raw_review_event(event: dict[str, Any], *, keyword: str | None, file_path: str) -> dict[str, Any] | None:
    """将 review_intel 的 RawReviewEvent JSON 映射为 intel_hub raw dict。"""
    raw_text = str(event.get("raw_text") or "").strip()
    if not raw_text:
        return None

    extra_meta = event.get("extra_meta") or {}
    note_id = str(extra_meta.get("note_id") or event.get("parent_id") or "")
    note_title = str(extra_meta.get("note_title") or "").strip()
    raw_metrics = event.get("raw_metrics") or {}

    return {
        "title": note_title or raw_text[:80],
        "summary": raw_text[:200],
        "raw_text": raw_text,
        "source_url": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else None,
        "source_name": "小红书",
        "platform": "xhs",
        "published_at": event.get("publish_time"),
        "captured_at": event.get("crawl_time"),
        "author": event.get("author_id"),
        "metrics": {
            "likes": raw_metrics.get("like_count", 0),
            "comments": raw_metrics.get("sub_comment_count", 0),
        },
        "keyword": keyword,
        "watchlist_hits": [],
        "tags": ["小红书评论", "用户声音"],
        "raw_source_type": "xhs_capture_event",
        "raw_payload": event,
        "file_path": file_path,
        "_xhs_note_id": note_id,
        "_xhs_note_title": note_title,
        "_xhs_like_count": raw_metrics.get("like_count", 0),
    }


def _map_store_comment(item: dict[str, Any], *, file_path: str) -> dict[str, Any] | None:
    """将 MediaCrawler store 原生评论 dict 映射为 intel_hub raw dict。"""
    content = str(item.get("content") or "").strip()
    if not content:
        return None

    note_id = str(item.get("note_id") or "")
    return {
        "title": content[:80],
        "summary": content[:200],
        "raw_text": content,
        "source_url": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else None,
        "source_name": "小红书",
        "platform": "xhs",
        "published_at": _xhs_ts_to_iso(item.get("create_time")),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "author": item.get("user_id"),
        "metrics": {
            "likes": item.get("like_count", 0),
            "comments": item.get("sub_comment_count", 0),
        },
        "keyword": item.get("source_keyword"),
        "watchlist_hits": [],
        "tags": ["小红书评论", "用户声音"],
        "raw_source_type": "xhs_store_jsonl",
        "raw_payload": item,
        "file_path": file_path,
        "_xhs_note_id": note_id,
        "_xhs_note_title": "",
        "_xhs_like_count": item.get("like_count", 0),
    }


def _map_sqlite_comment(
    comment: dict[str, Any], note: dict[str, Any], *, file_path: str
) -> dict[str, Any] | None:
    """将 MediaCrawler SQLite 评论行映射为 intel_hub raw dict。"""
    content = str(comment.get("content") or "").strip()
    if not content:
        return None

    note_id = str(comment.get("note_id") or "")
    note_title = str(note.get("title") or note.get("desc") or "")[:200].strip()
    return {
        "title": note_title or content[:80],
        "summary": content[:200],
        "raw_text": content,
        "source_url": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else None,
        "source_name": "小红书",
        "platform": "xhs",
        "published_at": _xhs_ts_to_iso(comment.get("create_time")),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "author": comment.get("user_id"),
        "metrics": {
            "likes": comment.get("like_count", 0),
            "comments": comment.get("sub_comment_count", 0),
        },
        "keyword": note.get("source_keyword"),
        "watchlist_hits": [],
        "tags": ["小红书评论", "用户声音"],
        "raw_source_type": "xhs_store_sqlite",
        "raw_payload": {"comment": comment, "note": note},
        "file_path": file_path,
        "_xhs_note_id": note_id,
        "_xhs_note_title": note_title,
        "_xhs_like_count": comment.get("like_count", 0),
    }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _extract_keyword_from_manifest(manifest: dict[str, Any]) -> str | None:
    qs = manifest.get("query_spec")
    if isinstance(qs, dict):
        terms = qs.get("terms")
        if isinstance(terms, list) and terms:
            return ",".join(str(t).strip() for t in terms if str(t).strip())
    cq = str(manifest.get("crawl_query") or "").strip()
    return cq if cq else None


def _xhs_ts_to_iso(value: Any) -> str | None:
    """小红书时间戳（毫秒/秒/ISO）转 ISO 字符串。"""
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n > 1e12:
        n = n / 1000.0
    elif n > 1e10:
        n = n / 1000.0
    return datetime.fromtimestamp(n, tz=timezone.utc).isoformat()
