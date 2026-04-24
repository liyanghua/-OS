"""采集任务队列 — 文件持久化 PoC 实现。

所有任务持久化到 data/job_queue.json，支持 enqueue / dequeue / retry / status 查询。
接口设计兼容后续切换 RQ / Celery。
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .job_models import CrawlJob


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class FileJobQueue:
    """基于 JSON 文件的轻量任务队列（PoC，可切换为 RQ/Celery）。"""

    def __init__(self, queue_path: str | Path = "data/job_queue.json"):
        self._path = Path(queue_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self._path.exists():
            self._save_all([])

    def _load_all(self) -> list[CrawlJob]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return [CrawlJob.from_dict(j) for j in data.get("jobs", [])]
        except Exception:
            return []

    def _save_all(self, jobs: list[CrawlJob]) -> None:
        payload = {
            "updated_at": _now_iso(),
            "jobs": [j.to_dict() for j in jobs],
        }
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            os.write(fd, data.encode("utf-8"))
            os.close(fd)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def enqueue(self, job: CrawlJob) -> CrawlJob:
        with self._lock:
            jobs = self._load_all()
            job.status = "pending"
            jobs.append(job)
            self._save_all(jobs)
        return job

    def dequeue(self) -> CrawlJob | None:
        """取出优先级最高的 pending 任务并标记 running。"""
        with self._lock:
            jobs = self._load_all()
            pending = [j for j in jobs if j.status == "pending"]
            if not pending:
                return None
            pending.sort(
                key=lambda j: (
                    1 if j.job_type == "pipeline_refresh" else 0,
                    j.priority,
                    j.created_at,
                )
            )
            chosen = pending[0]
            for j in jobs:
                if j.job_id == chosen.job_id:
                    j.mark_running()
                    chosen = j
                    break
            self._save_all(jobs)
            return chosen

    def complete(self, job_id: str, result_path: str | None = None) -> None:
        with self._lock:
            jobs = self._load_all()
            for j in jobs:
                if j.job_id == job_id:
                    j.mark_completed(result_path)
                    break
            self._save_all(jobs)

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            jobs = self._load_all()
            for j in jobs:
                if j.job_id == job_id:
                    j.mark_failed(error)
                    break
            self._save_all(jobs)

    def retry(self, job_id: str) -> bool:
        with self._lock:
            jobs = self._load_all()
            for j in jobs:
                if j.job_id == job_id and j.status in ("failed", "dead"):
                    j.status = "pending"
                    j.started_at = None
                    j.error = None
                    j.completed_at = None
                    j.last_heartbeat_at = None
                    j.result_path = None
                    self._save_all(jobs)
                    return True
            return False

    def touch_heartbeat(self, job_id: str) -> bool:
        with self._lock:
            jobs = self._load_all()
            for j in jobs:
                if j.job_id == job_id:
                    j.mark_heartbeat()
                    self._save_all(jobs)
                    return True
            return False

    def get_job(self, job_id: str) -> CrawlJob | None:
        jobs = self._load_all()
        for j in jobs:
            if j.job_id == job_id:
                return j
        return None

    def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[CrawlJob]:
        jobs = self._load_all()
        if status:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def list_group_jobs(self, job_group_id: str) -> list[CrawlJob]:
        jobs = [j for j in self._load_all() if j.job_group_id == job_group_id]
        jobs.sort(key=lambda j: j.created_at)
        return jobs

    def list_all(self) -> list[CrawlJob]:
        jobs = self._load_all()
        jobs.sort(key=lambda j: j.created_at)
        return jobs

    def list_batch_jobs(self, job_group_id: str) -> list[CrawlJob]:
        jobs = self.list_group_jobs(job_group_id)
        jobs.sort(
            key=lambda j: (
                1 if j.job_type == "pipeline_refresh" else 0,
                j.priority,
                j.created_at,
            )
        )
        return jobs

    def find_open_batch(self) -> str | None:
        jobs = self._load_all()
        group_ids = list({job.job_group_id for job in jobs if job.job_group_id})
        group_ids.sort(
            key=lambda gid: max((j.created_at for j in jobs if j.job_group_id == gid), default=""),
            reverse=True,
        )
        for group_id in group_ids:
            group_jobs = [j for j in jobs if j.job_group_id == group_id]
            pipeline_jobs = [j for j in group_jobs if j.job_type == "pipeline_refresh"]
            if any(j.status == "running" for j in pipeline_jobs):
                continue
            if any(j.status in ("completed", "failed", "dead") for j in pipeline_jobs):
                continue

            keyword_jobs = [j for j in group_jobs if j.job_type == "keyword_search"]
            if not keyword_jobs:
                continue

            if any(j.status in ("pending", "running") for j in keyword_jobs):
                return group_id
            if pipeline_jobs and any(j.status == "pending" for j in pipeline_jobs):
                return group_id
            if not pipeline_jobs and any(j.status in ("completed", "failed", "dead") for j in keyword_jobs):
                return group_id
        return None

    def count_group_jobs(
        self,
        job_group_id: str,
        *,
        job_type: str | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> int:
        jobs = self.list_group_jobs(job_group_id)
        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]
        if statuses:
            jobs = [j for j in jobs if j.status in statuses]
        return len(jobs)

    def has_pending_or_running_keyword_jobs(self, job_group_id: str | None = None) -> bool:
        jobs = self._load_all()
        if job_group_id:
            jobs = [j for j in jobs if j.job_group_id == job_group_id]
        return any(
            j.job_type == "keyword_search" and j.status in ("pending", "running")
            for j in jobs
        )

    def has_running_jobs(self) -> bool:
        return any(j.status == "running" for j in self._load_all())

    def find_pipeline_job(
        self,
        job_group_id: str,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> CrawlJob | None:
        jobs = [
            j for j in self._load_all()
            if j.job_group_id == job_group_id and j.job_type == "pipeline_refresh"
        ]
        if statuses:
            jobs = [j for j in jobs if j.status in statuses]
        if not jobs:
            return None
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[0]

    def ensure_pipeline_job(
        self,
        *,
        job_group_id: str,
        platform: str,
        display_keyword: str,
        priority: int = 0,
    ) -> CrawlJob | None:
        with self._lock:
            jobs = self._load_all()
            group_jobs = [j for j in jobs if j.job_group_id == job_group_id]
            existing = [
                j for j in group_jobs
                if j.job_type == "pipeline_refresh" and j.status in ("pending", "running", "completed")
            ]
            if existing:
                existing.sort(key=lambda j: j.created_at, reverse=True)
                return existing[0]

            has_pending_or_running_crawl = any(
                j.job_type == "keyword_search" and j.status in ("pending", "running")
                for j in group_jobs
            )
            if has_pending_or_running_crawl:
                return None

            refresh_job = CrawlJob(
                job_type="pipeline_refresh",
                platform=platform,
                job_group_id=job_group_id,
                display_keyword=display_keyword,
                priority=priority,
            )
            refresh_job.status = "pending"
            jobs.append(refresh_job)
            self._save_all(jobs)
            return refresh_job

    def latest_active_job(
        self,
        *,
        preferred_job_id: str | None = None,
    ) -> CrawlJob | None:
        jobs = self._load_all()
        scoped_jobs = jobs
        preferred_job: CrawlJob | None = None
        if preferred_job_id:
            for j in jobs:
                if j.job_id == preferred_job_id:
                    preferred_job = j
                    break
            if preferred_job:
                scoped_jobs = [j for j in jobs if j.job_group_id == preferred_job.job_group_id]

        def _pick_latest(matches: list[CrawlJob]) -> CrawlJob | None:
            if not matches:
                return None
            matches.sort(key=lambda j: (j.created_at, -j.priority), reverse=True)
            return matches[0]

        keyword_jobs = [j for j in scoped_jobs if j.job_type == "keyword_search"]
        for status in ("running", "pending"):
            picked = _pick_latest([j for j in keyword_jobs if j.status == status])
            if picked:
                return picked

        completed_with_pending_followup: list[CrawlJob] = []
        for crawl_job in [j for j in keyword_jobs if j.status == "completed"]:
            group_jobs = [j for j in scoped_jobs if j.job_group_id == crawl_job.job_group_id]
            pipeline_jobs = [j for j in group_jobs if j.job_type == "pipeline_refresh"]
            if not pipeline_jobs:
                continue
            pipeline_jobs.sort(key=lambda j: (j.created_at, -j.priority), reverse=True)
            if pipeline_jobs[0].status != "completed":
                completed_with_pending_followup.append(crawl_job)

        picked = _pick_latest(completed_with_pending_followup)
        if picked:
            return picked

        for status in ("failed", "dead"):
            picked = _pick_latest([j for j in keyword_jobs if j.status == status])
            if picked:
                return picked

        if preferred_job:
            return preferred_job
        return None

    def pending_count(self) -> int:
        return len([j for j in self._load_all() if j.status == "pending"])

    def stats(self) -> dict[str, int]:
        jobs = self._load_all()
        counts: dict[str, int] = {}
        for j in jobs:
            counts[j.status] = counts.get(j.status, 0) + 1
        return counts
