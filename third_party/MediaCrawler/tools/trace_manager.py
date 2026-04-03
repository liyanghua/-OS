"""Playwright 失败诊断管理器。

对采集失败的任务保存 screenshot + console log + 可选 trace，
归档到 data/traces/{date}/ 目录，超过 retention 天数自动清理。
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import BrowserContext, Page

from tools import utils


class TraceManager:
    """轻量级采集诊断归档器。"""

    def __init__(
        self,
        base_dir: str | Path = "data/traces",
        retention_days: int = 7,
        enable_tracing: bool = False,
    ):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._retention_days = retention_days
        self._enable_tracing = enable_tracing
        self._traces_saved = 0

    @property
    def traces_saved(self) -> int:
        return self._traces_saved

    def _today_dir(self) -> Path:
        d = self._base / datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def start_tracing(self, context: BrowserContext) -> None:
        if not self._enable_tracing:
            return
        try:
            await context.tracing.start(screenshots=True, snapshots=True)
        except Exception as ex:
            utils.logger.warning(f"[TraceManager] Failed to start tracing: {ex}")

    async def capture_failure(
        self,
        page: Optional[Page],
        context: Optional[BrowserContext],
        note_id: str,
        error: str,
    ) -> str | None:
        """截图 + 可选 trace 归档，返回保存目录路径。"""
        ts = datetime.now(tz=timezone.utc).strftime("%H%M%S")
        out_dir = self._today_dir() / f"{note_id}_{ts}"
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            if page and not page.is_closed():
                await page.screenshot(path=str(out_dir / "screenshot.png"))
        except Exception as ex:
            utils.logger.debug(f"[TraceManager] Screenshot failed: {ex}")

        if self._enable_tracing and context:
            try:
                await context.tracing.stop(path=str(out_dir / "trace.zip"))
                await context.tracing.start(screenshots=True, snapshots=True)
            except Exception as ex:
                utils.logger.debug(f"[TraceManager] Trace save failed: {ex}")

        meta = {
            "note_id": note_id,
            "error": error[:500],
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        (out_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        self._traces_saved += 1
        utils.logger.info(f"[TraceManager] Failure captured -> {out_dir}")
        return str(out_dir)

    def cleanup_old(self) -> int:
        """删除超过 retention_days 的旧 trace 目录，返回删除数量。"""
        if not self._base.exists():
            return 0
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=self._retention_days)
        removed = 0
        for child in sorted(self._base.iterdir()):
            if not child.is_dir():
                continue
            try:
                dir_date = datetime.strptime(child.name, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                if dir_date < cutoff:
                    shutil.rmtree(child)
                    removed += 1
            except ValueError:
                continue
        if removed:
            utils.logger.info(f"[TraceManager] Cleaned up {removed} old trace dirs")
        return removed
