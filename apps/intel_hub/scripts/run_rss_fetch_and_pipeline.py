#!/usr/bin/env python3
"""RSS 抓取 + Pipeline 一键执行脚本。

独立实现 RSS 抓取（feedparser + sqlite3），不依赖 TrendRadar __init__ 导入链。

流程:
  1. 读取 TrendRadar config.yaml 中的 RSS feeds 配置
  2. 用 feedparser 逐个抓取
  3. 存入 TrendRadar output/rss/{date}.db（与 TrendRadar schema 兼容）
  4. 可选：调用 intel_hub refresh_pipeline 走完四层编译链

用法:
  python -m apps.intel_hub.scripts.run_rss_fetch_and_pipeline
  python -m apps.intel_hub.scripts.run_rss_fetch_and_pipeline --skip-pipeline
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sqlite3
import sys
import time as _time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRENDRADAR_ROOT = PROJECT_ROOT / "third_party" / "TrendRadar"

sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("rss_pipeline")

RSS_SCHEMA = """
CREATE TABLE IF NOT EXISTS rss_feeds (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    feed_url TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    last_fetch_time TEXT,
    last_fetch_status TEXT,
    item_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rss_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    feed_id TEXT NOT NULL,
    url TEXT NOT NULL,
    published_at TEXT,
    summary TEXT,
    author TEXT,
    first_crawl_time TEXT NOT NULL,
    last_crawl_time TEXT NOT NULL,
    crawl_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feed_id) REFERENCES rss_feeds(id)
);
CREATE INDEX IF NOT EXISTS idx_rss_feed ON rss_items(feed_id);
CREATE INDEX IF NOT EXISTS idx_rss_published ON rss_items(published_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_rss_url_feed ON rss_items(url, feed_id);
"""


def _load_config() -> dict:
    cfg_path = TRENDRADAR_ROOT / "config" / "config.yaml"
    if not cfg_path.exists():
        log.error("TrendRadar config.yaml 不存在: %s", cfg_path)
        sys.exit(1)
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def _init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(RSS_SCHEMA)
    return conn


def _parse_published(entry: dict) -> str:
    """尝试从 entry 获取 ISO 格式发布时间。"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            from _time import struct_time
        except ImportError:
            pass
        try:
            import calendar
            t = entry.published_parsed
            return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            import calendar
            t = entry.updated_parsed
            return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    return entry.get("published", entry.get("updated", ""))


def step1_fetch_rss(config: dict) -> int:
    """抓取 RSS 并保存到 SQLite，返回总条目数。"""
    rss_cfg = config.get("rss", {})
    if not rss_cfg.get("enabled", False):
        log.warning("TrendRadar config.yaml 中 rss.enabled 为 false，跳过")
        return 0

    feeds = rss_cfg.get("feeds", [])
    enabled_feeds = [f for f in feeds if f.get("enabled", True)]
    log.info("=== Step 1: RSS 抓取 ===")
    log.info("启用源数: %d / %d", len(enabled_feeds), len(feeds))

    today = datetime.now().strftime("%Y-%m-%d")
    crawl_time = datetime.now().strftime("%H:%M")
    storage_cfg = config.get("storage", {})
    output_base = TRENDRADAR_ROOT / storage_cfg.get("data_dir", "output")
    db_path = output_base / "rss" / f"{today}.db"

    conn = _init_db(db_path)
    total_items = 0
    success_count = 0
    fail_count = 0

    for i, feed_cfg in enumerate(enabled_feeds):
        fid = feed_cfg.get("id", "")
        fname = feed_cfg.get("name", fid)
        furl = feed_cfg.get("url", "")
        if not fid or not furl:
            continue

        if i > 0:
            _time.sleep(random.uniform(1.0, 2.5))

        try:
            parsed = feedparser.parse(furl)
            entries = parsed.entries or []
            log.info("[RSS] %s: %d 条", fname, len(entries))

            conn.execute(
                """INSERT OR REPLACE INTO rss_feeds
                   (id, name, feed_url, is_active, last_fetch_time, last_fetch_status, item_count)
                   VALUES (?, ?, ?, 1, ?, 'success', ?)""",
                (fid, fname, furl, crawl_time, len(entries)),
            )

            for entry in entries:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                if not title or not url:
                    continue
                summary = entry.get("summary", "")[:2000] if entry.get("summary") else ""
                author = entry.get("author", "")
                published = _parse_published(entry)

                try:
                    conn.execute(
                        """INSERT INTO rss_items
                           (title, feed_id, url, published_at, summary, author, first_crawl_time, last_crawl_time)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(url, feed_id) DO UPDATE SET
                             last_crawl_time = excluded.last_crawl_time,
                             crawl_count = crawl_count + 1""",
                        (title, fid, url, published, summary, author, crawl_time, crawl_time),
                    )
                    total_items += 1
                except sqlite3.IntegrityError:
                    pass

            conn.commit()
            success_count += 1

        except Exception as exc:
            log.warning("[RSS] %s: 抓取失败 - %s", fname, exc)
            conn.execute(
                """INSERT OR REPLACE INTO rss_feeds
                   (id, name, feed_url, is_active, last_fetch_time, last_fetch_status, item_count)
                   VALUES (?, ?, ?, 1, ?, 'failed', 0)""",
                (fid, fname, furl, crawl_time),
            )
            conn.commit()
            fail_count += 1

    conn.close()
    log.info("抓取完成: %d 个源成功, %d 个失败, 共 %d 条目", success_count, fail_count, total_items)
    log.info("数据已保存: %s", db_path)
    return total_items


def step2_run_pipeline() -> dict:
    """运行 intel_hub pipeline，返回统计。"""
    log.info("=== Step 2: Pipeline 编译 ===")
    from apps.intel_hub.workflow.refresh_pipeline import run_pipeline
    result = run_pipeline(enable_vision=False)
    stats = {
        "signal_count": result.signal_count,
        "opportunity_count": result.opportunity_count,
        "risk_count": result.risk_count,
        "insight_count": getattr(result, "insight_count", 0),
        "visual_pattern_count": getattr(result, "visual_pattern_count", 0),
        "demand_spec_count": getattr(result, "demand_spec_count", 0),
    }
    log.info("Pipeline 完成: %s", json.dumps(stats, ensure_ascii=False))
    return stats


def main():
    parser = argparse.ArgumentParser(description="RSS 抓取 + Pipeline 一键执行")
    parser.add_argument("--skip-pipeline", action="store_true", help="跳过 Pipeline 编译，只抓取 RSS")
    args = parser.parse_args()

    config = _load_config()
    total_items = step1_fetch_rss(config)

    pipeline_stats = {}
    if not args.skip_pipeline and total_items > 0:
        pipeline_stats = step2_run_pipeline()
    elif args.skip_pipeline:
        log.info("已跳过 Pipeline 编译（--skip-pipeline）")
    else:
        log.info("RSS 无新数据，跳过 Pipeline")

    log.info("=== 最终统计 ===")
    log.info("RSS 条目: %d", total_items)
    if pipeline_stats:
        log.info("决策资产: %s", json.dumps(pipeline_stats, ensure_ascii=False))
    log.info("完成！可访问 http://127.0.0.1:8000/rss/tech 和 /rss/news 查看。")


if __name__ == "__main__":
    main()
