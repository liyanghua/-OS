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
            pending.sort(key=lambda j: j.priority)
            chosen = pending[0]
            for j in jobs:
                if j.job_id == chosen.job_id:
                    j.mark_running()
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

    def pending_count(self) -> int:
        return len([j for j in self._load_all() if j.status == "pending"])

    def stats(self) -> dict[str, int]:
        jobs = self._load_all()
        counts: dict[str, int] = {}
        for j in jobs:
            counts[j.status] = counts.get(j.status, 0) + 1
        return counts
