"""VideoGeneratorService: OpenRouter Seedance 2.0 Fast 异步视频生成。

Workflow:
  1. POST /api/v1/videos  -> {id, polling_url, status}
  2. GET  polling_url      -> {status, unsigned_urls, ...}
  3. Download video to local storage
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATED_VIDEOS_DIR = _REPO_ROOT / "data" / "generated_videos"
_GENERATED_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

_OPENROUTER_VIDEO_URL = "https://openrouter.ai/api/v1/videos"
_DEFAULT_MODEL = "bytedance/seedance-2.0-fast"
_POLL_INTERVAL = 15.0
_MAX_POLL_SECONDS = 300.0


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
        if first_frame_url:
            payload["frame_images"] = [{
                "type": "image_url",
                "image_url": {"url": first_frame_url},
                "frame_type": "first_frame",
            }]

        logger.info(
            "[VideoGen] submit: model=%s prompt_len=%d first_frame=%s aspect=%s",
            self._model, len(prompt), bool(first_frame_url), aspect_ratio,
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _OPENROUTER_VIDEO_URL,
                headers=self._headers(),
                json=payload,
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
        """Submit -> poll -> download. Returns {status, video_url, elapsed_ms, job_id}."""
        start = time.monotonic()

        job = await self.submit_job(
            prompt,
            first_frame_url=first_frame_url,
            aspect_ratio=aspect_ratio,
        )
        job_id = job.get("id", "")
        polling_url = job.get("polling_url", "")

        if not polling_url:
            return {"status": "failed", "error": "No polling_url returned", "job_id": job_id}

        elapsed_limit = _MAX_POLL_SECONDS
        while (time.monotonic() - start) < elapsed_limit:
            await asyncio.sleep(_POLL_INTERVAL)
            status_data = await self.poll_status(polling_url)
            st = status_data.get("status", "")
            logger.info("[VideoGen] poll: job=%s status=%s", job_id, st)

            if st == "completed":
                urls = status_data.get("unsigned_urls", [])
                if not urls:
                    return {"status": "failed", "error": "No video URL in response", "job_id": job_id}
                video_url = await self.download_video(urls[0], variant_id)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                return {
                    "status": "completed",
                    "video_url": video_url,
                    "elapsed_ms": elapsed_ms,
                    "job_id": job_id,
                    "usage": status_data.get("usage"),
                }
            elif st == "failed":
                return {
                    "status": "failed",
                    "error": status_data.get("error", "Unknown error"),
                    "job_id": job_id,
                }

        return {"status": "timeout", "error": "Polling exceeded time limit", "job_id": job_id}
