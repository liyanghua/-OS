"""NoteMetricsSyncer -- 从小红书创作者后台回采笔记互动数据。

策略：
1. 主方案 — 打开创作者后台数据中心，拦截浏览器发出的
   /api/galaxy/creator/datacenter/note/base?note_id=... 响应，
   获取结构化的互动数据（点赞、收藏、评论、分享、观看等）。
2. 降级方案 — 如果拦截失败，在创作者后台上下文中直接 fetch 该 API。

使用创作者后台而非公开笔记页，因为：
- 审核中 / 仅自己可见的笔记在公开页无法访问
- 创作者后台 API 无需额外签名，cookie 即可
- 数据更全面（含观看、涨粉、曝光等）
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from apps.intel_hub.config_loader import resolve_browser_headless

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SESSIONS_DIR = _REPO_ROOT / "data" / "sessions"
_STORAGE_STATE_PATH = _SESSIONS_DIR / "xhs_state.json"

_CREATOR_DATA_CENTER = "https://creator.xiaohongshu.com/creator/data-center/note"
_NOTE_API_TPL = "https://creator.xiaohongshu.com/api/galaxy/creator/datacenter/note/base?note_id={note_id}"

_AUDIT_STATUS_MAP = {
    0: "审核中",
    1: "审核通过",
    2: "审核未通过",
    3: "已隐藏",
}

_FETCH_NOTE_DATA_SCRIPT = """
async (noteId) => {
    try {
        const url = '/api/galaxy/creator/datacenter/note/base?note_id=' + noteId;
        const resp = await fetch(url, { credentials: 'include' });
        if (!resp.ok) return { error: 'HTTP ' + resp.status };
        return await resp.json();
    } catch (e) {
        return { error: e.message || String(e) };
    }
}
"""


class NoteMetricsSyncer:
    """Fetch note interaction metrics from Xiaohongshu Creator Center."""

    def __init__(self, headless: bool | None = None) -> None:
        self._headless = resolve_browser_headless(headless, default=True)

    def _has_storage_state(self) -> bool:
        return _STORAGE_STATE_PATH.exists()

    async def fetch(self, note_id: str) -> dict[str, Any] | None:
        if not note_id:
            return None
        if not self._has_storage_state():
            logger.warning("[NoteMetricsSyncer] no storage_state, cannot fetch")
            return None

        logger.info("[NoteMetricsSyncer] fetching note %s via Creator Center", note_id)

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=self._headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(
                    storage_state=str(_STORAGE_STATE_PATH),
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/125.0.0.0 Safari/537.36",
                )
                page = await context.new_page()

                api_result: dict[str, Any] | None = None

                async def _intercept(response):
                    nonlocal api_result
                    if "datacenter/note/base" in response.url and note_id in response.url:
                        try:
                            body = await response.json()
                            if body.get("success") and body.get("data"):
                                api_result = body["data"]
                                logger.info("[NoteMetricsSyncer] intercepted creator note API")
                        except Exception:
                            pass

                page.on("response", _intercept)

                await page.goto(_CREATOR_DATA_CENTER, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(5000)

                result: dict[str, Any] | None = None

                if api_result:
                    result = self._extract(api_result, note_id)
                    logger.info("[NoteMetricsSyncer] got data from page-load intercept")

                if not result:
                    logger.info("[NoteMetricsSyncer] intercept missed, fetching directly")
                    raw = await page.evaluate(_FETCH_NOTE_DATA_SCRIPT, note_id)
                    if raw and not raw.get("error") and raw.get("data"):
                        result = self._extract(raw["data"], note_id)
                        logger.info("[NoteMetricsSyncer] got data from direct fetch")
                    elif raw and raw.get("error"):
                        logger.warning("[NoteMetricsSyncer] direct fetch error: %s", raw["error"])

                await context.close()
                await browser.close()

            if not result:
                logger.warning("[NoteMetricsSyncer] all methods failed for %s", note_id)
                return None

            return result

        except Exception as e:
            logger.exception("[NoteMetricsSyncer] fetch failed: %s", e)
            return None

    @staticmethod
    def _extract(data: dict, note_id: str) -> dict[str, Any]:
        """Extract metrics from creator datacenter note/base response."""
        note_info = data.get("note_info", {})
        audit = note_info.get("audit_status", -1)

        liked = data.get("like_count", note_info.get("like_count", 0))
        collected = data.get("collect_count", 0)
        commented = data.get("comment_count", note_info.get("comment_count", 0))
        shared = data.get("share_count", 0)
        viewed = data.get("view_count", note_info.get("view_count", 0))
        rise_fans = data.get("rise_fans_count", 0)

        if isinstance(liked, int) and liked < 0:
            liked = 0
        if isinstance(collected, int) and collected < 0:
            collected = 0
        if isinstance(commented, int) and commented < 0:
            commented = 0
        if isinstance(shared, int) and shared < 0:
            shared = 0
        if isinstance(viewed, int) and viewed < 0:
            viewed = 0

        audit_label = _AUDIT_STATUS_MAP.get(audit, f"未知({audit})")

        result: dict[str, Any] = {
            "note_id": note_id,
            "liked_count": int(liked),
            "collected_count": int(collected),
            "comment_count": int(commented),
            "share_count": int(shared),
            "view_count": int(viewed),
            "rise_fans_count": int(rise_fans) if isinstance(rise_fans, int) and rise_fans >= 0 else 0,
            "title": note_info.get("desc", ""),
            "type": note_info.get("type", ""),
            "cover_url": note_info.get("cover_url", ""),
            "audit_status": audit,
            "audit_label": audit_label,
            "source": "creator_datacenter",
        }

        if audit == 0:
            result["note_status"] = "under_review"
            result["note_status_msg"] = "笔记审核中"
        elif audit == 2:
            result["note_status"] = "rejected"
            result["note_status_msg"] = "笔记审核未通过"
        elif audit == 3:
            result["note_status"] = "hidden"
            result["note_status_msg"] = "笔记已隐藏"

        return result
