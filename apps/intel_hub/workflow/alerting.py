"""告警系统 — 采集异常、会话失效、选择器失配等告警管理。

告警持久化到 data/alerts.json，Dashboard 轮询 GET /alerts 展示。
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

_ALERTS_PATH = Path("data/alerts.json")
_MAX_ALERTS = 100


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class Alert:
    alert_id: str = ""
    alert_type: str = ""  # session_needs_relogin | extractor_mismatch | crawl_failure | pipeline_error
    severity: str = "warning"  # info | warning | critical
    title: str = ""
    detail: str = ""
    source: str = ""
    created_at: str = ""
    resolved: bool = False
    resolved_at: str | None = None

    def __post_init__(self) -> None:
        if not self.alert_id:
            self.alert_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AlertManager:
    """文件持久化告警管理器。"""

    def __init__(self, alerts_path: str | Path = _ALERTS_PATH):
        self._path = Path(alerts_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8")).get("alerts", [])
        except Exception:
            return []

    def _save(self, alerts: list[dict[str, Any]]) -> None:
        alerts = alerts[-_MAX_ALERTS:]
        data = json.dumps(
            {"updated_at": _now_iso(), "alerts": alerts},
            ensure_ascii=False,
            indent=2,
        )
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

    def emit(self, alert: Alert) -> Alert:
        alerts = self._load()
        alerts.append(alert.to_dict())
        self._save(alerts)
        return alert

    def emit_session_relogin(self, account_id: str, platform: str, reason: str) -> Alert:
        return self.emit(Alert(
            alert_type="session_needs_relogin",
            severity="critical",
            title=f"会话需要重新登录: {account_id}",
            detail=f"平台: {platform}, 原因: {reason}",
            source=f"session:{account_id}",
        ))

    def emit_extractor_mismatch(self, page_type: str, detail: str) -> Alert:
        return self.emit(Alert(
            alert_type="extractor_mismatch",
            severity="warning",
            title=f"页面结构可能已变更: {page_type}",
            detail=detail,
            source=f"extractor:{page_type}",
        ))

    def emit_crawl_failure(self, job_id: str, error: str) -> Alert:
        return self.emit(Alert(
            alert_type="crawl_failure",
            severity="warning",
            title=f"采集任务失败: {job_id}",
            detail=error[:300],
            source=f"job:{job_id}",
        ))

    def emit_pipeline_error(self, error: str) -> Alert:
        return self.emit(Alert(
            alert_type="pipeline_error",
            severity="critical",
            title="Pipeline 执行失败",
            detail=error[:300],
            source="pipeline",
        ))

    def list_alerts(self, unresolved_only: bool = False) -> list[dict[str, Any]]:
        alerts = self._load()
        if unresolved_only:
            alerts = [a for a in alerts if not a.get("resolved", False)]
        return alerts

    def resolve(self, alert_id: str) -> bool:
        alerts = self._load()
        for a in alerts:
            if a.get("alert_id") == alert_id:
                a["resolved"] = True
                a["resolved_at"] = _now_iso()
                self._save(alerts)
                return True
        return False
