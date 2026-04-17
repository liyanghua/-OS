"""VideoGeneratorService: OpenRouter Seedance 2.0 Fast 异步视频生成。

Workflow:
  1. POST /api/v1/videos  -> {id, polling_url, status}
  2. GET  polling_url      -> {status, unsigned_urls, ...}
  3. Download video to local storage
"""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = _REPO_ROOT / "data"
_GENERATED_VIDEOS_DIR = _DATA_DIR / "generated_videos"
_GENERATED_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

_OPENROUTER_VIDEO_URL = "https://openrouter.ai/api/v1/videos"
_DEFAULT_MODEL = "bytedance/seedance-2.0-fast"
_POLL_INTERVAL = 15.0
_MAX_POLL_SECONDS = 300.0

_WEB_PATH_MAP: dict[str, Path] = {
    "/source-images/": _DATA_DIR / "source_images",
    "/generated-images/": _DATA_DIR / "generated_images",
}
_MAX_FRAME_BYTES = 8 * 1024 * 1024  # 8 MB guard


def _guess_mime(file_path: str, content_type: str = "") -> str:
    mime, _ = mimetypes.guess_type(file_path)
    if mime and mime.startswith("image/"):
        return mime
    if content_type and content_type.startswith("image/"):
        return content_type.split(";")[0].strip()
    return "image/jpeg"


async def _resolve_to_data_uri(url: str) -> str | None:
    """Convert a first-frame URL (local web path, https, or data URI) to a
    base64 data URI suitable for the OpenRouter frame_images payload.

    Returns None (with a warning log) when resolution fails, so the caller
    can gracefully fall back to text-to-video.
    """
    if not url or not url.strip():
        return None

    url = url.strip()

    if url.startswith("data:"):
        return url

    # --- local web path (/source-images/... or /generated-images/...) ---
    for prefix, base_dir in _WEB_PATH_MAP.items():
        if url.startswith(prefix):
            rel = url[len(prefix):]
            local_path = base_dir / rel
            if not local_path.is_file():
                logger.warning("[VideoGen] local file not found: %s", local_path)
                return None
            raw = local_path.read_bytes()
            if len(raw) > _MAX_FRAME_BYTES:
                logger.warning("[VideoGen] local file too large (%d bytes): %s", len(raw), local_path)
                return None
            mime = _guess_mime(str(local_path))
            b64 = base64.b64encode(raw).decode()
            logger.info("[VideoGen] resolved local frame: %s (%d bytes, %s)", url[:80], len(raw), mime)
            return f"data:{mime};base64,{b64}"

    # --- remote URL (https / http) ---
    if url.startswith(("http://", "https://")):
        try:
            headers: dict[str, str] = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
            }
            if "xhscdn.com" in url or "xiaohongshu.com" in url:
                headers["Referer"] = "https://www.xiaohongshu.com/"

            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                raw = resp.content

            if len(raw) > _MAX_FRAME_BYTES:
                logger.warning("[VideoGen] remote image too large (%d bytes): %s", len(raw), url[:120])
                return None

            ct = resp.headers.get("content-type", "")
            mime = _guess_mime(url, ct)
            b64 = base64.b64encode(raw).decode()
            logger.info("[VideoGen] resolved remote frame: %s (%d bytes, %s)", url[:80], len(raw), mime)
            return f"data:{mime};base64,{b64}"
        except Exception:
            logger.warning("[VideoGen] failed to download remote frame: %s", url[:120], exc_info=True)
            return None

    logger.warning("[VideoGen] unrecognized first_frame_url format: %s", url[:120])
    return None


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


