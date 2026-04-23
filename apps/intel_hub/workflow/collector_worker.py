"""采集 Worker — 从队列消费任务并调用 MediaCrawler 执行。

职责链：dequeue -> load session -> configure MC -> run crawl -> write raw -> release session -> update job。
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

from .job_models import CrawlJob
from .job_queue import FileJobQueue
from .crawl_status import CrawlStatusReporter
from .session_service import SessionService
from .alerting import AlertManager

logger = logging.getLogger("collector_worker")

REPO_ROOT = Path(__file__).resolve().parents[3]
MC_ROOT = REPO_ROOT / "third_party" / "MediaCrawler"


def _ensure_mc_on_path() -> None:
    mc_str = str(MC_ROOT)
    if mc_str not in sys.path:
        sys.path.append(mc_str)


async def execute_keyword_search(
    job: CrawlJob,
    reporter: CrawlStatusReporter | None = None,
    session_service: SessionService | None = None,
) -> str | None:
    """执行关键词搜索任务，返回 output 目录路径。"""
    _ensure_mc_on_path()

    import config as mc_config  # type: ignore
    from media_platform.xhs.core import set_crawl_reporter  # type: ignore
    from main import main as mc_main  # type: ignore

    payload = job.payload
    mc_config.KEYWORDS = payload.get("keywords", mc_config.KEYWORDS)
    mc_config.CRAWLER_MAX_NOTES_COUNT = payload.get("max_notes", 20)
    mc_config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = payload.get("max_comments", 10)
    mc_config.CRAWLER_TYPE = "search"
    mc_config.PLATFORM = payload.get("platform", "xhs")
    mc_config.LOGIN_TYPE = payload.get("login_type", "qrcode")
    mc_config.SORT_TYPE = payload.get("sort_type", getattr(mc_config, "SORT_TYPE", "popularity_descending"))

    account_id: str | None = None
    if session_service:
        session = session_service.acquire_session(mc_config.PLATFORM)
        if session:
            account_id = session.account_id
            logger.info(f"[collector_worker] Acquired session: {account_id}")
            if reporter:
                reporter.set_session_id(account_id)

    if reporter:
        set_crawl_reporter(reporter)

    try:
        await mc_main()
        output_dir = str(MC_ROOT / "data" / mc_config.PLATFORM / "jsonl")

        if session_service and account_id:
            session_service.release_session(account_id, success=True)

        return output_dir

    except Exception as ex:
        logger.error(f"[collector_worker] Crawl failed: {ex}")
        if session_service and account_id:
            session_service.release_session(account_id, success=False, error=str(ex))
        raise


async def process_one_job(
    queue: FileJobQueue,
    session_service: SessionService | None = None,
    status_path: str | Path = "data/crawl_status.json",
) -> bool:
    """从队列取一个任务执行，返回是否处理了任务。"""
    job = queue.dequeue()
    if not job:
        return False

    logger.info(f"[collector_worker] Processing job {job.job_id} ({job.job_type})")

    reporter = CrawlStatusReporter(
        status_path=status_path,
        platform=job.platform,
        output_dir="",
    )

    alert_mgr = AlertManager()
    try:
        if job.job_type == "keyword_search":
            result_path = await execute_keyword_search(
                job, reporter=reporter, session_service=session_service
            )
            queue.complete(job.job_id, result_path=result_path)
            reporter.crawl_finished("completed")

            # Phase 4.2: auto-trigger pipeline if no more pending keyword_search jobs
            pending = queue.list_jobs(status="pending")
            has_pending_crawl = any(j.job_type == "keyword_search" for j in pending)
            if not has_pending_crawl:
                logger.info("[collector_worker] All crawl jobs done, enqueuing pipeline_refresh")
                refresh_job = CrawlJob(
                    job_type="pipeline_refresh",
                    platform=job.platform,
                    priority=0,
                )
                queue.enqueue(refresh_job)

        elif job.job_type == "pipeline_refresh":
            from .refresh_pipeline import run_pipeline  # type: ignore
            await asyncio.to_thread(run_pipeline)
            queue.complete(job.job_id)
            reporter.crawl_finished("completed")
        else:
            queue.fail(job.job_id, f"Unknown job_type: {job.job_type}")
            reporter.crawl_finished("failed")

    except Exception as ex:
        queue.fail(job.job_id, str(ex))
        reporter.crawl_finished("failed")
        alert_mgr.emit_crawl_failure(job.job_id, str(ex))
        logger.error(f"[collector_worker] Job {job.job_id} failed: {ex}")

    return True


async def worker_loop(
    queue: FileJobQueue,
    session_service: SessionService | None = None,
    poll_interval: float = 10.0,
    max_jobs: int | None = None,
) -> None:
    """持续轮询队列处理任务。"""
    processed = 0
    logger.info("[collector_worker] Worker loop started")

    while True:
        try:
            did_work = await process_one_job(queue, session_service)
            if did_work:
                processed += 1
                if max_jobs and processed >= max_jobs:
                    logger.info(f"[collector_worker] Reached max_jobs={max_jobs}, stopping")
                    break
            else:
                await asyncio.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("[collector_worker] Interrupted, stopping")
            break
        except Exception as ex:
            logger.error(f"[collector_worker] Unexpected error: {ex}")
            await asyncio.sleep(poll_interval)
