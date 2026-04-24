"""采集 Worker — 从队列消费任务并调用 MediaCrawler 执行。

职责链：dequeue -> load session -> configure MC -> run crawl -> write raw -> release session -> update job。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from .crawl_runner import MC_ROOT, build_legacy_crawl_command
from .job_models import CrawlJob
from .job_queue import FileJobQueue
from .crawl_status import CrawlStatusReporter
from .session_service import SessionService
from .alerting import AlertManager

logger = logging.getLogger("collector_worker")

REPO_ROOT = Path(__file__).resolve().parents[3]


def _status_path_for_platform(base_status_path: str | Path, platform: str) -> Path:
    base = Path(base_status_path)
    normalized = (platform or "xhs").strip().lower()
    if not normalized:
        normalized = "xhs"
    return base.with_name(f"{base.stem}_{normalized}{base.suffix or '.json'}")


def _pipeline_status_path_for_platform(base_status_path: str | Path, platform: str) -> Path:
    """Return a platform-scoped status file dedicated to pipeline_refresh jobs.

    Keeps pipeline_refresh from overwriting the crawl_status_<platform>.json that
    keyword_search has just populated (otherwise the UI shows the crawl as
    "completed in ~1s with 0 keywords").
    """
    base = Path(base_status_path)
    normalized = (platform or "xhs").strip().lower() or "xhs"
    suffix = base.suffix or ".json"
    # 保持 stem 前缀与 crawl_status_<platform>.json 对齐，换成 pipeline_status_* 即可
    return base.with_name(f"pipeline_status_{normalized}{suffix}")


def _crawl_log_path(job_id: str) -> Path:
    log_dir = REPO_ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"crawl_{job_id}.log"


def _mediacrawler_dependency_paths() -> list[Path]:
    """Return MediaCrawler code root plus its vendored venv site-packages."""
    dependency_paths = [MC_ROOT]
    venv_lib = MC_ROOT / ".venv" / "lib"
    if venv_lib.exists():
        dependency_paths.extend(
            path
            for path in sorted(venv_lib.glob("python*/site-packages"))
            if path.is_dir()
        )
    return dependency_paths


def _ensure_mc_on_path() -> None:
    for dependency_path in _mediacrawler_dependency_paths():
        path_str = str(dependency_path)
        if path_str not in sys.path:
            # Append after the current app venv so local 3.14-compatible wheels
            # still win over MediaCrawler's bundled 3.11 packages.
            sys.path.append(path_str)


def _reporter_still_owns_status(reporter: CrawlStatusReporter | None) -> bool:
    if reporter is None or not reporter.path.exists():
        return True
    try:
        payload = json.loads(reporter.path.read_text(encoding="utf-8"))
    except Exception:
        return True
    return payload.get("run_id") == reporter.status.run_id


async def execute_keyword_search(
    job: CrawlJob,
    queue: FileJobQueue | None = None,
    reporter: CrawlStatusReporter | None = None,
    session_service: SessionService | None = None,
) -> str | None:
    """执行关键词搜索任务，返回 output 目录路径。"""
    payload = job.payload
    platform = str(job.platform or payload.get("platform", "xhs") or "xhs")
    output_dir = str(MC_ROOT / "data" / platform / "jsonl")

    account_id: str | None = None
    if session_service:
        session = session_service.acquire_session(platform)
        if session:
            account_id = session.account_id
            logger.info(f"[collector_worker] Acquired session: {account_id}")
            if reporter:
                reporter.set_session_id(account_id)

    if queue:
        queue.touch_heartbeat(job.job_id)

    log_path = _crawl_log_path(job.job_id)
    try:
        command = build_legacy_crawl_command(
            platform=platform,
            keywords=str(payload.get("keywords", "")),
            login_type=str(payload.get("login_type", "qrcode")),
            max_notes=int(payload.get("max_notes", 20)),
            max_comments=int(payload.get("max_comments", 10)),
            sort_type=str(payload.get("sort_type", "popularity_descending")),
            headless=bool(payload.get("headless", False)),
            status_path=str(reporter.path if reporter else REPO_ROOT / "data" / "crawl_status.json"),
            session_id=account_id or "",
        )
        # stdout/stderr 重定向到独立日志文件，便于排查 "浏览器弹出就关" 这类静默退出；
        # start_new_session=True 让子进程独立于 uvicorn 的进程组，避免 --reload 触发信号级联杀子
        with log_path.open("ab") as log_fp:
            logger.info(
                f"[collector_worker] Launching MediaCrawler for job={job.job_id} (log: {log_path})"
            )
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(MC_ROOT),
                env=dict(os.environ),
                stdout=log_fp,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
            while True:
                return_code = await process.wait()
                if queue:
                    queue.touch_heartbeat(job.job_id)
                if return_code is not None:
                    break
        if return_code != 0:
            raise RuntimeError(
                f"MediaCrawler exited with code {return_code} (log: {log_path})"
            )
        if queue:
            queue.touch_heartbeat(job.job_id)

        if session_service and account_id:
            session_service.release_session(account_id, success=True)

        return output_dir

    except Exception as ex:
        logger.error(f"[collector_worker] Crawl failed: {ex} (log: {log_path})")
        if queue:
            queue.touch_heartbeat(job.job_id)
        if session_service and account_id:
            session_service.release_session(account_id, success=False, error=str(ex))
        raise


async def process_one_job(
    queue: FileJobQueue,
    session_service: SessionService | None = None,
    status_path: str | Path = "data/crawl_status.json",
    alerts_path: str | Path = "data/alerts.json",
    runtime_config_path: str | Path | None = None,
) -> bool:
    """从队列取一个任务执行，返回是否处理了任务。"""
    job = queue.dequeue()
    if not job:
        return False

    logger.info(f"[collector_worker] Processing job {job.job_id} ({job.job_type})")

    # pipeline_refresh 不再写 crawl_status_<platform>.json（否则会把刚刚由 MediaCrawler
    # 子进程写入的 keyword_search 状态瞬间覆盖为 "0 keyword, 1.1s completed"）。
    if job.job_type == "pipeline_refresh":
        reporter_status_path = _pipeline_status_path_for_platform(status_path, job.platform)
    else:
        reporter_status_path = _status_path_for_platform(status_path, job.platform)
    reporter = CrawlStatusReporter(
        status_path=reporter_status_path,
        platform=job.platform,
        output_dir="",
    )

    alert_mgr = AlertManager(alerts_path)
    try:
        if job.job_type == "keyword_search":
            result_path = await execute_keyword_search(
                job, queue=queue, reporter=reporter, session_service=session_service
            )
            queue.complete(job.job_id, result_path=result_path)
            if _reporter_still_owns_status(reporter):
                reporter.crawl_finished("completed")

            refresh_job = queue.ensure_pipeline_job(
                job_group_id=job.job_group_id,
                platform=job.platform,
                display_keyword=job.display_keyword,
                priority=0,
            )
            if refresh_job:
                logger.info("[collector_worker] All crawl jobs done, enqueuing pipeline_refresh")

        elif job.job_type == "pipeline_refresh":
            from .refresh_pipeline import run_pipeline  # type: ignore
            queue.touch_heartbeat(job.job_id)
            await asyncio.to_thread(run_pipeline, runtime_config_path)
            queue.touch_heartbeat(job.job_id)
            queue.complete(job.job_id)
            reporter.crawl_finished("completed")
        else:
            queue.fail(job.job_id, f"Unknown job_type: {job.job_type}")
            reporter.crawl_finished("failed")

    except Exception as ex:
        queue.fail(job.job_id, str(ex))
        if job.job_type != "keyword_search" or _reporter_still_owns_status(reporter):
            reporter.crawl_finished("failed")
        alert_mgr.emit_crawl_failure(job.job_id, str(ex))
        if job.job_type == "keyword_search":
            queue.ensure_pipeline_job(
                job_group_id=job.job_group_id,
                platform=job.platform,
                display_keyword=job.display_keyword,
                priority=0,
            )
        logger.error(f"[collector_worker] Job {job.job_id} failed: {ex}")

    return True


async def worker_loop(
    queue: FileJobQueue,
    session_service: SessionService | None = None,
    poll_interval: float = 10.0,
    max_jobs: int | None = None,
    status_path: str | Path = "data/crawl_status.json",
    alerts_path: str | Path = "data/alerts.json",
    runtime_config_path: str | Path | None = None,
) -> None:
    """持续轮询队列处理任务。"""
    processed = 0
    logger.info("[collector_worker] Worker loop started")

    while True:
        try:
            did_work = await process_one_job(
                queue,
                session_service,
                status_path=status_path,
                alerts_path=alerts_path,
                runtime_config_path=runtime_config_path,
            )
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
