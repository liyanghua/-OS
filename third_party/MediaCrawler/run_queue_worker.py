"""Queue Worker — 从 job_queue.json 批量消费采集任务。

批量模式：读取所有 pending keyword_search 任务，合并关键词到一次浏览器会话中执行。
一次 QR 登录覆盖所有关键词，storage_state 导出供后续复用。

用法: uv run run_queue_worker.py
"""
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT))

from apps.intel_hub.workflow.job_queue import FileJobQueue
from apps.intel_hub.workflow.job_models import CrawlJob
from apps.intel_hub.workflow.crawl_status import CrawlStatusReporter
from apps.intel_hub.workflow.alerting import AlertManager

import config as mc_config
from media_platform.xhs.core import set_crawl_reporter
from main import main as mc_main


QUEUE_PATH = str(REPO_ROOT / "data" / "job_queue.json")
STATUS_PATH = str(REPO_ROOT / "data" / "crawl_status.json")


async def worker_main() -> None:
    queue = FileJobQueue(QUEUE_PATH)
    alert_mgr = AlertManager(str(REPO_ROOT / "data" / "alerts.json"))

    # Dequeue all pending keyword_search jobs at once
    jobs_to_process: list[CrawlJob] = []
    while True:
        job = queue.dequeue()
        if not job:
            break
        jobs_to_process.append(job)

    if not jobs_to_process:
        print("没有待处理任务，退出。")
        return

    # Merge all keywords into a single comma-separated string
    all_keywords = []
    for job in jobs_to_process:
        kw = job.payload.get("keywords", "")
        if kw:
            all_keywords.append(kw)
    merged_keywords = ",".join(all_keywords)

    print(f"{'='*60}")
    print(f"批量模式：合并 {len(jobs_to_process)} 个任务")
    print(f"关键词: {merged_keywords}")
    print(f"{'='*60}\n")

    # Use settings from first job
    first = jobs_to_process[0]
    mc_config.KEYWORDS = merged_keywords
    mc_config.CRAWLER_MAX_NOTES_COUNT = first.payload.get("max_notes", 10)
    mc_config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = first.payload.get("max_comments", 10)
    mc_config.CRAWLER_TYPE = "search"
    mc_config.PLATFORM = first.payload.get("platform", "xhs")
    mc_config.LOGIN_TYPE = first.payload.get("login_type", "qrcode")

    reporter = CrawlStatusReporter(
        status_path=STATUS_PATH,
        platform=mc_config.PLATFORM,
        output_dir=str(Path("data") / mc_config.PLATFORM / "jsonl"),
    )
    set_crawl_reporter(reporter)

    try:
        await mc_main()
        reporter.crawl_finished("completed")

        output_dir = str(Path("data") / mc_config.PLATFORM / "jsonl")
        for job in jobs_to_process:
            queue.complete(job.job_id, result_path=output_dir)
        print(f"\n✓ 全部 {len(jobs_to_process)} 个任务完成")

    except Exception as ex:
        reporter.crawl_finished("failed")
        for job in jobs_to_process:
            queue.fail(job.job_id, str(ex))
        alert_mgr.emit_crawl_failure("batch", str(ex))
        print(f"\n✗ 批量任务失败: {ex}")

    # Show final stats
    final = queue.stats()
    completed = final.get("completed", 0)
    failed = final.get("failed", 0) + final.get("dead", 0)
    print(f"\n最终状态: {final}")
    print(f"成功: {completed}, 失败: {failed}")

    if completed > 0:
        print("\n触发 Pipeline 刷新...")
        try:
            from apps.intel_hub.workflow.refresh_pipeline import run_pipeline
            result = run_pipeline()
            print(f"Pipeline 完成: {result}")
        except Exception as ex:
            print(f"Pipeline 失败: {ex}")
            alert_mgr.emit_pipeline_error(str(ex))


if __name__ == "__main__":
    from tools import app_runner
    from main import async_cleanup, crawler

    def _force_stop():
        c = crawler
        if not c:
            return
        cdp_manager = getattr(c, "cdp_manager", None)
        launcher = getattr(cdp_manager, "launcher", None)
        if launcher:
            try:
                launcher.cleanup()
            except Exception:
                pass

    app_runner.run(
        worker_main,
        async_cleanup,
        cleanup_timeout_seconds=15.0,
        on_first_interrupt=_force_stop,
    )
