"""ImageGeneratorService: 多通道文生图（OpenRouter Gemini 优先，DashScope 通义万相 fallback）。"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_GENERATED_DIR = Path(__file__).resolve().parents[3] / "data" / "generated_images"

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DASHSCOPE_DEFAULT_MODEL = os.environ.get("IMAGE_GEN_MODEL", "wanx2.1-t2i-turbo")
_DASHSCOPE_FALLBACK_MODEL = "wanx-v1"
_POLL_INTERVAL = 2.0
_MAX_POLL_SECONDS = 120.0


class ImagePrompt(BaseModel):
    slot_id: str = Field(description="cover | content_1 | content_2 ...")
    prompt: str
    negative_prompt: str = ""
    size: str = "1024*1024"
    ref_image_url: str = Field(default="", description="参考图 URL（原始笔记封面等），非空时启用参考图模式")


class ImageResult(BaseModel):
    slot_id: str
    status: str = "pending"
    image_url: str = ""
    error: str = ""
    elapsed_ms: int = 0
    provider: str = ""
    final_prompt: str = ""
    final_negative_prompt: str = ""
    gen_mode: str = ""
    user_edited: bool = False


class PromptSource(BaseModel):
    """追溯单条 prompt 片段的来源。"""
    field: str = Field(description="e.g. strategy.image_strategy")
    content: str = Field(description="该字段贡献的文本片段")
    priority: int = Field(default=0, description="融合优先级，数字越小越高")


class RichImagePrompt(BaseModel):
    """融合多数据源后的结构化 prompt，供 Prompt Builder 展示 + 编辑。"""
    slot_id: str
    prompt_text: str = Field(default="", description="融合后的完整正向 prompt（只读计算字段）")
    negative_prompt: str = Field(default="", description="融合后的负向 prompt")
    style_tags: list[str] = Field(default_factory=list, description="风格标签")
    subject: str = Field(default="", description="主体描述")
    must_include: list[str] = Field(default_factory=list, description="必含元素")
    avoid_items: list[str] = Field(default_factory=list, description="规避元素")
    ref_image_url: str = ""
    sources: list[PromptSource] = Field(default_factory=list, description="可追溯的来源分解")
    size: str = "1024*1024"

    def compose_prompt_text(self) -> str:
        """从结构化字段重新组装完整 prompt 文本。"""
        parts: list[str] = []
        if self.subject:
            parts.append(self.subject)
        if self.must_include:
            parts.append("必含元素：" + "、".join(self.must_include))
        if self.style_tags:
            parts.append("风格：" + "、".join(self.style_tags))
        return "，".join(parts) if parts else self.prompt_text

    def to_image_prompt(self) -> "ImagePrompt":
        full_prompt = self.compose_prompt_text() or self.prompt_text
        return ImagePrompt(
            slot_id=self.slot_id,
            prompt=full_prompt,
            negative_prompt=self.negative_prompt,
            size=self.size,
            ref_image_url=self.ref_image_url,
        )


class ImageGeneratorService:
    """多通道文生图服务：OpenRouter Gemini 优先，DashScope 通义万相 fallback。"""

    def __init__(self) -> None:
        self._openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        self._openrouter_model = os.environ.get("OPENROUTER_IMAGE_MODEL", "google/gemini-3.1-flash-image-preview")
        self._dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "")

    def is_available(self) -> bool:
        return self._is_openrouter_available() or self._is_dashscope_available()

    def _is_openrouter_available(self) -> bool:
        if not self._openrouter_key:
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def _is_dashscope_available(self) -> bool:
        if not self._dashscope_key:
            return False
        try:
            from dashscope import ImageSynthesis  # noqa: F401
            return True
        except ImportError:
            return False

    def generate_single(
        self,
        prompt: ImagePrompt,
        opportunity_id: str,
        on_progress: Callable[[str, str, dict[str, Any]], None] | None = None,
        provider: str = "auto",
    ) -> ImageResult:
        if not self.is_available():
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error="图片生成服务不可用（缺少 API Key 或 SDK）")

        if on_progress:
            on_progress(prompt.slot_id, "generating", {"prompt": prompt.prompt[:60]})

        if provider == "openrouter":
            if self._is_openrouter_available():
                return self._generate_openrouter(prompt, opportunity_id, on_progress)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error="OpenRouter 不可用（缺少 OPENROUTER_API_KEY）")

        if provider == "dashscope":
            if self._is_dashscope_available():
                return self._generate_dashscope(prompt, opportunity_id, on_progress)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error="通义万相不可用（缺少 DASHSCOPE_API_KEY）")

        if self._is_openrouter_available():
            result = self._generate_openrouter(prompt, opportunity_id, on_progress)
            if result.status == "completed":
                return result
            logger.warning("OpenRouter failed for slot=%s: %s, trying DashScope", prompt.slot_id, result.error)

        if self._is_dashscope_available():
            return self._generate_dashscope(prompt, opportunity_id, on_progress)

        return ImageResult(slot_id=prompt.slot_id, status="failed", error="所有图片生成通道不可用")

    # ── OpenRouter / Gemini ──────────────────────────────────────────

    def _generate_openrouter(
        self,
        prompt: ImagePrompt,
        opportunity_id: str,
        on_progress: Callable[[str, str, dict[str, Any]], None] | None = None,
    ) -> ImageResult:
        import openai

        t0 = time.perf_counter()
        try:
            client = openai.OpenAI(
                base_url=_OPENROUTER_BASE_URL,
                api_key=self._openrouter_key,
            )

            text_instruction = f"请根据以下描述生成一张高质量图片，适合作为小红书笔记配图。\n\n描述：{prompt.prompt}"
            if prompt.negative_prompt:
                text_instruction += f"\n\n避免：{prompt.negative_prompt}"

            if prompt.ref_image_url:
                text_instruction = f"请参考这张图片的风格和构图，根据以下描述生成一张新的高质量配图。\n\n描述：{prompt.prompt}"
                if prompt.negative_prompt:
                    text_instruction += f"\n\n避免：{prompt.negative_prompt}"
                user_msg_content: Any = [
                    {"type": "image_url", "image_url": {"url": prompt.ref_image_url}},
                    {"type": "text", "text": text_instruction},
                ]
            else:
                user_msg_content = text_instruction

            raw_response = client.chat.completions.with_raw_response.create(
                model=self._openrouter_model,
                messages=[
                    {"role": "user", "content": user_msg_content},
                ],
                max_tokens=4096,
            )

            raw_json = json.loads(raw_response.text.strip())
            choices = raw_json.get("choices", [])
            if not choices:
                elapsed = int((time.perf_counter() - t0) * 1000)
                return ImageResult(slot_id=prompt.slot_id, status="failed",
                                   error="OpenRouter 返回空响应", elapsed_ms=elapsed, provider="openrouter")

            msg = choices[0].get("message", {})

            images = msg.get("images", [])
            if images:
                for img_item in images:
                    url = ""
                    if isinstance(img_item, dict):
                        url_obj = img_item.get("image_url", {})
                        url = url_obj.get("url", "") if isinstance(url_obj, dict) else str(url_obj)
                    if url:
                        image_path = self._extract_and_save_image(url, opportunity_id, prompt.slot_id)
                        if image_path:
                            elapsed = int((time.perf_counter() - t0) * 1000)
                            serve_url = f"/generated-images/{opportunity_id}/{image_path.name}"
                            logger.info("OpenRouter image (via images[]): slot=%s elapsed=%dms", prompt.slot_id, elapsed)
                            if on_progress:
                                on_progress(prompt.slot_id, "completed", {"image_url": serve_url, "provider": "openrouter"})
                            return ImageResult(slot_id=prompt.slot_id, status="completed",
                                               image_url=serve_url, elapsed_ms=elapsed, provider="openrouter")

            content = msg.get("content") or ""
            if content:
                image_path = self._extract_and_save_image(content, opportunity_id, prompt.slot_id)
                if image_path:
                    elapsed = int((time.perf_counter() - t0) * 1000)
                    serve_url = f"/generated-images/{opportunity_id}/{image_path.name}"
                    logger.info("OpenRouter image (via content): slot=%s elapsed=%dms", prompt.slot_id, elapsed)
                    if on_progress:
                        on_progress(prompt.slot_id, "completed", {"image_url": serve_url, "provider": "openrouter"})
                    return ImageResult(slot_id=prompt.slot_id, status="completed",
                                       image_url=serve_url, elapsed_ms=elapsed, provider="openrouter")

            image_path = self._extract_multipart_image(msg, opportunity_id, prompt.slot_id)
            if image_path:
                elapsed = int((time.perf_counter() - t0) * 1000)
                serve_url = f"/generated-images/{opportunity_id}/{image_path.name}"
                if on_progress:
                    on_progress(prompt.slot_id, "completed", {"image_url": serve_url, "provider": "openrouter"})
                return ImageResult(slot_id=prompt.slot_id, status="completed",
                                   image_url=serve_url, elapsed_ms=elapsed, provider="openrouter")

            elapsed = int((time.perf_counter() - t0) * 1000)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error="OpenRouter 响应中未找到图片数据", elapsed_ms=elapsed, provider="openrouter")

        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("OpenRouter image gen error: %s", exc, exc_info=True)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error=f"OpenRouter: {exc}", elapsed_ms=elapsed, provider="openrouter")

    def _extract_and_save_image(self, content: str, opportunity_id: str, slot_id: str) -> Path | None:
        """从响应内容中提取 base64 图片或 URL 并保存。"""
        import re

        b64_match = re.search(r'data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\n]+)', content)
        if b64_match:
            fmt = b64_match.group(1)
            b64_data = b64_match.group(2).replace('\n', '')
            return self._save_base64(b64_data, opportunity_id, slot_id, fmt)

        b64_block = re.search(r'```(?:base64)?\s*\n?([A-Za-z0-9+/=\n]{100,})\s*```', content)
        if b64_block:
            b64_data = b64_block.group(1).replace('\n', '')
            return self._save_base64(b64_data, opportunity_id, slot_id, "png")

        url_match = re.search(r'https?://\S+\.(?:png|jpg|jpeg|webp)\S*', content)
        if url_match:
            return self._save_from_url(url_match.group(0), opportunity_id, slot_id)

        if len(content) > 500:
            cleaned = content.strip()
            if all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n ' for c in cleaned[:200]):
                b64_data = cleaned.replace('\n', '').replace(' ', '')
                if len(b64_data) > 1000:
                    return self._save_base64(b64_data, opportunity_id, slot_id, "png")

        return None

    def _extract_multipart_image(self, raw: Any, opportunity_id: str, slot_id: str) -> Path | None:
        """从多模态响应的 raw 结构中提取图片。"""
        if not isinstance(raw, dict):
            return None

        content_parts = raw.get("content", [])
        if isinstance(content_parts, list):
            for part in content_parts:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "image_url":
                    url_obj = part.get("image_url", {})
                    url = url_obj.get("url", "") if isinstance(url_obj, dict) else ""
                    if url.startswith("data:image"):
                        import re
                        m = re.match(r'data:image/(\w+);base64,(.+)', url)
                        if m:
                            return self._save_base64(m.group(2), opportunity_id, slot_id, m.group(1))
                    elif url.startswith("http"):
                        return self._save_from_url(url, opportunity_id, slot_id)

                inline_data = part.get("inline_data", {})
                if isinstance(inline_data, dict) and inline_data.get("data"):
                    mime = inline_data.get("mime_type", "image/png")
                    fmt = mime.split("/")[-1] if "/" in mime else "png"
                    return self._save_base64(inline_data["data"], opportunity_id, slot_id, fmt)

        return None

    # ── DashScope 通义万相 ───────────────────────────────────────────

    def _generate_dashscope(
        self,
        prompt: ImagePrompt,
        opportunity_id: str,
        on_progress: Callable[[str, str, dict[str, Any]], None] | None = None,
    ) -> ImageResult:
        from dashscope import ImageSynthesis

        t0 = time.perf_counter()
        try:
            if prompt.ref_image_url:
                rsp = ImageSynthesis.async_call(
                    model="wanx2.1-imageedit",
                    prompt=prompt.prompt,
                    negative_prompt=prompt.negative_prompt or None,
                    n=1,
                    function="stylization_all",
                    base_image_url=prompt.ref_image_url,
                    api_key=self._dashscope_key,
                )
                if rsp.status_code != 200:
                    logger.warning("DashScope imageedit failed (%s), falling back to text-only", rsp.get("message", ""))
                    rsp = ImageSynthesis.async_call(
                        model=_DASHSCOPE_DEFAULT_MODEL,
                        prompt=prompt.prompt,
                        negative_prompt=prompt.negative_prompt or None,
                        n=1,
                        size=prompt.size,
                        api_key=self._dashscope_key,
                    )
            else:
                rsp = ImageSynthesis.async_call(
                    model=_DASHSCOPE_DEFAULT_MODEL,
                    prompt=prompt.prompt,
                    negative_prompt=prompt.negative_prompt or None,
                    n=1,
                    size=prompt.size,
                    api_key=self._dashscope_key,
                )

            if rsp.status_code != 200:
                rsp = ImageSynthesis.async_call(
                    model=_DASHSCOPE_FALLBACK_MODEL,
                    prompt=prompt.prompt,
                    negative_prompt=prompt.negative_prompt or None,
                    n=1,
                    size=prompt.size,
                    api_key=self._dashscope_key,
                )

            if rsp.status_code != 200:
                elapsed = int((time.perf_counter() - t0) * 1000)
                err_msg = f"提交任务失败: {rsp.get('code', '')} {rsp.get('message', '')}"
                return ImageResult(slot_id=prompt.slot_id, status="failed",
                                   error=err_msg, elapsed_ms=elapsed, provider="dashscope")

            task_id = rsp.output.get("task_id", "")
            logger.info("DashScope task submitted: slot=%s task_id=%s", prompt.slot_id, task_id)

            deadline = time.perf_counter() + _MAX_POLL_SECONDS
            while time.perf_counter() < deadline:
                time.sleep(_POLL_INTERVAL)
                status_rsp = ImageSynthesis.fetch(task_id, api_key=self._dashscope_key)
                task_status = status_rsp.output.get("task_status", "")

                if task_status == "SUCCEEDED":
                    results = status_rsp.output.get("results", [])
                    if results:
                        remote_url = results[0].get("url", "") or results[0].get("b64_image", "")
                        local_path = self._save_from_url(remote_url, opportunity_id, prompt.slot_id)
                        if local_path:
                            elapsed = int((time.perf_counter() - t0) * 1000)
                            serve_url = f"/generated-images/{opportunity_id}/{local_path.name}"
                            if on_progress:
                                on_progress(prompt.slot_id, "completed", {"image_url": serve_url, "provider": "dashscope"})
                            return ImageResult(slot_id=prompt.slot_id, status="completed",
                                               image_url=serve_url, elapsed_ms=elapsed, provider="dashscope")
                    break

                if task_status in ("FAILED", "UNKNOWN"):
                    err = status_rsp.output.get("message", "任务失败")
                    elapsed = int((time.perf_counter() - t0) * 1000)
                    if on_progress:
                        on_progress(prompt.slot_id, "failed", {"error": err})
                    return ImageResult(slot_id=prompt.slot_id, status="failed",
                                       error=err, elapsed_ms=elapsed, provider="dashscope")

            elapsed = int((time.perf_counter() - t0) * 1000)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error="DashScope 生成超时", elapsed_ms=elapsed, provider="dashscope")

        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("DashScope image gen error: %s", exc, exc_info=True)
            if on_progress:
                on_progress(prompt.slot_id, "failed", {"error": str(exc)})
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error=str(exc), elapsed_ms=elapsed, provider="dashscope")

    # ── 共用工具 ─────────────────────────────────────────────────────

    def generate_batch(
        self,
        prompts: list[ImagePrompt],
        opportunity_id: str,
        on_progress: Callable[[str, str, dict[str, Any]], None] | None = None,
        provider: str = "auto",
    ) -> list[ImageResult]:
        results: list[ImageResult] = []
        for i, prompt in enumerate(prompts):
            if on_progress:
                on_progress(prompt.slot_id, "queued", {"index": i, "total": len(prompts)})
            result = self.generate_single(prompt, opportunity_id, on_progress=on_progress, provider=provider)
            results.append(result)
        return results

    @staticmethod
    def _save_base64(b64_data: str, opportunity_id: str, slot_id: str, fmt: str = "png") -> Path:
        out_dir = _GENERATED_DIR / opportunity_id
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = f".{fmt}" if not fmt.startswith(".") else fmt
        if suffix in (".jpeg",):
            suffix = ".jpg"
        filename = f"{slot_id}_{uuid.uuid4().hex[:8]}{suffix}"
        out_path = out_dir / filename
        out_path.write_bytes(base64.b64decode(b64_data))
        logger.info("Image saved (base64): %s (%d bytes)", out_path, out_path.stat().st_size)
        return out_path

    @staticmethod
    def _save_from_url(url: str, opportunity_id: str, slot_id: str) -> Path | None:
        out_dir = _GENERATED_DIR / opportunity_id
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".png"
        if ".jpg" in url or ".jpeg" in url:
            suffix = ".jpg"
        elif ".webp" in url:
            suffix = ".webp"
        filename = f"{slot_id}_{uuid.uuid4().hex[:8]}{suffix}"
        out_path = out_dir / filename
        try:
            urllib.request.urlretrieve(url, str(out_path))
            logger.info("Image saved (url): %s (%d bytes)", out_path, out_path.stat().st_size)
            return out_path
        except Exception as exc:
            logger.warning("Failed to download image from %s: %s", url, exc)
            return None


def extract_image_prompts_from_draft(
    draft: dict[str, Any],
    brief: Any | None = None,
    ref_image_urls: list[str] | None = None,
) -> list[ImagePrompt]:
    """从 quick_draft + brief 提取需要生成的图片描述列表。

    ref_image_urls: 原始笔记的图片 URL 列表（第 0 张为封面）。
    非空时，每张生成 prompt 会附带对应的 ref_image_url，供服务选择参考图模式。
    """
    prompts: list[ImagePrompt] = []
    refs = ref_image_urls or []

    cover_prompt = draft.get("cover_image_prompt", "")
    if cover_prompt:
        prompts.append(ImagePrompt(
            slot_id="cover", prompt=cover_prompt, size="1024*1024",
            ref_image_url=refs[0] if refs else "",
        ))

    if brief is not None:
        image_plan = getattr(brief, "image_plan", None)
        if image_plan and hasattr(image_plan, "image_slots"):
            for i, slot in enumerate(image_plan.image_slots[:4]):
                desc = getattr(slot, "description", "") or getattr(slot, "subject", "") or ""
                if desc and desc != cover_prompt:
                    ref_url = refs[i + 1] if (i + 1) < len(refs) else (refs[0] if refs else "")
                    prompts.append(ImagePrompt(
                        slot_id=f"content_{i + 1}",
                        prompt=desc,
                        size="1024*1024",
                        ref_image_url=ref_url,
                    ))

    if not prompts:
        visual = ""
        if brief:
            visual = getattr(brief, "visual_direction", "") or getattr(brief, "cover_direction", "") or ""
        if visual:
            prompts.append(ImagePrompt(
                slot_id="cover", prompt=visual, size="1024*1024",
                ref_image_url=refs[0] if refs else "",
            ))

    return prompts
