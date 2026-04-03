"""采集调度器 — 基于配置文件定时创建采集任务。

读取 config/crawl_schedule.yaml，按 cron 表达式或间隔创建 CrawlJob 入队。
PoC 阶段使用 schedule 库做 in-process 调度。
"""

from __future__ import annotations

import logging
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .job_models import CrawlJob
from .job_queue import FileJobQueue

logger = logging.getLogger("scheduler")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCHEDULE_PATH = REPO_ROOT / "config" / "crawl_schedule.yaml"
DEFAULT_KEYWORDS_PATH = REPO_ROOT / "config" / "keywords.yaml"


def _load_schedule_config(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_SCHEDULE_PATH
    if not p.exists():
        logger.warning(f"[scheduler] Schedule config not found: {p}")
        return {"schedules": []}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {"schedules": []}


def _load_keywords(path: str | None = None) -> str:
    p = Path(path) if path else DEFAULT_KEYWORDS_PATH
    if not p.exists():
        return ""
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    keywords = data.get("keywords", [])
    if isinstance(keywords, list):
        return ",".join(str(k) for k in keywords)
    return str(keywords)


def create_jobs_from_schedule(
    schedule_entry: dict[str, Any],
    queue: FileJobQueue,
) -> list[CrawlJob]:
    """将一个调度条目拆分成具体的 CrawlJob 并入队。"""
    job_type = schedule_entry.get("job_type", "keyword_search")
    platform = schedule_entry.get("platform", "xhs")
    priority = schedule_entry.get("priority", 5)
    max_notes = schedule_entry.get("max_notes_per_keyword", 10)

    keywords_from = schedule_entry.get("keywords_from")
    keywords_str = _load_keywords(keywords_from) if keywords_from else ""
    if not keywords_str:
        keywords_str = schedule_entry.get("keywords", "")

    if not keywords_str:
        logger.warning(f"[scheduler] No keywords for schedule: {schedule_entry.get('name')}")
        return []

    job = CrawlJob(
        platform=platform,
        job_type=job_type,
        payload={
            "keywords": keywords_str,
            "max_notes": max_notes,
            "max_comments": schedule_entry.get("max_comments", 10),
            "schedule_name": schedule_entry.get("name", "manual"),
        },
        priority=priority,
    )
    queue.enqueue(job)
    logger.info(f"[scheduler] Created job {job.job_id} for schedule '{schedule_entry.get('name')}'")
    return [job]


def run_all_schedules(
    queue: FileJobQueue,
    config_path: Path | None = None,
) -> list[CrawlJob]:
    """立即执行所有调度条目（手动触发）。"""
    cfg = _load_schedule_config(config_path)
    all_jobs: list[CrawlJob] = []
    for entry in cfg.get("schedules", []):
        if not entry.get("enabled", True):
            continue
        jobs = create_jobs_from_schedule(entry, queue)
        all_jobs.extend(jobs)
    return all_jobs


class SchedulerDaemon:
    """简易 in-process 调度守护线程。

    PoC 阶段使用固定间隔检查 + 上次运行时间比对；
    生产阶段可切换为 Celery Beat 或 APScheduler。
    """

    def __init__(
        self,
        queue: FileJobQueue,
        config_path: Path | None = None,
        check_interval: float = 60.0,
    ):
        self._queue = queue
        self._config_path = config_path
        self._interval = check_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_run: dict[str, str] = {}

    def _should_run(self, entry: dict[str, Any]) -> bool:
        """简化判断：每个 schedule 每天最多运行一次。"""
        name = entry.get("name", "")
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        last = self._last_run.get(name, "")
        return last != today

    def _loop(self) -> None:
        while self._running:
            try:
                cfg = _load_schedule_config(self._config_path)
                for entry in cfg.get("schedules", []):
                    if not entry.get("enabled", True):
                        continue
                    if self._should_run(entry):
                        create_jobs_from_schedule(entry, self._queue)
                        self._last_run[entry.get("name", "")] = (
                            datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
                        )
            except Exception as ex:
                logger.error(f"[scheduler] Error in scheduler loop: {ex}")
            time.sleep(self._interval)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scheduler")
        self._thread.start()
        logger.info("[scheduler] Scheduler daemon started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[scheduler] Scheduler daemon stopped")
