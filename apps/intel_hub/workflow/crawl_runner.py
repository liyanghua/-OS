"""MediaCrawler 抓取入口包装脚本。

职责：
1. 初始化 CrawlStatusReporter 并注入到 MediaCrawler
2. 以 subprocess 方式启动抓取（复用 MediaCrawler 的 uv run 入口）
3. 或以 in-process 方式直接调用 MediaCrawler main（需同 venv）
4. 抓取完成后可选自动触发 refresh_pipeline

CLI: python -m apps.intel_hub.workflow.crawl_runner --keywords "桌布,餐桌布"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
MEDIACRAWLER_DIR = REPO_ROOT / "third_party" / "MediaCrawler"
STATUS_PATH = REPO_ROOT / "data" / "crawl_status.json"


def _resolve_output_dir(platform: str = "xhs") -> str:
    return str(MEDIACRAWLER_DIR / "data" / platform / "jsonl")


def run_crawl(
    keywords: str = "桌布,餐桌布,防水桌布",
    platform: str = "xhs",
    login_type: str = "qrcode",
    max_notes: int = 5,
    max_comments: int = 5,
    auto_pipeline: bool = False,
) -> None:
    """运行 MediaCrawler 抓取并上报状态。"""
    from apps.intel_hub.workflow.crawl_status import CrawlStatusReporter

    reporter = CrawlStatusReporter(
        status_path=STATUS_PATH,
        platform=platform,
        output_dir=_resolve_output_dir(platform),
    )

    sys.path.insert(0, str(MEDIACRAWLER_DIR))

    try:
        import config as mc_config
        mc_config.PLATFORM = platform
        mc_config.KEYWORDS = keywords
        mc_config.LOGIN_TYPE = login_type
        mc_config.CRAWLER_TYPE = "search"
        mc_config.SAVE_DATA_OPTION = "jsonl"
        mc_config.CRAWLER_MAX_NOTES_COUNT = max_notes
        mc_config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = max_comments
        mc_config.HEADLESS = False

        from media_platform.xhs.core import set_crawl_reporter
        set_crawl_reporter(reporter)

        from main import main as mc_main

        logger.info("[crawl_runner] Starting MediaCrawler crawl: keywords=%s", keywords)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mc_main())
            reporter.crawl_finished("completed")
            logger.info("[crawl_runner] Crawl completed successfully")
        except KeyboardInterrupt:
            reporter.crawl_finished("interrupted")
            logger.warning("[crawl_runner] Crawl interrupted by user")
        except Exception as ex:
            reporter.crawl_finished("failed")
            logger.error("[crawl_runner] Crawl failed: %s", ex)
        finally:
            loop.close()

    except ImportError as ex:
        reporter.crawl_finished("failed")
        logger.error("[crawl_runner] Failed to import MediaCrawler: %s", ex)
        return
    finally:
        if str(MEDIACRAWLER_DIR) in sys.path:
            sys.path.remove(str(MEDIACRAWLER_DIR))

    if auto_pipeline:
        logger.info("[crawl_runner] Auto-triggering refresh_pipeline ...")
        try:
            from apps.intel_hub.workflow.refresh_pipeline import run_pipeline
            result = run_pipeline()
            logger.info(
                "[crawl_runner] Pipeline done: %d signals, %d opportunities, %d risks",
                result.signal_count, result.opportunity_count, result.risk_count,
            )
        except Exception as ex:
            logger.error("[crawl_runner] Pipeline failed: %s", ex)


def main() -> None:
    parser = argparse.ArgumentParser(description="MediaCrawler 抓取入口")
    parser.add_argument("--keywords", default="桌布,餐桌布,防水桌布", help="逗号分隔的关键词")
    parser.add_argument("--platform", default="xhs", help="平台 (xhs)")
    parser.add_argument("--login-type", default="qrcode", help="登录方式 (qrcode/phone/cookie)")
    parser.add_argument("--max-notes", type=int, default=5, help="每个关键词最大笔记数")
    parser.add_argument("--max-comments", type=int, default=5, help="每条笔记最大评论数")
    parser.add_argument("--auto-pipeline", action="store_true", help="抓取完成后自动运行 pipeline")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    run_crawl(
        keywords=args.keywords,
        platform=args.platform,
        login_type=args.login_type,
        max_notes=args.max_notes,
        max_comments=args.max_comments,
        auto_pipeline=args.auto_pipeline,
    )


if __name__ == "__main__":
    main()
