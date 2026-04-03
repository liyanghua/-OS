"""带状态上报的 MediaCrawler 启动入口。

用法: uv run run_with_status.py --platform xhs --lt qrcode --type search
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# append (not insert) so MediaCrawler's own modules take priority
sys.path.append(str(REPO_ROOT))

from apps.intel_hub.workflow.crawl_status import CrawlStatusReporter

import config as mc_config
from media_platform.xhs.core import set_crawl_reporter

reporter = CrawlStatusReporter(
    status_path=str(REPO_ROOT / "data" / "crawl_status.json"),
    platform=mc_config.PLATFORM,
    output_dir=str(Path("data") / mc_config.PLATFORM / "jsonl"),
)
set_crawl_reporter(reporter)

from main import main, async_cleanup, crawler
from tools.app_runner import run


def _force_stop():
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


async def main_with_status():
    try:
        await main()
        reporter.crawl_finished("completed")
    except KeyboardInterrupt:
        reporter.crawl_finished("interrupted")
    except Exception as ex:
        reporter.crawl_finished("failed")
        raise


if __name__ == "__main__":
    run(main_with_status, async_cleanup, cleanup_timeout_seconds=15.0, on_first_interrupt=_force_stop)
