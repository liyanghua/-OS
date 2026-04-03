"""采集任务数据模型。

定义 CrawlJob — 所有采集任务的统一描述，
不依赖特定队列实现（RQ / Celery / file-based）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class CrawlJob:
    job_id: str = ""
    platform: str = "xhs"
    job_type: str = "keyword_search"  # keyword_search | note_detail | comments | pipeline_refresh
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 0 = highest
    max_retries: int = 3
    retry_count: int = 0
    status: str = "pending"  # pending | running | completed | failed | dead
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    result_path: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrawlJob:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})

    def mark_running(self) -> None:
        self.status = "running"
        self.started_at = _now_iso()

    def mark_completed(self, result_path: str | None = None) -> None:
        self.status = "completed"
        self.completed_at = _now_iso()
        self.result_path = result_path

    def mark_failed(self, error: str) -> None:
        self.retry_count += 1
        if self.retry_count >= self.max_retries:
            self.status = "dead"
        else:
            self.status = "failed"
        self.error = error[:500]
        self.completed_at = _now_iso()

    def can_retry(self) -> bool:
        return self.status == "failed" and self.retry_count < self.max_retries
