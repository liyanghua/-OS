"""AgentRunRegistry — 进程内机会卡生成 Agent 任务注册表。

职责：
- 同 ``lens_id`` 互斥（同一时间只允许一个生成任务）；
- 维护任务快照（里程碑进度、最近事件、状态、错误等），供 GET 接口与
  抽屉断线重连查询；
- 提供软取消信号，让 ``OpportunityGenAgent.run()`` 在每个里程碑头部
  早退。

任务事件流持久化复用 ``apps.content_planning.gateway.event_bus``，
本注册表只保存"摘要"，不复述全量事件。
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# 5 个里程碑（文案/权重见 plan §4），保持稳定的 stage_id，便于前端做 i18n。
DEFAULT_MILESTONES: list[dict[str, Any]] = [
    {"id": "M1", "label": "探查与解析", "weight": 10},
    {"id": "M2", "label": "信号提取", "weight": 50},
    {"id": "M3", "label": "跨模态与映射", "weight": 10},
    {"id": "M4", "label": "机会卡编译", "weight": 15},
    {"id": "M5", "label": "透视聚合与入库", "weight": 15},
]


@dataclass
class AgentRunSnapshot:
    """单次 Agent 任务的运行时快照。"""

    task_id: str
    lens_id: str
    lens_label: str = ""
    status: str = "pending"  # pending | running | done | failed | cancelled
    started_at: str = field(default_factory=_now_iso)
    ended_at: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    milestones: list[dict[str, Any]] = field(default_factory=lambda: [
        {**m, "status": "pending", "progress": 0.0} for m in DEFAULT_MILESTONES
    ])
    counters: dict[str, int] = field(default_factory=lambda: {
        "notes_total": 0,
        "notes_done": 0,
        "vlm_calls": 0,
        "llm_calls": 0,
        "cards_total": 0,
    })
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    error: dict[str, Any] | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    _cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("_cancelled", None)
        return d


class AgentRunRegistry:
    """进程内单例：管理所有活跃/最近完成的 Agent 任务。"""

    _MAX_RECENT_EVENTS: int = 30
    _MAX_KEEP_TASKS: int = 16  # 完成后仍保留若干条供刷新页面回看

    def __init__(self) -> None:
        self._tasks: dict[str, AgentRunSnapshot] = {}
        self._lock = threading.Lock()

    # ── 启动与互斥 ──────────────────────────────────────────────
    def start(
        self,
        lens_id: str,
        *,
        lens_label: str = "",
        options: dict[str, Any] | None = None,
    ) -> tuple[str, AgentRunSnapshot]:
        """登记一个新任务；若同 ``lens_id`` 已有 in-flight 任务则抛 ``RuntimeError``。"""
        with self._lock:
            active = self._active_by_lens_locked(lens_id)
            if active is not None:
                raise RuntimeError(
                    f"该类目已有正在执行的生成任务 task_id={active.task_id}"
                )
            task_id = uuid.uuid4().hex[:16]
            snap = AgentRunSnapshot(
                task_id=task_id,
                lens_id=lens_id,
                lens_label=lens_label or lens_id,
                status="pending",
                options=dict(options or {}),
            )
            self._tasks[task_id] = snap
            self._evict_locked()
            return task_id, snap

    # ── 查询 ────────────────────────────────────────────────────
    def get(self, task_id: str) -> AgentRunSnapshot | None:
        with self._lock:
            return self._tasks.get(task_id)

    def get_active_by_lens(self, lens_id: str) -> AgentRunSnapshot | None:
        with self._lock:
            return self._active_by_lens_locked(lens_id)

    def _active_by_lens_locked(self, lens_id: str) -> AgentRunSnapshot | None:
        for snap in self._tasks.values():
            if snap.lens_id == lens_id and snap.status in {"pending", "running"}:
                return snap
        return None

    # ── 状态变更 ────────────────────────────────────────────────
    def mark_running(self, task_id: str) -> None:
        with self._lock:
            snap = self._tasks.get(task_id)
            if snap is not None and snap.status == "pending":
                snap.status = "running"

    def mark_done(self, task_id: str, summary: dict[str, Any] | None = None) -> None:
        with self._lock:
            snap = self._tasks.get(task_id)
            if snap is None:
                return
            snap.status = "done"
            snap.ended_at = _now_iso()
            if summary:
                snap.summary = dict(summary)
            for m in snap.milestones:
                if m["status"] != "completed":
                    m["status"] = "completed"
                    m["progress"] = 1.0

    def mark_failed(
        self,
        task_id: str,
        error_kind: str,
        message: str,
        *,
        suggestion: str = "",
        suggested_url: str = "",
    ) -> None:
        with self._lock:
            snap = self._tasks.get(task_id)
            if snap is None:
                return
            snap.status = "failed"
            snap.ended_at = _now_iso()
            snap.error = {
                "error_kind": error_kind,
                "message": message,
                "suggestion": suggestion,
                "suggested_url": suggested_url,
            }

    def request_cancel(self, task_id: str) -> bool:
        with self._lock:
            snap = self._tasks.get(task_id)
            if snap is None:
                return False
            if snap.status not in {"pending", "running"}:
                return False
            snap._cancelled = True
            return True

    def is_cancelled(self, task_id: str) -> bool:
        with self._lock:
            snap = self._tasks.get(task_id)
            return bool(snap and snap._cancelled)

    def mark_cancelled(self, task_id: str) -> None:
        with self._lock:
            snap = self._tasks.get(task_id)
            if snap is None:
                return
            snap.status = "cancelled"
            snap.ended_at = _now_iso()

    # ── 进度更新 ────────────────────────────────────────────────
    def update_milestone(
        self,
        task_id: str,
        milestone_id: str,
        *,
        status: str | None = None,
        progress: float | None = None,
    ) -> None:
        with self._lock:
            snap = self._tasks.get(task_id)
            if snap is None:
                return
            for m in snap.milestones:
                if m["id"] == milestone_id:
                    if status is not None:
                        m["status"] = status
                    if progress is not None:
                        m["progress"] = max(0.0, min(1.0, float(progress)))
                    break

    def bump_counters(self, task_id: str, **deltas: int) -> None:
        with self._lock:
            snap = self._tasks.get(task_id)
            if snap is None:
                return
            for k, v in deltas.items():
                snap.counters[k] = snap.counters.get(k, 0) + int(v)

    def set_counter(self, task_id: str, name: str, value: int) -> None:
        with self._lock:
            snap = self._tasks.get(task_id)
            if snap is None:
                return
            snap.counters[name] = int(value)

    def append_event(self, task_id: str, event: dict[str, Any]) -> None:
        """缓存最近 N 条事件摘要，前端首次打开抽屉可用作"补帧"。"""
        with self._lock:
            snap = self._tasks.get(task_id)
            if snap is None:
                return
            evt = dict(event)
            evt.setdefault("ts", time.time())
            snap.recent_events.append(evt)
            if len(snap.recent_events) > self._MAX_RECENT_EVENTS:
                snap.recent_events = snap.recent_events[-self._MAX_RECENT_EVENTS:]

    # ── 内部工具 ────────────────────────────────────────────────
    def _evict_locked(self) -> None:
        if len(self._tasks) <= self._MAX_KEEP_TASKS:
            return
        finished = [
            (tid, s.ended_at or s.started_at)
            for tid, s in self._tasks.items()
            if s.status in {"done", "failed", "cancelled"}
        ]
        finished.sort(key=lambda kv: kv[1])
        for tid, _ in finished[: len(self._tasks) - self._MAX_KEEP_TASKS]:
            self._tasks.pop(tid, None)


agent_run_registry = AgentRunRegistry()