class VideoGeneratorService:
    """Seedance 2.0 Fast video generation via OpenRouter async API."""

    def __init__(self) -> None:
        self._api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self._model = os.environ.get("VIDEO_GEN_MODEL", _DEFAULT_MODEL)

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def submit_job(
        self,
        prompt: str,
        *,
        first_frame_url: str = "",
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
        duration: int = 5,
    ) -> dict:
        """Submit a video generation job. Returns {id, polling_url, status}."""
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "duration": duration,
        }
        frame_resolved = False
        if first_frame_url:
            data_uri = await _resolve_to_data_uri(first_frame_url)
            if data_uri:
                payload["frame_images"] = [{
                    "type": "image_url",
                    "image_url": {"url": data_uri},
                    "frame_type": "first_frame",
                }]
                frame_resolved = True
            else:
                logger.warning(
                    "[VideoGen] first_frame unavailable, fallback to text-to-video: %s",
                    first_frame_url[:120],
                )

        logger.info(
            "[VideoGen] submit: model=%s prompt_len=%d first_frame=%s(resolved=%s) aspect=%s",
            self._model, len(prompt), bool(first_frame_url), frame_resolved, aspect_ratio,
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _OPENROUTER_VIDEO_URL,
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code >= 400:
                logger.error(
                    "[VideoGen] OpenRouter %d: %s",
                    resp.status_code, resp.text[:1000],
                )
            resp.raise_for_status()
            data = resp.json()

        logger.info("[VideoGen] job submitted: id=%s status=%s", data.get("id"), data.get("status"))
        return data

    async def poll_status(self, polling_url: str) -> dict:
        """Poll the job status. Returns full status dict."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(polling_url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def download_video(self, content_url: str, variant_id: str) -> str:
        """Download video to local storage. Returns web-accessible path."""
        out_dir = _GENERATED_VIDEOS_DIR / variant_id
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / "video.mp4"

        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.get(content_url, headers=self._headers())
            resp.raise_for_status()
            dest.write_bytes(resp.content)

        web_path = f"/generated-videos/{variant_id}/video.mp4"
        logger.info("[VideoGen] downloaded: %s (%d bytes)", web_path, dest.stat().st_size)
        return web_path

    async def generate_and_wait(
        self,
        prompt: str,
        variant_id: str,
        *,
        first_frame_url: str = "",
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Submit -> poll -> download. Returns {status, video_url, elapsed_ms, job_id, frame_dropped}."""
        start = time.monotonic()

        frame_dropped = False
        try:
            job = await self.submit_job(
                prompt,
                first_frame_url=first_frame_url,
                aspect_ratio=aspect_ratio,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400 and first_frame_url:
                logger.warning(
                    "[VideoGen] frame rejected (likely content policy), retrying without frame: %s",
                    first_frame_url[:120],
                )
                job = await self.submit_job(
                    prompt,
                    first_frame_url="",
                    aspect_ratio=aspect_ratio,
                )
                frame_dropped = True
            else:
                raise

        job_id = job.get("id", "")
        polling_url = job.get("polling_url", "")

        if not polling_url:
            return {"status": "failed", "error": "No polling_url returned", "job_id": job_id, "frame_dropped": frame_dropped}

        elapsed_limit = _MAX_POLL_SECONDS
        while (time.monotonic() - start) < elapsed_limit:
            await asyncio.sleep(_POLL_INTERVAL)
            status_data = await self.poll_status(polling_url)
            st = status_data.get("status", "")
            logger.info("[VideoGen] poll: job=%s status=%s", job_id, st)

            if st == "completed":
                urls = status_data.get("unsigned_urls", [])
                if not urls:
                    return {"status": "failed", "error": "No video URL in response", "job_id": job_id, "frame_dropped": frame_dropped}
                video_url = await self.download_video(urls[0], variant_id)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                return {
                    "status": "completed",
                    "video_url": video_url,
                    "elapsed_ms": elapsed_ms,
                    "job_id": job_id,
                    "usage": status_data.get("usage"),
                    "frame_dropped": frame_dropped,
                }
            elif st == "failed":
                return {
                    "status": "failed",
                    "error": status_data.get("error", "Unknown error"),
                    "job_id": job_id,
                    "frame_dropped": frame_dropped,
                }

        return {"status": "timeout", "error": "Polling exceeded time limit", "job_id": job_id, "frame_dropped": frame_dropped}
