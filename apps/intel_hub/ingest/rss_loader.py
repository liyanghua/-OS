"""RSS 数据加载器 — 供 UI 原生浏览页使用。

直读 TrendRadar ``output/rss/{date}.db`` 中的 rss_items + rss_feeds 表，
返回完整字段（title, link, summary, published, feed_name, feed_url, category）。

category 由 config/rss_feeds_tech.yaml 和 config/rss_feeds_news.yaml 中的
feed_id → category 映射决定。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "third_party" / "TrendRadar" / "output" / "rss"
_TECH_CONFIG = _PROJECT_ROOT / "config" / "rss_feeds_tech.yaml"
_NEWS_CONFIG = _PROJECT_ROOT / "config" / "rss_feeds_news.yaml"

_category_cache: dict[str, str] | None = None


def _build_category_map() -> dict[str, str]:
    """从 config yaml 构建 {feed_id: category} 映射。"""
    global _category_cache
    if _category_cache is not None:
        return _category_cache

    mapping: dict[str, str] = {}
    for cfg_path in (_TECH_CONFIG, _NEWS_CONFIG):
        if not cfg_path.exists():
            continue
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        for feed in data.get("feeds", []):
            fid = feed.get("id", "")
            cat = feed.get("category", "tech")
            if fid:
                mapping[fid] = cat
    _category_cache = mapping
    return mapping


def _find_latest_rss_db(output_dir: Path) -> Path | None:
    """在 output_dir 下找到按文件名日期最新的 .db 文件。"""
    if not output_dir.exists():
        return None
    dbs = sorted(output_dir.glob("*.db"), key=lambda p: p.name, reverse=True)
    return dbs[0] if dbs else None


def load_rss_records(
    output_dir: Path | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """加载 RSS 条目，可按 category ('tech' / 'news') 过滤。

    Returns
    -------
    list[dict]
        每条包含: id, title, link, summary, published_at, author,
        feed_id, feed_name, feed_url, category, first_crawl_time
    """
    rss_dir = output_dir or _DEFAULT_OUTPUT_DIR
    db_path = _find_latest_rss_db(rss_dir)
    if db_path is None:
        return []

    cat_map = _build_category_map()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "rss_items" not in tables:
            return []

        feed_map: dict[str, dict[str, Any]] = {}
        if "rss_feeds" in tables:
            for row in conn.execute("SELECT * FROM rss_feeds").fetchall():
                feed_map[row["id"]] = dict(row)

        rows = conn.execute(
            "SELECT * FROM rss_items ORDER BY published_at DESC, id DESC"
        ).fetchall()

    records: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        fid = item.get("feed_id", "")
        feed_info = feed_map.get(fid, {})
        item_cat = cat_map.get(fid, "tech")

        if category and item_cat != category:
            continue

        records.append({
            "id": item.get("id"),
            "title": item.get("title", ""),
            "link": item.get("url", ""),
            "summary": item.get("summary", ""),
            "published_at": item.get("published_at", ""),
            "author": item.get("author", ""),
            "feed_id": fid,
            "feed_name": feed_info.get("name", fid),
            "feed_url": feed_info.get("feed_url", ""),
            "category": item_cat,
            "first_crawl_time": item.get("first_crawl_time", ""),
        })

    return records


def count_rss_records(
    output_dir: Path | None = None,
) -> dict[str, int]:
    """返回 {'tech': N, 'news': M, 'total': N+M}。"""
    all_records = load_rss_records(output_dir=output_dir)
    tech = sum(1 for r in all_records if r["category"] == "tech")
    news = sum(1 for r in all_records if r["category"] == "news")
    return {"tech": tech, "news": news, "total": tech + news}
