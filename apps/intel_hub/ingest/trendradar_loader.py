from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_SUFFIXES = {".json", ".jsonl", ".db"}
DATE_PATTERNS = (
    re.compile(r"(\d{4}-\d{2}-\d{2}(?:[T_ -]\d{2}[:\-]?\d{2}[:\-]?\d{2})?)"),
    re.compile(r"(\d{8}(?:\d{6})?)"),
)


def load_latest_raw_signals(output_dir: Path, include_rss: bool = True) -> list[dict[str, Any]]:
    latest_files = _find_latest_files(output_dir, include_rss=include_rss)
    records: list[dict[str, Any]] = []
    for file_path in latest_files:
        for record in _load_records_from_file(file_path):
            normalized = _normalize_raw_record(record, file_path)
            if normalized:
                records.append(normalized)
    return records


def _find_latest_files(output_dir: Path, include_rss: bool) -> list[Path]:
    candidate_roots = [output_dir / "news"]
    if include_rss:
        candidate_roots.append(output_dir / "rss")

    latest_files: list[Path] = []
    for root in candidate_roots:
        if root.exists():
            files = [path for path in root.rglob("*") if path.is_file() and path.suffix in SUPPORTED_SUFFIXES]
            latest = _pick_latest(files)
            if latest:
                latest_files.append(latest)

    if latest_files:
        return latest_files

    files = [path for path in output_dir.rglob("*") if path.is_file() and path.suffix in SUPPORTED_SUFFIXES]
    latest = _pick_latest(files)
    return [latest] if latest else []


def _pick_latest(files: list[Path]) -> Path | None:
    if not files:
        return None
    return max(files, key=lambda path: (_batch_sort_key(path), path.stat().st_mtime, path.name))


