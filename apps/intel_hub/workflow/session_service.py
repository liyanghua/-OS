"""Session Service — 管理采集账号池、登录态、冷却期与健康状态。

所有会话元数据持久化到 data/sessions/session_registry.json。
Worker 通过 acquire_session / release_session 获取/归还可用会话。
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional


_SESSIONS_DIR = Path("data/sessions")
_REGISTRY_PATH = _SESSIONS_DIR / "session_registry.json"
_MAX_CONSECUTIVE_FAILURES = 3
_DEFAULT_COOLDOWN_MINUTES = 15


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _normalize_platform(platform: str | None) -> str:
    value = (platform or "").strip().lower()
    if value in {"xhs", "xiaohongshu", "rednote"}:
        return "xhs"
    if value in {"dy", "douyin", "tiktok_cn"}:
        return "dy"
    return value or "xhs"


@dataclass
class AccountSession:
    account_id: str
    platform: str
    storage_state_path: str
    exported_at: str = ""
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_failure_reason: str | None = None
    consecutive_failures: int = 0
    cooldown_until: str | None = None
    status: str = "available"  # available | stale | cooldown | needs_relogin

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SessionService:
    """管理 data/sessions/ 下所有 storage_state 文件和会话元数据。"""

    def __init__(self, sessions_dir: str | Path = _SESSIONS_DIR):
        self._dir = Path(sessions_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = self._dir / "session_registry.json"
        self._sessions: dict[str, AccountSession] = {}
        self._load()

    def _load(self) -> None:
        if self._registry_path.exists():
            try:
                data = json.loads(self._registry_path.read_text(encoding="utf-8"))
                for item in data.get("sessions", []):
                    s = AccountSession(**{
                        k: v for k, v in item.items()
                        if k in AccountSession.__dataclass_fields__
                    })
                    self._sessions[s.account_id] = s
            except Exception:
                self._sessions = {}
        self._discover_imported_sessions()

    def _save(self) -> None:
        payload = {
            "updated_at": _now_iso(),
            "sessions": [s.to_dict() for s in self._sessions.values()],
        }
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        try:
            os.write(fd, data.encode("utf-8"))
            os.close(fd)
            os.replace(tmp, self._registry_path)
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _discover_imported_sessions(self) -> None:
        discovered: dict[str, AccountSession] = {}
        for state_path in sorted(self._dir.glob("*_state.json")):
            stem = state_path.stem
            platform = _normalize_platform(stem[:-6] if stem.endswith("_state") else stem)
            account_id = f"{platform}_imported"
            exported_at = ""
            meta_candidates = [
                state_path.with_suffix(".meta.json"),
                state_path.with_name(f"{state_path.name}.meta.json"),
            ]
            for meta_path in meta_candidates:
                if not meta_path.exists():
                    continue
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                exported_at = str(meta.get("exported_at", "") or "")
                platform = _normalize_platform(meta.get("platform", platform))
                break

            existing = self._sessions.get(account_id)
            session = existing or AccountSession(
                account_id=account_id,
                platform=platform,
                storage_state_path=str(state_path),
                exported_at=exported_at or _now_iso(),
                status="available",
            )
            session.platform = platform
            session.storage_state_path = str(state_path)
            if exported_at:
                session.exported_at = exported_at
            if session.status == "stale" and state_path.exists():
                session.status = "available"
            self._sessions[account_id] = session
            discovered[account_id] = session

        stale_import_ids = [
            account_id
            for account_id, session in self._sessions.items()
            if account_id.endswith("_imported") and account_id not in discovered
        ]
        for account_id in stale_import_ids:
            self._sessions.pop(account_id, None)

    def register_session(
        self,
        account_id: str,
        platform: str,
        storage_state_path: str,
    ) -> AccountSession:
        session = AccountSession(
            account_id=account_id,
            platform=platform,
            storage_state_path=storage_state_path,
            exported_at=_now_iso(),
            status="available",
        )
        self._sessions[account_id] = session
        self._save()
        return session

    def acquire_session(self, platform: str) -> AccountSession | None:
        """分配一个可用会话，优先选最近成功过的。"""
        self._discover_imported_sessions()
        now = datetime.now(tz=timezone.utc)
        normalized_platform = _normalize_platform(platform)

        candidates = []
        for s in self._sessions.values():
            if _normalize_platform(s.platform) != normalized_platform:
                continue
            if s.status == "needs_relogin":
                continue
            if s.status == "cooldown" and s.cooldown_until:
                try:
                    until = datetime.fromisoformat(s.cooldown_until)
                    if now < until:
                        continue
                    s.status = "available"
                except Exception:
                    pass
            if not Path(s.storage_state_path).exists():
                s.status = "stale"
                continue
            if s.status in ("available", "stale"):
                candidates.append(s)

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: x.last_success_at or "",
            reverse=True,
        )
        chosen = candidates[0]
        self._save()
        return chosen

    def release_session(
        self,
        account_id: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        session = self._sessions.get(account_id)
        if not session:
            return

        if success:
            session.last_success_at = _now_iso()
            session.consecutive_failures = 0
            session.status = "available"
            session.last_failure_reason = None
        else:
            session.last_failure_at = _now_iso()
            session.last_failure_reason = (error or "unknown")[:500]
            session.consecutive_failures += 1
            if session.consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                session.status = "needs_relogin"
            else:
                session.status = "cooldown"
                cooldown_end = datetime.now(tz=timezone.utc) + timedelta(
                    minutes=_DEFAULT_COOLDOWN_MINUTES
                )
                session.cooldown_until = cooldown_end.isoformat()

        self._save()

    def mark_relogin_needed(self, account_id: str) -> None:
        session = self._sessions.get(account_id)
        if session:
            session.status = "needs_relogin"
            self._save()

    def mark_available(self, account_id: str) -> None:
        session = self._sessions.get(account_id)
        if session:
            session.status = "available"
            session.consecutive_failures = 0
            session.exported_at = _now_iso()
            self._save()

    def list_sessions(self, platform: str | None = None) -> list[AccountSession]:
        self._discover_imported_sessions()
        if platform:
            normalized_platform = _normalize_platform(platform)
            return [s for s in self._sessions.values() if _normalize_platform(s.platform) == normalized_platform]
        return list(self._sessions.values())

    def get_alerts(self) -> list[dict[str, Any]]:
        """返回需要人工介入的会话告警。"""
        self._discover_imported_sessions()
        alerts = []
        for s in self._sessions.values():
            if s.status == "needs_relogin":
                alerts.append({
                    "type": "session_needs_relogin",
                    "account_id": s.account_id,
                    "platform": s.platform,
                    "reason": s.last_failure_reason,
                    "since": s.last_failure_at,
                })
        platforms_with_session = {_normalize_platform(s.platform) for s in self._sessions.values()}
        for platform, title in (("xhs", "请导入小红书登录态"), ("dy", "请导入抖音登录态")):
            if platform in platforms_with_session:
                continue
            alerts.append(
                {
                    "type": "session_import_required",
                    "platform": platform,
                    "title": title,
                    "reason": "未发现可用 storage_state 文件",
                    "since": "",
                }
            )
        return alerts
