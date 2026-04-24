"""MediaCrawler legacy crawl command helpers.

保持 intel_hub 侧只负责构造并启动 MediaCrawler 原生运行环境里的子进程，
不在主应用 Python 进程内直接 import MediaCrawler 依赖。
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
from pathlib import Path
from typing import Sequence


logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
MC_ROOT = REPO_ROOT / "third_party" / "MediaCrawler"
MC_VENV_PYTHON = MC_ROOT / ".venv" / "bin" / "python"
MC_LEGACY_RUNNER = MC_ROOT / "legacy_intel_hub_runner.py"


def _bool_flag(value: bool) -> str:
    return "true" if value else "false"


def build_legacy_crawl_command(
    *,
    platform: str,
    keywords: str,
    login_type: str,
    max_notes: int,
    max_comments: int,
    sort_type: str,
    headless: bool,
    status_path: str | Path,
    session_id: str = "",
) -> list[str]:
    """Build the subprocess command that reuses the known-good MediaCrawler route."""
    command = [
        str(MC_VENV_PYTHON),
        str(MC_LEGACY_RUNNER),
        "--platform",
        platform,
        "--lt",
        login_type,
        "--type",
        "search",
        "--save_data_option",
        "jsonl",
        "--keywords",
        keywords,
        "--max_notes",
        str(max_notes),
        "--max_comments",
        str(max_comments),
        "--sort_type",
        sort_type,
        "--headless",
        _bool_flag(headless),
        "--status_path",
        str(status_path),
    ]
    if session_id:
        command.extend(["--session_id", session_id])
    return command


def run_crawl_subprocess(
    *,
    platform: str,
    keywords: str,
    login_type: str = "qrcode",
    max_notes: int = 20,
    max_comments: int = 10,
    sort_type: str = "popularity_descending",
    headless: bool = False,
    status_path: str | Path,
    session_id: str = "",
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    """Launch MediaCrawler in its own venv/workdir using the legacy route."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    command = build_legacy_crawl_command(
        platform=platform,
        keywords=keywords,
        login_type=login_type,
        max_notes=max_notes,
        max_comments=max_comments,
        sort_type=sort_type,
        headless=headless,
        status_path=status_path,
        session_id=session_id,
    )
    logger.info("[crawl_runner] Starting legacy MediaCrawler route: keywords=%s", keywords)
    return subprocess.Popen(command, cwd=str(MC_ROOT), env=env)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MediaCrawler legacy crawl command launcher")
    parser.add_argument("--platform", default="xhs")
    parser.add_argument("--keywords", default="桌布,餐桌布,防水桌布")
    parser.add_argument("--login-type", default="qrcode")
    parser.add_argument("--max-notes", type=int, default=20)
    parser.add_argument("--max-comments", type=int, default=10)
    parser.add_argument("--sort-type", default="popularity_descending")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--status-path", default=str(REPO_ROOT / "data" / "crawl_status.json"))
    parser.add_argument("--session-id", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    process = run_crawl_subprocess(
        platform=args.platform,
        keywords=args.keywords,
        login_type=args.login_type,
        max_notes=args.max_notes,
        max_comments=args.max_comments,
        sort_type=args.sort_type,
        headless=args.headless,
        status_path=args.status_path,
        session_id=args.session_id,
    )
    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