def _load_records_from_file(file_path: Path) -> list[dict[str, Any]]:
    if file_path.suffix == ".json":
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return [
            {
                **item,
                "raw_source_type": "json",
            }
            for item in _coerce_records(payload)
        ]
    if file_path.suffix == ".jsonl":
        lines = [line for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [
            {
                **item,
                "raw_source_type": "jsonl",
            }
            for item in (json.loads(line) for line in lines)
            if isinstance(item, dict)
        ]
    if file_path.suffix == ".db":
        return _load_records_from_sqlite(file_path)
    return []


def _coerce_records(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "records", "data", "rows", "news", "rss"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def _load_records_from_sqlite(file_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(file_path) as connection:
        connection.row_factory = sqlite3.Row
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        table_set = set(tables)
        if "news_items" in table_set:
            return _load_news_records(connection, table_set)
        if "rss_items" in table_set:
            return _load_rss_records(connection, table_set)
        return _load_generic_sqlite_records(connection, table_set)


def _load_news_records(connection: sqlite3.Connection, tables: set[str]) -> list[dict[str, Any]]:
    platform_map = _table_map(connection, "platforms") if "platforms" in tables else {}
    rank_map = _latest_rank_map(connection, "rank_history", ("news_item_id", "item_id", "news_id")) if "rank_history" in tables else {}

    records: list[dict[str, Any]] = []
    for row in connection.execute("SELECT * FROM news_items").fetchall():
        item = dict(row)
        platform_info = platform_map.get(item.get("platform_id")) if item.get("platform_id") is not None else None
        latest_rank = rank_map.get(item.get("id"), {})
        metrics = _extract_metrics(item)
        if latest_rank.get("score") is not None:
            metrics["rank_score"] = latest_rank.get("score")
        if item.get("hot_score") is not None:
            metrics["hot_score"] = item.get("hot_score")

        records.append(
            {
                "title": _pick_text(item, "title", "headline", "news_title"),
                "summary": _pick_text(item, "summary", "description", "excerpt", "content"),
                "raw_text": _pick_text(item, "raw_text", "content", "text", "body", "summary"),
                "source_url": _pick_text(item, "source_url", "url", "link"),
                "source_name": _pick_text(
                    platform_info or {},
                    "display_name",
                    "title",
                    "name",
                )
                or _pick_text(item, "source_name", "media", "site_name", "publisher"),
                "platform": _pick_text(item, "platform", "channel", "source_type")
                or _pick_text(platform_info or {}, "name", "slug", "code", "source_type")
                or "news",
                "published_at": _pick_text(item, "published_at", "publish_time", "created_at", "time"),
                "captured_at": _pick_text(item, "captured_at", "collected_at")
                or _pick_text(latest_rank, "captured_at", "created_at", "updated_at"),
                "author": _pick_text(item, "author", "author_name", "username"),
                "account": _pick_text(item, "account", "account_name", "screen_name"),
                "metrics": metrics,
                "rank": _pick_int(item.get("rank")) or _pick_int(latest_rank.get("rank")),
                "keyword": _pick_text(item, "keyword", "matched_keyword", "query"),
                "watchlist_hits": _parse_multi_value(
                    item.get("watchlist_hits") or item.get("matched_watchlists") or item.get("watchlist_context")
                ),
                "tags": _parse_multi_value(item.get("tags")),
                "raw_source_type": "db_news_items",
                "raw_payload": {
                    "news_item": item,
                    "platform": platform_info or {},
                    "rank_history": latest_rank,
                },
            }
        )
    return records


def _load_rss_records(connection: sqlite3.Connection, tables: set[str]) -> list[dict[str, Any]]:
    feed_map = _table_map(connection, "rss_feeds") if "rss_feeds" in tables else {}
    records: list[dict[str, Any]] = []

    for row in connection.execute("SELECT * FROM rss_items").fetchall():
        item = dict(row)
        feed_info = feed_map.get(item.get("feed_id")) if item.get("feed_id") is not None else None
        records.append(
            {
                "title": _pick_text(item, "title", "headline"),
                "summary": _pick_text(item, "summary", "description", "excerpt", "content"),
                "raw_text": _pick_text(item, "raw_text", "content", "text", "body", "summary"),
                "source_url": _pick_text(item, "source_url", "url", "link"),
                "source_name": _pick_text(feed_info or {}, "title", "name") or _pick_text(item, "source_name", "feed_title"),
                "platform": "rss",
                "published_at": _pick_text(item, "published_at", "publish_time", "created_at"),
                "captured_at": _pick_text(item, "captured_at", "collected_at"),
                "author": _pick_text(item, "author", "author_name"),
                "account": _pick_text(feed_info or {}, "title", "name"),
                "metrics": _extract_metrics(item),
                "rank": _pick_int(item.get("rank")),
                "keyword": _pick_text(item, "keyword", "matched_keyword", "query"),
                "watchlist_hits": _parse_multi_value(
                    item.get("watchlist_hits") or item.get("matched_watchlists") or item.get("watchlist_context")
                ),
                "tags": _parse_multi_value(item.get("tags")),
                "raw_source_type": "db_rss_items",
                "raw_payload": {
                    "rss_item": item,
                    "rss_feed": feed_info or {},
                },
            }
        )
    return records


def _load_generic_sqlite_records(connection: sqlite3.Connection, tables: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for table_name in tables:
        cursor = connection.execute(f"SELECT * FROM {table_name}")
        columns = [description[0] for description in cursor.description or []]
        for row in cursor.fetchall():
            records.append(
                {
                    **dict(zip(columns, row)),
                    "raw_source_type": "db_generic",
                }
            )
    return records


def _table_map(connection: sqlite3.Connection, table_name: str) -> dict[Any, dict[str, Any]]:
    rows = connection.execute(f"SELECT * FROM {table_name}").fetchall()
    table_dict: dict[Any, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        if "id" in item:
            table_dict[item["id"]] = item
    return table_dict


def _latest_rank_map(
    connection: sqlite3.Connection,
    table_name: str,
    item_id_keys: tuple[str, ...],
) -> dict[Any, dict[str, Any]]:
    rows = [dict(row) for row in connection.execute(f"SELECT * FROM {table_name}").fetchall()]
    if not rows:
        return {}

    item_key = next((key for key in item_id_keys if key in rows[0]), None)
    if item_key is None:
        return {}

    timestamp_keys = ("captured_at", "created_at", "updated_at", "recorded_at", "time")
    latest: dict[Any, dict[str, Any]] = {}
    for row in rows:
        item_id = row.get(item_key)
        if item_id is None:
            continue
        current = latest.get(item_id)
        if current is None or _row_sort_key(row, timestamp_keys) >= _row_sort_key(current, timestamp_keys):
            latest[item_id] = row
    return latest


def _normalize_raw_record(record: dict[str, Any], file_path: Path) -> dict[str, Any] | None:
    title = _pick_text(record, "title", "headline", "news_title")
    summary = _pick_text(record, "summary", "description", "excerpt", "content")
    raw_text = _pick_text(record, "raw_text", "content", "text", "body", "summary") or summary or title
    if not any([title, summary, raw_text]):
        return None

    source_url = _pick_text(record, "source_url", "url", "link")
    source_name = _pick_text(record, "source_name", "media", "site_name", "publisher", "platform_name")
    captured_at = _pick_text(record, "captured_at", "collected_at", "crawled_at")
    published_at = _pick_text(
        record,
        "published_at",
        "publish_time",
        "published",
        "created_at",
        "time",
    )
    keyword = _pick_text(record, "keyword", "matched_keyword", "query")
    platform = _pick_text(record, "platform", "channel", "source_type") or file_path.parent.name
    rank = _pick_int(record.get("rank") or record.get("position"))
    metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else _extract_metrics(record)
    watchlist_hits = _parse_multi_value(
        record.get("watchlist_hits") or record.get("matched_watchlists") or record.get("watchlist_context")
    )
    raw_source_type = _pick_text(record, "raw_source_type") or file_path.suffix.lstrip(".")

    return {
        "title": title or summary or raw_text or "Untitled signal",
        "summary": summary or raw_text or "",
        "source_url": source_url,
        "source_name": source_name or file_path.parent.name,
        "published_at": published_at,
        "captured_at": captured_at,
        "raw_text": raw_text or "",
        "author": _pick_text(record, "author", "author_name", "username"),
        "account": _pick_text(record, "account", "account_name", "screen_name"),
        "metrics": metrics,
        "platform": platform,
        "keyword": keyword,
        "rank": rank,
        "watchlist_hits": watchlist_hits,
        "tags": record.get("tags") if isinstance(record.get("tags"), list) else [],
        "raw_source_type": raw_source_type,
        "raw_payload": record,
        "file_path": str(file_path),
    }


def _pick_text(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _pick_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_metrics(record: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key in ("trending_score", "engagement", "hotness", "likes", "comments", "shares", "hot_score", "score"):
        value = record.get(key)
        if isinstance(value, (int, float)):
            metrics[key] = value
    return metrics


def _parse_multi_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
        separators = ["|", ",", ";"]
        for separator in separators:
            if separator in text:
                return [part.strip() for part in text.split(separator) if part.strip()]
        return [text]
    return [str(value).strip()]


def _batch_sort_key(path: Path) -> tuple[int, ...]:
    search_space = " ".join([path.stem, path.name, path.parent.name])
    for pattern in DATE_PATTERNS:
        match = pattern.search(search_space)
        if not match:
            continue
        token = match.group(1).replace("_", "T").replace(" ", "T").replace("-", "")
        if "T" in token:
            token = token.replace(":", "").replace("T", "")
        token = token.strip()
        try:
            if len(token) == 8:
                parsed = datetime.strptime(token, "%Y%m%d")
            elif len(token) == 14:
                parsed = datetime.strptime(token, "%Y%m%d%H%M%S")
            else:
                continue
            return (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second)
        except ValueError:
            continue
    return (0, 0, 0, 0, 0, 0)


def _row_sort_key(row: dict[str, Any], timestamp_keys: tuple[str, ...]) -> tuple[str, int]:
    for key in timestamp_keys:
        value = row.get(key)
        if value:
            return (str(value), int(row.get("id") or 0))
    return ("", int(row.get("id") or 0))
