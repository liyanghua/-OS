"""bootstrap_data.py — 客户侧数据迁移落地的 Python 子 CLI。

由 ``scripts/bootstrap_data.sh`` 调用，但也可以手动单独运行：

    python -m apps.intel_hub.scripts.bootstrap_data summary
    python -m apps.intel_hub.scripts.bootstrap_data validate
    python -m apps.intel_hub.scripts.bootstrap_data sync-cards

子命令：
- ``summary``        : 打印当前各 SQLite 关键表行数 / JSON 文件大小，便于核验导入是否成功。
- ``validate``       : 校验关键文件存在 + sqlite 可连通 + 关键表存在；非零退出码代表异常。
- ``sync-cards``     : 把 ``data/output/xhs_opportunities/opportunity_cards.json`` 写入
                        ``data/xhs_review.sqlite``（等价于主站启动时的 sync 行为，但不需要起服务）。

设计原则：
- 路径通过 ``apps.intel_hub.config_loader.resolve_repo_path`` 解析，与主站一致。
- 出现异常时仍尽量打印能完成的部分，最终用退出码体现成功/失败。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from apps.intel_hub.config_loader import (
    load_runtime_settings,
    resolve_repo_path,
)
from apps.intel_hub.storage.xhs_review_store import XHSReviewStore


# 与 ``apps/intel_hub/api/app.py::create_app`` 对齐的关键路径表。
_SQLITE_TABLES: list[tuple[str, list[str]]] = [
    ("data/intel_hub.sqlite", ["opportunity_cards", "signals", "evidence_refs"]),
    ("data/xhs_review.sqlite", ["xhs_opportunity_cards", "xhs_reviews"]),
    (
        "data/content_plan.sqlite",
        ["planning_sessions", "rule_specs", "rule_packs", "context_specs"],
    ),
    (
        "data/growth_lab.sqlite",
        [
            "workspace_plans",
            "visual_strategy_packs",
            "strategy_candidates",
            "creative_briefs",
            "prompt_specs",
            "note_packs",
            "visual_feedback_records",
        ],
    ),
    ("data/b2b_platform.sqlite", ["organizations", "workspaces"]),
    ("data/agent_memory.sqlite", []),  # 表名动态，仅检查文件可连通
]

_KEY_JSON_FILES: list[str] = [
    "data/output/xhs_opportunities/opportunity_cards.json",
    "data/output/xhs_opportunities/pipeline_details.json",
]


def _row_count(db_path: Path, table: str) -> int | str:
    if not db_path.exists():
        return "missing"
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except sqlite3.OperationalError as exc:
        return f"err:{exc}"
    except Exception as exc:  # noqa: BLE001
        return f"err:{type(exc).__name__}"


def _file_size(path: Path) -> int | str:
    if not path.exists():
        return "missing"
    try:
        return path.stat().st_size
    except OSError as exc:
        return f"err:{exc}"


def cmd_summary(_args: argparse.Namespace) -> int:
    """打印 sqlite 行数 + JSON 大小汇总，便于人工核验。"""
    print("=== SQLite rows ===")
    for rel, tables in _SQLITE_TABLES:
        db_path = resolve_repo_path(rel)
        if not tables:
            present = "exists" if db_path.exists() else "missing"
            print(f"  {rel:42s}  [{present}]")
            continue
        for tbl in tables:
            count = _row_count(db_path, tbl)
            print(f"  {rel:42s}  {tbl:30s}  {count}")

    print("\n=== JSON files ===")
    for rel in _KEY_JSON_FILES:
        path = resolve_repo_path(rel)
        size = _file_size(path)
        if isinstance(size, int):
            kb = size / 1024
            print(f"  {rel:60s}  {kb:8.1f} KB")
        else:
            print(f"  {rel:60s}  [{size}]")

    print("\n=== Runtime config ===")
    try:
        settings = load_runtime_settings()
        print(f"  storage_path           : {settings.resolved_storage_path()}")
        print(f"  trendradar_output_dir  : {settings.resolved_output_dir()}")
        print(f"  fixture_fallback_dir   : {settings.resolved_fixture_fallback_dir()}")
        print(f"  raw_snapshot_dir       : {settings.resolved_raw_snapshot_dir()}")
        for src in settings.mediacrawler_sources:
            out = src.get("output_path", "")
            fb = src.get("fixture_fallback", "")
            present = "OK" if (out and resolve_repo_path(out).exists()) else (
                "fallback" if fb and resolve_repo_path(fb).exists() else "missing"
            )
            plat = src.get("platform", "")
            print(f"  mediacrawler[{plat}]   : {out}  [{present}]")
    except Exception as exc:  # noqa: BLE001
        print(f"  (load_runtime_settings 失败：{exc})")
    return 0


def cmd_validate(_args: argparse.Namespace) -> int:
    """硬性校验：缺关键 sqlite 文件或表不存在则非零退出。"""
    fatal = False
    for rel, tables in _SQLITE_TABLES:
        db_path = resolve_repo_path(rel)
        if not db_path.exists():
            # agent_memory 缺失允许；其他必有
            if "agent_memory" in rel:
                continue
            print(f"[FAIL] 缺少 SQLite: {rel}", file=sys.stderr)
            fatal = True
            continue
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("SELECT 1")
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] 无法连接 {rel}: {exc}", file=sys.stderr)
            fatal = True
            continue
        # 表存在性
        for tbl in tables:
            count = _row_count(db_path, tbl)
            if isinstance(count, str) and count.startswith("err"):
                print(f"[FAIL] {rel} 表缺失或异常: {tbl} -> {count}", file=sys.stderr)
                fatal = True

    if fatal:
        return 2
    print("[ OK ] 关键 SQLite + 表均可连通")
    return 0


def cmd_sync_cards(_args: argparse.Namespace) -> int:
    """把 opportunity_cards.json 写入 xhs_review.sqlite（与主站启动行为等价）。"""
    cards_json = resolve_repo_path("data/output/xhs_opportunities/opportunity_cards.json")
    if not cards_json.exists():
        # 兼容老路径
        legacy = resolve_repo_path("data/opportunity_cards.json")
        if legacy.exists():
            cards_json = legacy
    if not cards_json.exists():
        print(f"[WARN] 未找到 opportunity_cards.json，跳过 sync", file=sys.stderr)
        return 1

    db_path = resolve_repo_path("data/xhs_review.sqlite")
    store = XHSReviewStore(db_path)
    try:
        n = store.sync_cards_from_json(cards_json)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] sync_cards_from_json 失败: {exc}", file=sys.stderr)
        return 3
    print(f"[ OK ] sync_cards_from_json -> {n} 张机会卡 写入 {db_path}")
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    """读取 manifest.json 与本地实际行数做差异比对。"""
    manifest_path = Path(args.path)
    if not manifest_path.exists():
        print(f"[FAIL] manifest 不存在: {manifest_path}", file=sys.stderr)
        return 4
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = payload.get("sqlite_rows", {})
    print(f"manifest exported_at={payload.get('exported_at')} commit={payload.get('git_commit')}")
    diff = 0
    for key, exp in expected.items():
        if "::" not in key:
            continue
        rel, tbl = key.split("::", 1)
        actual = _row_count(resolve_repo_path(rel), tbl)
        marker = "OK" if str(actual) == str(exp) else "DIFF"
        if marker == "DIFF":
            diff += 1
        print(f"  [{marker}] {key}: expected={exp} actual={actual}")
    if diff:
        print(f"[WARN] 共 {diff} 项与 manifest 不一致（可能是导入后还做过操作）", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="客户侧数据迁移辅助 CLI（行数汇总 / 校验 / 机会卡 sync）"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("summary", help="打印 sqlite 行数与 JSON 大小")
    sub.add_parser("validate", help="校验关键 SQLite 与表连通性")
    sub.add_parser("sync-cards", help="把 opportunity_cards.json 写入 xhs_review.sqlite")

    p_man = sub.add_parser("manifest", help="对比 manifest.json 与本地实际行数")
    p_man.add_argument("path", help="manifest.json 路径")

    args = parser.parse_args(argv)

    handlers = {
        "summary": cmd_summary,
        "validate": cmd_validate,
        "sync-cards": cmd_sync_cards,
        "manifest": cmd_manifest,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
