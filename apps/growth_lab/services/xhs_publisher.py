"""XHSPublishService: Playwright 自动化发布视频到小红书创作者中心。

流程:
  1. 加载登录态（storage_state 或 cookie）
  2. 导航到 creator.xiaohongshu.com/publish/publish?target=video
  3. 上传视频文件
  4. 填写标题 / 正文 / 话题标签
  5. 点击发布并等待结果
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SESSIONS_DIR = _REPO_ROOT / "data" / "sessions"
_STORAGE_STATE_PATH = _SESSIONS_DIR / "xhs_state.json"
_STORAGE_STATE_MAX_AGE_HOURS = 24

_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=menu&target=video"
_CREATOR_HOME_URL = "https://creator.xiaohongshu.com/creator/home"

_XHS_TITLE_MAX_LEN = 20
_XHS_MAX_TOPICS = 5


def _ensure_env() -> None:
    env_file = _REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and val:
            os.environ.setdefault(key, val)


_ensure_env()


def _is_storage_state_valid() -> Optional[str]:
    """Check if a valid (non-stale) storage_state file exists."""
    if not _STORAGE_STATE_PATH.exists():
        return None
    meta_path = _STORAGE_STATE_PATH.with_suffix(".meta.json")
    if meta_path.exists():
        import json
        from datetime import datetime, timezone
        try:
            meta = json.loads(meta_path.read_text())
            exported = datetime.fromisoformat(meta["exported_at"])
            age_hours = (datetime.now(tz=timezone.utc) - exported).total_seconds() / 3600
            if age_hours > _STORAGE_STATE_MAX_AGE_HOURS:
                logger.info("[XHSPublish] storage_state stale (%.1fh old)", age_hours)
                return None
        except Exception:
            pass
    return str(_STORAGE_STATE_PATH)


class XHSPublishService:
    """Playwright-based XHS video publisher."""

    def __init__(self, headless: bool = False) -> None:
        self._headless = headless
        self._cookie_str = os.environ.get("XHS_COOKIE_STR", "")

    async def publish_video(
        self,
        video_path: str,
        title: str,
        body: str,
        topics: list[str],
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> dict[str, Any]:
        """Complete publish flow. Returns {status, note_url, error, elapsed_ms}."""
        from playwright.async_api import async_playwright

        start = time.monotonic()
        video_file = Path(video_path)
        if not video_file.exists():
            abs_path = _REPO_ROOT / video_path.lstrip("/")
            if abs_path.exists():
                video_file = abs_path
            else:
                return {"status": "failed", "error": f"视频文件不存在: {video_path}"}

        def _progress(step: str, detail: str = "") -> None:
            logger.info("[XHSPublish] %s %s", step, detail)
            if on_progress:
                on_progress(step, detail)

        _progress("starting", "启动浏览器…")

        async with async_playwright() as pw:
            launch_args = {
                "headless": self._headless,
                "args": ["--disable-blink-features=AutomationControlled"],
            }

            browser = await pw.chromium.launch(**launch_args)
            ss_path = _is_storage_state_valid()

            if ss_path:
                _progress("login", "使用已有登录态…")
                context = await browser.new_context(
                    storage_state=ss_path,
                    viewport={"width": 1400, "height": 900},
                )
            elif self._cookie_str:
                _progress("login", "无有效登录态，尝试 Cookie 注入…")
                context = await browser.new_context(
                    viewport={"width": 1400, "height": 900},
                )
                await self._inject_cookies(context, self._cookie_str)
            else:
                await browser.close()
                return {
                    "status": "failed",
                    "error": "无有效登录态且未配置 XHS_COOKIE_STR，请先通过 MediaCrawler 登录小红书",
                }

            try:
                page = context.pages[0] if context.pages else await context.new_page()

                # -- verify login --
                _progress("login_check", "验证登录状态…")
                await page.goto(_CREATOR_HOME_URL, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(2000)

                if "login" in page.url.lower():
                    return {
                        "status": "failed",
                        "error": "登录态无效，请重新通过 MediaCrawler 登录小红书",
                    }

                # -- navigate to publish page --
                _progress("navigate", "打开发布页面…")
                await page.goto(_PUBLISH_URL, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(2000)

                # -- upload video --
                _progress("upload", "上传视频文件…")
                uploaded = await self._upload_video(page, str(video_file.resolve()))
                if not uploaded:
                    return {"status": "failed", "error": "视频上传失败，未找到上传入口"}

                _progress("upload_wait", "等待视频处理…")
                await self._wait_video_processed(page)

                # -- fill title --
                _progress("fill_title", "填写标题…")
                await self._fill_title(page, title[:_XHS_TITLE_MAX_LEN])

                # -- fill body --
                _progress("fill_body", "填写正文…")
                await self._fill_body(page, body)

                # -- add topics --
                if topics:
                    _progress("add_topics", f"添加话题标签 ({len(topics)})…")
                    await self._add_topics(page, topics[:_XHS_MAX_TOPICS])

                # -- click publish --
                _progress("publishing", "点击发布…")
                result = await self._click_publish(page)

                elapsed_ms = int((time.monotonic() - start) * 1000)
                if result.get("status") == "published":
                    _progress("done", f"发布成功！耗时 {elapsed_ms/1000:.1f}s")
                    return {
                        "status": "published",
                        "note_url": result.get("note_url", ""),
                        "elapsed_ms": elapsed_ms,
                    }
                else:
                    return {
                        "status": "failed",
                        "error": result.get("error", "发布失败"),
                        "elapsed_ms": elapsed_ms,
                    }

            except Exception as e:
                logger.exception("[XHSPublish] 发布异常: %s", e)
                return {
                    "status": "failed",
                    "error": str(e),
                    "elapsed_ms": int((time.monotonic() - start) * 1000),
                }
            finally:
                await context.close()
                await browser.close()

    # ── Upload ────────────────────────────────────────────────────

    async def _upload_video(self, page, video_path: str) -> bool:
        """Locate file input and upload video."""

        # Strategy 1: find all <input type="file"> elements, force-unhide, then set_input_files
        try:
            all_inputs = page.locator('input[type="file"]')
            count = await all_inputs.count()
            logger.info("[XHSPublish] found %d input[type=file] elements", count)
            for i in range(count):
                inp = all_inputs.nth(i)
                await inp.evaluate(
                    "el => { el.style.opacity='1'; el.style.display='block';"
                    " el.style.visibility='visible'; el.style.position='relative';"
                    " el.style.width='200px'; el.style.height='50px'; }"
                )
                try:
                    accept = await inp.get_attribute("accept") or ""
                    logger.info("[XHSPublish] input[%d] accept=%s", i, accept)
                    await inp.set_input_files(video_path)
                    logger.info("[XHSPublish] uploaded via input[type=file] index %d", i)
                    return True
                except Exception as e:
                    logger.warning("[XHSPublish] input[%d] set_input_files failed: %s", i, e)
        except Exception as e:
            logger.warning("[XHSPublish] strategy 1 failed: %s", e)

        # Strategy 2: use file_chooser event triggered by clicking the upload zone
        upload_zone_selectors = [
            '[class*="upload-wrapper"]',
            '[class*="drag-over"]',
            '[class*="upload-input"]',
            '[class*="upload"]',
            'div[class*="container"] >> text=上传视频',
            ':text("上传视频")',
        ]
        for sel in upload_zone_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() == 0:
                    continue
                logger.info("[XHSPublish] trying file_chooser via click on: %s", sel)
                async with page.expect_file_chooser(timeout=10000) as fc_info:
                    await el.click()
                file_chooser = await fc_info.value
                await file_chooser.set_files(video_path)
                logger.info("[XHSPublish] uploaded via file_chooser (selector: %s)", sel)
                return True
            except Exception as e:
                logger.warning("[XHSPublish] file_chooser via '%s' failed: %s", sel, e)

        # Strategy 3: JS-level dispatch to any file input
        try:
            uploaded = await page.evaluate("""(videoPath) => {
                const inputs = document.querySelectorAll('input[type="file"]');
                return inputs.length;
            }""", video_path)
            logger.info("[XHSPublish] JS found %s file inputs (strategies exhausted)", uploaded)
        except Exception:
            pass

        return False

    async def _wait_video_processed(self, page, on_progress=None) -> None:
        """Wait for video upload + processing to complete (up to 3 min)."""
        max_rounds = 60
        for i in range(max_rounds):
            await page.wait_for_timeout(3000)

            progress_selectors = [
                '[class*="progress"]',
                '[class*="uploading"]',
                '[class*="loading"]',
                '[class*="percent"]',
            ]
            still_processing = False
            for sel in progress_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        still_processing = True
                        txt = (await el.text_content() or "").strip()[:60]
                        if i % 5 == 0:
                            logger.info("[XHSPublish] upload in progress (%ds): %s = '%s'", i * 3, sel, txt)
                        break
                except Exception:
                    continue

            if not still_processing:
                ready_selectors = [
                    '[class*="cover"]',
                    '[class*="video-preview"]',
                    '[class*="uploaded"]',
                    '[class*="reUpload"]',
                    ':text("重新上传")',
                ]
                for sel in ready_selectors:
                    try:
                        if await page.locator(sel).first.count() > 0:
                            logger.info("[XHSPublish] video ready after %ds (found %s)", i * 3, sel)
                            return
                    except Exception:
                        continue

            if i > 20 and not still_processing:
                logger.info("[XHSPublish] no progress indicator after %ds, proceeding", i * 3)
                break

        logger.info("[XHSPublish] video processing wait done (%ds)", max_rounds * 3)

    # ── Title ─────────────────────────────────────────────────────

    async def _fill_title(self, page, title: str) -> None:
        """Fill in the title field."""
        selectors = [
            '[placeholder*="标题"]',
            'input[class*="title"]',
            '#title',
            'c-input_inner',
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click()
                    await el.fill("")
                    await el.type(title, delay=50)
                    logger.info("[XHSPublish] title filled via: %s", sel)
                    return
            except Exception:
                continue

        try:
            editable = page.locator('div[contenteditable="true"]').first
            if await editable.count() > 0:
                await editable.click()
                await editable.type(title, delay=50)
                logger.info("[XHSPublish] title filled via contenteditable")
        except Exception as e:
            logger.warning("[XHSPublish] title fill failed: %s", e)

    # ── Body ──────────────────────────────────────────────────────

    async def _fill_body(self, page, body: str) -> None:
        """Fill in the body/description editor."""
        selectors = [
            '#post-textarea',
            '[placeholder*="添加正文"]',
            '[placeholder*="描述"]',
            'div.ql-editor[contenteditable="true"]',
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click()
                    await el.type(body, delay=30)
                    logger.info("[XHSPublish] body filled via: %s", sel)
                    return
            except Exception:
                continue

        try:
            editables = page.locator('div[contenteditable="true"]')
            count = await editables.count()
            if count >= 2:
                editor = editables.nth(1)
                await editor.click()
                await editor.type(body, delay=30)
                logger.info("[XHSPublish] body filled via 2nd contenteditable")
            elif count == 1:
                editor = editables.first
                await editor.click()
                await page.keyboard.press("End")
                await page.keyboard.press("Enter")
                await page.keyboard.type(body, delay=30)
                logger.info("[XHSPublish] body appended via single contenteditable")
        except Exception as e:
            logger.warning("[XHSPublish] body fill failed: %s", e)

    # ── Topics ────────────────────────────────────────────────────

    async def _add_topics(self, page, topics: list[str]) -> None:
        """Add topic hashtags by typing # and selecting from dropdown."""
        for topic in topics:
            try:
                clean = topic.strip().lstrip("#")
                if not clean:
                    continue

                editor = page.locator('#post-textarea, div.ql-editor, div[contenteditable="true"]').last
                await editor.click()
                await page.keyboard.press("End")
                await page.keyboard.type(f" #{clean}", delay=80)

                await page.wait_for_timeout(2000)

                dropdown_selectors = [
                    '[class*="topic-list"] [class*="item"]',
                    '[class*="mention-list"] [class*="item"]',
                    '[class*="hash-tag"] [class*="item"]',
                    '[class*="suggest"] [class*="item"]',
                    '[class*="dropdown"] [class*="option"]',
                ]
                clicked = False
                for dd_sel in dropdown_selectors:
                    try:
                        items = page.locator(dd_sel)
                        if await items.count() > 0:
                            await items.first.click()
                            clicked = True
                            logger.info("[XHSPublish] topic '%s' selected from dropdown (%s)", clean, dd_sel)
                            break
                    except Exception:
                        continue

                if not clicked:
                    logger.info("[XHSPublish] topic '%s' typed (no dropdown match)", clean)

                await page.wait_for_timeout(500)

            except Exception as e:
                logger.warning("[XHSPublish] add topic '%s' failed: %s", topic, e)

    # ── Publish ───────────────────────────────────────────────────

    async def _click_publish(self, page) -> dict:
        """Click the publish button and wait for result."""
        selectors = [
            'button:has-text("发布")',
            'button:has-text("发布笔记")',
            '[class*="publish"] button',
            'button.css-k0lszz',
            'button[class*="submit"]',
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_enabled():
                    await btn.click()
                    logger.info("[XHSPublish] publish button clicked via: %s", sel)
                    break
            except Exception:
                continue
        else:
            return {"status": "failed", "error": "未找到发布按钮"}

        await page.wait_for_timeout(3000)

        for _ in range(20):
            await page.wait_for_timeout(2000)
            current_url = page.url

            success_indicators = [
                "publish/success",
                "/creator/home",
                "publish-success",
            ]
            for indicator in success_indicators:
                if indicator in current_url.lower():
                    note_url = current_url
                    try:
                        link = page.locator('a[href*="/explore/"]').first
                        if await link.count() > 0:
                            note_url = await link.get_attribute("href") or current_url
                    except Exception:
                        pass
                    return {"status": "published", "note_url": note_url}

            try:
                success_text = page.locator(':text("发布成功"), :text("已发布")')
                if await success_text.count() > 0:
                    return {"status": "published", "note_url": current_url}
            except Exception:
                pass

            try:
                error_text = page.locator('[class*="error"], [class*="fail"]')
                if await error_text.count() > 0 and await error_text.first.is_visible():
                    err_msg = await error_text.first.text_content() or "发布失败"
                    return {"status": "failed", "error": err_msg}
            except Exception:
                pass

        return {"status": "published", "note_url": page.url}

    # ── Cookie injection ──────────────────────────────────────────

    @staticmethod
    async def _inject_cookies(context, cookie_str: str) -> None:
        """Parse and inject cookies from string."""
        cookies = []
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" not in item:
                continue
            name, _, value = item.partition("=")
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".xiaohongshu.com",
                "path": "/",
            })
        if cookies:
            await context.add_cookies(cookies)
            logger.info("[XHSPublish] injected %d cookies", len(cookies))


def build_publish_content(hook_script: dict, spec: dict | None = None) -> dict:
    """From hook_script + spec, assemble title / body / topics for publish."""
    opening = hook_script.get("opening_line", "")
    supporting = hook_script.get("supporting_line", "")
    cta = hook_script.get("cta_line", "")

    title = opening[:_XHS_TITLE_MAX_LEN] if opening else "前3秒视频"

    body_parts = []
    if opening:
        body_parts.append(f"✨ {opening}")
    if supporting:
        body_parts.append(supporting)
    if cta:
        body_parts.append(f"\n👉 {cta}")

    body = "\n\n".join(body_parts)

    topics = []
    if spec:
        for scenario in spec.get("target_scenarios", [])[:2]:
            topics.append(scenario)
        claim = spec.get("core_claim", "")
        if claim:
            import re
            words = re.findall(r"[\u4e00-\u9fff]{2,6}", claim)
            for w in words[:2]:
                if w not in topics:
                    topics.append(w)

    if not topics:
        topics = ["好物推荐", "短视频"]

    return {"title": title, "body": body, "topics": topics}
