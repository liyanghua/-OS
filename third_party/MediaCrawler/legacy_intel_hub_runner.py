"""Legacy MediaCrawler runner for intel_hub queue consumption.

这层保持 MediaCrawler 在自己的目录和 .venv 里执行，同时把 intel_hub
需要的状态上报与少量参数覆盖注入进去，等价复用此前验证成功的 main.py 路线。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT))

from apps.intel_hub.workflow.crawl_status import CrawlStatusReporter

import config as mc_config
from media_platform.xhs.core import set_crawl_reporter
from main import async_cleanup, crawler, main
from tools.app_runner import run


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="intel_hub legacy MediaCrawler runner")
    parser.add_argument("--platform", default="xhs")
    parser.add_argument("--lt", default="qrcode")
    parser.add_argument("--type", default="search")
    parser.add_argument("--save_data_option", default="jsonl")
    parser.add_argument("--keywords", default=mc_config.KEYWORDS)
    parser.add_argument("--max_notes", type=int, default=mc_config.CRAWLER_MAX_NOTES_COUNT)
    parser.add_argument(
        "--max_comments",
        type=int,
        default=mc_config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,
    )
    parser.add_argument("--sort_type", default=getattr(mc_config, "SORT_TYPE", "popularity_descending"))
    parser.add_argument("--headless", default=str(mc_config.HEADLESS).lower())
    parser.add_argument("--status_path", required=True)
    parser.add_argument("--session_id", default="")
    return parser


def _apply_args(args: argparse.Namespace) -> CrawlStatusReporter:
    mc_config.PLATFORM = args.platform
    mc_config.LOGIN_TYPE = args.lt
    mc_config.CRAWLER_TYPE = args.type
    mc_config.SAVE_DATA_OPTION = args.save_data_option
    mc_config.KEYWORDS = args.keywords
    mc_config.CRAWLER_MAX_NOTES_COUNT = args.max_notes
    mc_config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = args.max_comments
    mc_config.HEADLESS = _to_bool(str(args.headless))
    mc_config.CDP_HEADLESS = mc_config.HEADLESS
    if hasattr(mc_config, "SORT_TYPE"):
        mc_config.SORT_TYPE = args.sort_type
    mc_config.ENABLE_GET_WORDCLOUD = False

    output_dir = str(Path("data") / mc_config.PLATFORM / "jsonl")
    reporter = CrawlStatusReporter(
        status_path=args.status_path,
        platform=mc_config.PLATFORM,
        output_dir=output_dir,
    )
    if args.session_id:
        reporter.set_session_id(args.session_id)
    set_crawl_reporter(reporter)
    return reporter


def _reset_argv_for_mediacrawler() -> None:
    sys.argv = [sys.argv[0]]


def _force_stop() -> None:
    c = crawler
    if not c:
        return
    cdp_manager = getattr(c, "cdp_manager", None)
    launcher = getattr(cdp_manager, "launcher", None)
    if not launcher:
        return
    try:
        launcher.cleanup()
    except Exception:
        pass


def _main_with_status_factory(reporter: CrawlStatusReporter):
    async def _main_with_status():
        try:
            await main()
            reporter.crawl_finished("completed")
        except KeyboardInterrupt:
            reporter.crawl_finished("interrupted")
        except Exception:
            reporter.crawl_finished("failed")
            raise

    return _main_with_status


def cli() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    reporter = _apply_args(args)
    _reset_argv_for_mediacrawler()
    run(
        _main_with_status_factory(reporter),
        async_cleanup,
        cleanup_timeout_seconds=15.0,
        on_first_interrupt=_force_stop,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
