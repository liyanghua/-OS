"""统一 raw signal 收集路由。

根据 RuntimeSettings 配置决定启用哪些数据源，
依次调用各 loader 并合并返回统一的 raw signal dict 列表。
后续 pipeline 只需调用 ``collect_raw_signals(settings)``。

数据源顺序（合并为单一列表，供 normalize 去重）：
1. TrendRadar（含 RSS 可选）
2. MediaCrawler（``runtime.yaml`` → ``mediacrawler_sources``，如小红书 jsonl 目录）
3. 旧版 xhs_capture（``xhs_sources`` + 聚合）
4. Raw Lake 增量（``data/raw_lake/...``，未 ingested 的 run）

流水线全貌见 ``docs/DATA_PIPELINE_XHS_INTEL_HUB.md``。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from apps.intel_hub.config_loader import RuntimeSettings, resolve_repo_path

logger = logging.getLogger(__name__)

_RAW_LAKE_DIR = "data/raw_lake"


def collect_raw_signals(settings: RuntimeSettings) -> list[dict[str, Any]]:
    """根据配置收集所有源的 raw signals。"""
    raw_records: list[dict[str, Any]] = []

    raw_records.extend(_collect_trendradar(settings))
    raw_records.extend(_collect_mediacrawler(settings))
    raw_records.extend(_collect_xhs_capture(settings))
    raw_records.extend(_collect_raw_lake())

    logger.info(
        "source_router: collected %d total raw records (trendradar + mediacrawler + xhs_capture + raw_lake)",
        len(raw_records),
    )
    return raw_records


def _collect_trendradar(settings: RuntimeSettings) -> list[dict[str, Any]]:
    from apps.intel_hub.ingest.trendradar_loader import load_latest_raw_signals

    output_dir = settings.resolved_output_dir()
    records = load_latest_raw_signals(output_dir, include_rss=settings.include_rss)

    if not records and settings.resolved_fixture_fallback_dir():
        fallback_dir = settings.resolved_fixture_fallback_dir()
        records = load_latest_raw_signals(fallback_dir, include_rss=settings.include_rss)

    logger.info("source_router[trendradar]: %d records", len(records))
    return records


def _collect_mediacrawler(settings: RuntimeSettings) -> list[dict[str, Any]]:
    sources = settings.mediacrawler_sources
    if not sources:
        return []

    from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

    records: list[dict[str, Any]] = []
    for src in sources:
        if not src.get("enabled", True):
            continue
        platform = src.get("platform", "xiaohongshu")
        output_path = src.get("output_path", "")
        resolved = _resolve_source_path(output_path)

        loaded = load_mediacrawler_records(resolved, platform=platform)
        if not loaded:
            fallback = src.get("fixture_fallback", "")
            if fallback:
                fallback_resolved = _resolve_source_path(fallback)
                loaded = load_mediacrawler_records(fallback_resolved, platform=platform)
                if loaded:
                    logger.info(
                        "source_router[mediacrawler]: used fixture fallback %s (%d records)",
                        fallback_resolved,
                        len(loaded),
                    )

        records.extend(loaded)

    logger.info("source_router[mediacrawler]: %d records total", len(records))
    return records


def _collect_xhs_capture(settings: RuntimeSettings) -> list[dict[str, Any]]:
    """保留对旧 xhs_loader + xhs_aggregator 路径的兼容。"""
    if not settings.xhs_sources:
        return []

    from apps.intel_hub.ingest.xhs_aggregator import aggregate_comments_to_signals
    from apps.intel_hub.ingest.xhs_loader import load_xhs_raw_signals

    xhs_raw = load_xhs_raw_signals(settings.xhs_sources)
    if not xhs_raw:
        return []

    records = aggregate_comments_to_signals(xhs_raw, settings.xhs_aggregation)
    logger.info("source_router[xhs_capture]: %d aggregated records", len(records))
    return records


def _resolve_source_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return resolve_repo_path(path_str)


def _collect_raw_lake() -> list[dict[str, Any]]:
    """Phase 4: 扫描 data/raw_lake/ 目录，增量加载未处理的 run。

    目录结构: data/raw_lake/{platform}/{date}/{run_id}/
        notes.jsonl
        comments.jsonl
        metadata.json  (含 ingested: bool 标记)
    """
    lake_dir = resolve_repo_path(_RAW_LAKE_DIR)
    if not lake_dir.exists():
        return []

    from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

    records: list[dict[str, Any]] = []

    for platform_dir in sorted(lake_dir.iterdir()):
        if not platform_dir.is_dir():
            continue
        platform = platform_dir.name

        for date_dir in sorted(platform_dir.iterdir()):
            if not date_dir.is_dir():
                continue

            for run_dir in sorted(date_dir.iterdir()):
                if not run_dir.is_dir():
                    continue

                meta_path = run_dir / "metadata.json"
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        if meta.get("ingested", False):
                            continue
                    except Exception:
                        pass

                notes_path = run_dir / "notes.jsonl"
                if notes_path.exists():
                    loaded = load_mediacrawler_records(notes_path, platform=platform)
                    records.extend(loaded)

                _mark_run_ingested(meta_path, run_dir)

    if records:
        logger.info("source_router[raw_lake]: %d records from new runs", len(records))
    return records


def _mark_run_ingested(meta_path: Path, run_dir: Path) -> None:
    """标记一个 raw_lake run 为已处理。"""
    try:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            meta = {"run_dir": str(run_dir)}
        meta["ingested"] = True
        meta["ingested_at"] = __import__("datetime").datetime.now(
            tz=__import__("datetime").timezone.utc
        ).isoformat()
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as ex:
        logger.warning(f"source_router: failed to mark run ingested: {ex}")
