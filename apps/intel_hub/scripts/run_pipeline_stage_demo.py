#!/usr/bin/env python3
"""演示 run_pipeline 各阶段日志：读取 MediaCrawler 产出的小红书 JSONL，不经过 fixture。

V2: 支持 --enable-vision（千问 VL 视觉分析），输出评论关联统计和视觉统计。

默认数据目录（相对仓库根）::

    third_party/MediaCrawler/data/xhs/jsonl

用法（仓库根目录）::

    python apps/intel_hub/scripts/run_pipeline_stage_demo.py
    python apps/intel_hub/scripts/run_pipeline_stage_demo.py --enable-vision

指定其它目录::

    python apps/intel_hub/scripts/run_pipeline_stage_demo.py \\
        --mediacrawler-jsonl third_party/MediaCrawler/data/xhs/jsonl

日志需为 INFO 才可见 ``[intel_hub.pipeline]`` 行；本脚本已配置 basicConfig。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_MC_JSONL = REPO_ROOT / "third_party/MediaCrawler/data/xhs/jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="用 MediaCrawler 小红书 JSONL 跑 pipeline 阶段日志演示")
    parser.add_argument(
        "--mediacrawler-jsonl",
        type=Path,
        default=DEFAULT_MC_JSONL,
        help=f"MediaCrawler 小红书 jsonl 目录（默认: {DEFAULT_MC_JSONL.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--enable-vision",
        action="store_true",
        help="启用千问 VL 视觉分析（需要 DASHSCOPE_API_KEY 环境变量）",
    )
    args = parser.parse_args()

    mc_dir = args.mediacrawler_jsonl
    if not mc_dir.is_absolute():
        mc_dir = (REPO_ROOT / mc_dir).resolve()

    if not mc_dir.is_dir():
        print(f"错误: 目录不存在: {mc_dir}", file=sys.stderr)
        print("请先运行 MediaCrawler 完成小红书采集，或传入 --mediacrawler-jsonl", file=sys.stderr)
        return 1

    jsonl_files = list(mc_dir.rglob("*.jsonl"))
    if not jsonl_files:
        print(f"错误: 目录下无 .jsonl 文件: {mc_dir}", file=sys.stderr)
        return 1

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s | %(message)s",
    )
    logging.getLogger("apps.intel_hub.ingest").setLevel(logging.INFO)
    logging.getLogger("apps.intel_hub.workflow").setLevel(logging.INFO)

    tmp = Path(tempfile.mkdtemp(prefix="intel_hub_pipeline_demo_"))
    empty_tr = tmp / "empty_trendradar"
    empty_tr.mkdir(parents=True, exist_ok=True)

    # runtime 内路径相对于仓库根，便于与 resolve_repo_path 一致
    try:
        output_path_rel = mc_dir.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        output_path_rel = mc_dir.as_posix()

    cfg_path = tmp / "runtime_stage_demo.yaml"
    lines = [
        f"trendradar_output_dir: {empty_tr.as_posix()}",
        f"storage_path: {(tmp / 'intel_hub.sqlite').as_posix()}",
        "default_page_size: 20",
        f"raw_snapshot_dir: {(tmp / 'raw').as_posix()}",
        "include_rss: false",
        "fixture_fallback_dir: ''",
        "mediacrawler_sources:",
        "  - enabled: true",
        "    platform: xiaohongshu",
        f"    output_path: {output_path_rel}",
        "xhs_sources: []",
        "xhs_aggregation: {}",
    ]
    cfg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    from apps.intel_hub.config_loader import clear_config_caches
    from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records
    from apps.intel_hub.workflow.refresh_pipeline import run_pipeline

    clear_config_caches()
    print("--- 临时 runtime:", cfg_path, file=sys.stderr)
    print(f"--- MediaCrawler 小红书目录: {mc_dir} ({len(jsonl_files)} 个 .jsonl)", file=sys.stderr)
    if args.enable_vision:
        import os
        has_key = bool(os.environ.get("DASHSCOPE_API_KEY"))
        print(f"--- 千问VL视觉分析: {'已启用' if has_key else '已请求但缺少DASHSCOPE_API_KEY'}", file=sys.stderr)
    else:
        print("--- 千问VL视觉分析: 未启用（用 --enable-vision 开启）", file=sys.stderr)
    print("--- TrendRadar: 空目录（不读 fixture）", file=sys.stderr)
    print("---", file=sys.stderr)

    # 预先加载一次 records 统计评论关联
    preload_records = load_mediacrawler_records(mc_dir)
    _print_comment_stats(preload_records)

    result = run_pipeline(cfg_path, enable_vision=args.enable_vision)

    # 视觉信号统计（从 pipeline 结果中提取）
    _print_visual_stats(result)

    print(
        json.dumps(
            {
                "raw_count": result.raw_count,
                "extraction_count": result.extraction_count,
                "signal_count": result.signal_count,
                "opportunity_count": result.opportunity_count,
                "risk_count": result.risk_count,
                "insight_count": result.insight_count,
                "visual_pattern_count": result.visual_pattern_count,
                "demand_spec_count": result.demand_spec_count,
                "storage_path": str(result.storage_path),
                "mediacrawler_dir": str(mc_dir),
                "enable_vision": args.enable_vision,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _print_comment_stats(records: list[dict]) -> None:
    """输出评论关联统计到 stderr。"""
    total_records = len(records)
    with_comments = [r for r in records if r.get("comments")]
    total_comments = sum(len(r.get("comments", [])) for r in records)
    avg_comments = total_comments / len(with_comments) if with_comments else 0
    with_images = sum(1 for r in records if r.get("image_list"))

    print("", file=sys.stderr)
    print("=== 评论关联统计 ===", file=sys.stderr)
    print(f"  笔记总数: {total_records}", file=sys.stderr)
    print(f"  关联评论笔记数: {len(with_comments)} / {total_records}", file=sys.stderr)
    print(f"  评论总数: {total_comments}", file=sys.stderr)
    print(f"  每笔记平均评论: {avg_comments:.1f}", file=sys.stderr)
    print(f"  含图片笔记数: {with_images} / {total_records}", file=sys.stderr)
    print("", file=sys.stderr)


def _print_visual_stats(result: "PipelineResult") -> None:  # noqa: F821
    """输出视觉相关统计。"""
    print("", file=sys.stderr)
    print("=== 决策资产产出 ===", file=sys.stderr)
    print(f"  Opportunity: {result.opportunity_count}", file=sys.stderr)
    print(f"  Risk:        {result.risk_count}", file=sys.stderr)
    print(f"  Insight:     {result.insight_count}", file=sys.stderr)
    print(f"  VisualPattern: {result.visual_pattern_count}", file=sys.stderr)
    print(f"  DemandSpec:  {result.demand_spec_count}", file=sys.stderr)
    print("", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
