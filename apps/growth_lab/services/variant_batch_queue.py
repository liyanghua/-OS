"""VariantBatchQueue：主图裂变批量生成队列管理。

管理多 slot 并行生成任务，支持状态追踪和 SSE 风格进度上报。
MVP 阶段使用 ThreadPoolExecutor + 内存状态；生产可替换为 Celery / RQ。
"""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)

SlotStatus = Literal["queued", "running", "done", "failed"]

_MAX_WORKERS = 4


@dataclass
class SlotInfo:
    """单个生成槽位的状态。"""

    slot_id: str = ""
    index: int = 0
    status: SlotStatus = "queued"
    variant: dict[str, Any] = field(default_factory=dict)
    result_url: str = ""
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0


@dataclass
class BatchJob:
    """一个批量生成任务。"""

    batch_id: str = ""
    slots: list[SlotInfo] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: Literal["queued", "running", "done", "partial", "failed"] = "queued"


class VariantBatchQueue:
    """批量变体生成队列——管理并行 slot 执行与状态上报。"""

    def __init__(
        self,
        *,
        max_workers: int = _MAX_WORKERS,
        generate_fn: Callable[[dict], str] | None = None,
    ) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._batches: dict[str, BatchJob] = {}
        self._lock = Lock()
        self._generate_fn = generate_fn or self._mock_generate

    def enqueue_batch(
        self,
        variants: list[dict],
        *,
        workspace_id: str = "",
        brand_id: str = "",
    ) -> str:
        """将一组 variant dict 加入批量队列，返回 batch_id。"""
        batch_id = uuid.uuid4().hex[:16]
        slots: list[SlotInfo] = []
        for i, v in enumerate(variants):
            slots.append(SlotInfo(
                slot_id=uuid.uuid4().hex[:12],
                index=i,
                variant=v,
            ))

        job = BatchJob(batch_id=batch_id, slots=slots)

        with self._lock:
            self._batches[batch_id] = job

        logger.info("批量任务入队: batch=%s slots=%d", batch_id, len(slots))

        job.status = "running"
        for slot in slots:
            self._pool.submit(self._execute_slot, batch_id, slot.index)

        return batch_id

    def get_batch_status(self, batch_id: str) -> dict[str, Any]:
        """返回批量任务状态（SSE 友好格式）。"""
        with self._lock:
            job = self._batches.get(batch_id)
            if job is None:
                return {"batch_id": batch_id, "error": "not_found"}

            slot_summaries = []
            for s in job.slots:
                slot_summaries.append({
                    "slot_id": s.slot_id,
                    "index": s.index,
                    "status": s.status,
                    "result_url": s.result_url,
                    "error": s.error,
                })

            done_count = sum(1 for s in job.slots if s.status == "done")
            failed_count = sum(1 for s in job.slots if s.status == "failed")
            total = len(job.slots)

            if done_count + failed_count >= total:
                job.status = "done" if failed_count == 0 else "partial"

            return {
                "batch_id": batch_id,
                "status": job.status,
                "total": total,
                "done": done_count,
                "failed": failed_count,
                "progress_pct": round(
                    (done_count + failed_count) / max(total, 1) * 100, 1,
                ),
                "slots": slot_summaries,
            }

    def _execute_slot(self, batch_id: str, slot_index: int) -> None:
        """执行单个 slot 的生成任务（在线程池中运行）。"""
        with self._lock:
            job = self._batches.get(batch_id)
            if job is None or slot_index >= len(job.slots):
                return
            slot = job.slots[slot_index]
            slot.status = "running"
            slot.started_at = time.time()

        try:
            result_url = self._generate_fn(slot.variant)
            with self._lock:
                slot.status = "done"
                slot.result_url = result_url
                slot.finished_at = time.time()
            logger.info(
                "Slot 完成: batch=%s slot=%d elapsed=%.1fs",
                batch_id, slot_index, slot.finished_at - slot.started_at,
            )
        except Exception as exc:
            with self._lock:
                slot.status = "failed"
                slot.error = str(exc)[:200]
                slot.finished_at = time.time()
            logger.warning(
                "Slot 失败: batch=%s slot=%d error=%s",
                batch_id, slot_index, exc,
            )

    @staticmethod
    def _mock_generate(variant: dict) -> str:
        """MVP mock：模拟生成延迟并返回占位 URL。"""
        import random
        time.sleep(random.uniform(0.5, 2.0))
        variant_id = variant.get("variant_id", "unknown")
        return f"https://mock-cdn.example.com/generated/{variant_id}.png"
