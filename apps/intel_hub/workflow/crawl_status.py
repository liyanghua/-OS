"""结构化抓取状态上报器。

在 MediaCrawler 抓取过程中写入 JSON 状态文件到 data/crawl_status.json，
供 intel_hub API 读取展示抓取进度。

写入方式：write-to-temp + os.replace 原子替换，避免读取到半写文件。
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class CrawlStatus:
    run_id: str = ""
    started_at: str = ""
    status: str = "idle"  # idle | running | completed | failed
    platform: str = ""
    keywords: list[str] = field(default_factory=list)
    current_keyword: str = ""
    current_keyword_index: int = 0
    total_keywords: int = 0
    notes_found: int = 0
    notes_saved: int = 0
    notes_failed: int = 0
    comments_saved: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str = ""
    completed_at: str | None = None
    output_dir: str = ""
    # Phase 1.2: tracing diagnostics
    traces_saved: int = 0
    trace_dir: str = ""
    # Phase 2.3: extended observability
    session_id: str = ""
    extractor_versions: dict[str, str] = field(default_factory=dict)
    duration_seconds: float = 0.0
    avg_note_delay_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CrawlStatusReporter:
    """轻量抓取状态上报器，写 JSON 文件供 API 读取。"""

    def __init__(self, status_path: str | Path, platform: str = "xhs", output_dir: str = ""):
        self._path = Path(status_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._status = CrawlStatus(
            run_id=uuid.uuid4().hex[:12],
            started_at=_now_iso(),
            status="running",
            platform=platform,
            output_dir=output_dir,
            updated_at=_now_iso(),
        )
        self._flush()

    def _flush(self) -> None:
        self._status.updated_at = _now_iso()
        data = json.dumps(self._status.to_dict(), ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            os.write(fd, data.encode("utf-8"))
            os.close(fd)
            os.replace(tmp, self._path)
        except Exception:
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def set_keywords(self, keywords: list[str]) -> None:
        self._status.keywords = keywords
        self._status.total_keywords = len(keywords)
        self._flush()

    def keyword_started(self, keyword: str, index: int) -> None:
        self._status.current_keyword = keyword
        self._status.current_keyword_index = index
        self._flush()

    def notes_found(self, count: int) -> None:
        self._status.notes_found += count
        self._flush()

    def note_saved(self, note_id: str) -> None:
        self._status.notes_saved += 1
        self._flush()

    def note_failed(self, note_id: str, error: str) -> None:
        self._status.notes_failed += 1
        self._status.errors.append({
            "note_id": note_id,
            "error": error[:200],
            "timestamp": _now_iso(),
        })
        if len(self._status.errors) > 50:
            self._status.errors = self._status.errors[-50:]
        self._flush()

    def comments_saved(self, count: int) -> None:
        self._status.comments_saved += count
        self._flush()

    def keyword_finished(self) -> None:
        self._flush()

    def trace_captured(self, trace_dir: str) -> None:
        self._status.traces_saved += 1
        self._status.trace_dir = trace_dir
        self._flush()

    def set_session_id(self, session_id: str) -> None:
        self._status.session_id = session_id
        self._flush()

    def set_extractor_versions(self, versions: dict[str, str]) -> None:
        self._status.extractor_versions = versions
        self._flush()

    def crawl_finished(self, status: str = "completed") -> None:
        self._status.status = status
        self._status.completed_at = _now_iso()
        if self._status.started_at:
            try:
                start = datetime.fromisoformat(self._status.started_at)
                end = datetime.now(tz=timezone.utc)
                self._status.duration_seconds = round((end - start).total_seconds(), 1)
            except Exception:
                pass
        if self._status.notes_saved > 0 and self._status.duration_seconds > 0:
            self._status.avg_note_delay_seconds = round(
                self._status.duration_seconds / self._status.notes_saved, 1
            )
        self._flush()

    @property
    def status(self) -> CrawlStatus:
        return self._status


class NoopReporter:
    """空操作 reporter，当 hook 未注入时使用。"""

    def set_keywords(self, keywords: list[str]) -> None: ...
    def keyword_started(self, keyword: str, index: int) -> None: ...
    def notes_found(self, count: int) -> None: ...
    def note_saved(self, note_id: str) -> None: ...
    def note_failed(self, note_id: str, error: str) -> None: ...
    def comments_saved(self, count: int) -> None: ...
    def keyword_finished(self) -> None: ...
    def trace_captured(self, trace_dir: str) -> None: ...
    def set_session_id(self, session_id: str) -> None: ...
    def set_extractor_versions(self, versions: dict[str, str]) -> None: ...
    def crawl_finished(self, status: str = "completed") -> None: ...
