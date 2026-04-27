"""ImageGeneratorService: 多通道文生图（图片网关 + DashScope fallback）。"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

def _ensure_env() -> None:
    """Ensure .env is loaded – always reads the file to fill any missing keys."""
    env_file = Path(__file__).resolve().parents[3] / ".env"
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

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATED_DIR = _REPO_ROOT / "data" / "generated_images"
_SOURCE_IMAGES_DIR = _REPO_ROOT / "data" / "source_images"
_DEFAULT_IMAGE_GATEWAY_BASE_URL = "https://openrouter.ai/api/v1"
_DASHSCOPE_DEFAULT_MODEL = os.environ.get("IMAGE_GEN_MODEL", "wan2.5-t2i-preview")
_DASHSCOPE_FALLBACK_MODEL = os.environ.get("IMAGE_GEN_FALLBACK_MODEL", "wanx2.1-t2i-turbo")
_DASHSCOPE_IMAGE_EDIT_MODEL = os.environ.get("DASHSCOPE_IMAGE_EDIT_MODEL", "qwen-image-edit")

# OpenAI 系图像模型在 OpenRouter chat/completions 接口需要显式声明 modalities，否则只回文本。
_OPENROUTER_NEEDS_MODALITIES: set[str] = {
    "openai/gpt-5.4-image-2",
}

# 部分模型可能由独立 OpenRouter 账号供给（独立配额）。命中映射时使用对应环境变量里的 key，
# 未配置时回落到 OPENROUTER_API_KEY。
_OPENROUTER_KEY_OVERRIDES: dict[str, str] = {
    "openai/gpt-5.4-image-2": "OPENROUTER_GPT5_IMAGE_KEY",
}

# wan2.5-t2i-preview 要求总像素 [1280*1280, 1440*1440]，宽高比 [1:4, 4:1]；
# wanx2.1/2.2 系列要求 [512, 1440] 单边且 <= 1440*1440。
# 这里只存两套常用比例；未在表里的 aspect 会退回到 1:1。
_WAN25_SIZE_BY_ASPECT = {
    "1:1": "1280*1280",
    "3:4": "1104*1472",
    "4:3": "1472*1104",
    "9:16": "960*1696",
    "16:9": "1696*960",
}
_WANX21_SIZE_BY_ASPECT = {
    "1:1": "1024*1024",
    "3:4": "864*1152",
    "4:3": "1152*864",
    "9:16": "720*1280",
    "16:9": "1280*720",
}


def _aspect_from_size(size: str) -> str:
    """把 '1024*1024' 等尺寸字符串反推一个最接近的比例标签。"""
    try:
        w, _, h = (size or "").partition("*")
        w_i = int(w); h_i = int(h)
        if w_i <= 0 or h_i <= 0:
            return "1:1"
        ratio = w_i / h_i
        if abs(ratio - 1.0) < 0.05:
            return "1:1"
        if abs(ratio - 3 / 4) < 0.05:
            return "3:4"
        if abs(ratio - 4 / 3) < 0.05:
            return "4:3"
        if abs(ratio - 9 / 16) < 0.05:
            return "9:16"
        if abs(ratio - 16 / 9) < 0.05:
            return "16:9"
    except Exception:
        pass
    return "1:1"


def _size_for_dashscope_model(model_name: str, requested_size: str) -> str:
    """按模型映射到对应分辨率档位，避免 wan2.5 拒收小尺寸 / wanx 拒收大尺寸。"""
    aspect = _aspect_from_size(requested_size)
    if "wan2.5" in (model_name or "").lower():
        return _WAN25_SIZE_BY_ASPECT.get(aspect, _WAN25_SIZE_BY_ASPECT["1:1"])
    # wanx2.1 / wanx-v1 / 其它
    return _WANX21_SIZE_BY_ASPECT.get(aspect, requested_size or "1024*1024")
_POLL_INTERVAL = 2.0
_MAX_POLL_SECONDS = 120.0


class ImagePrompt(BaseModel):
    slot_id: str = Field(description="cover | content_1 | content_2 ...")
    prompt: str
    negative_prompt: str = ""
    size: str = "1024*1024"
    ref_image_url: str = Field(default="", description="参考图 URL（原始笔记封面等），非空时启用参考图模式")
    mode: Literal["generate", "edit"] = Field(
        default="generate",
        description="generate=常规文生图/参考图生成；edit=以 ref_image_url 为底图的图生图微调（保构图）",
    )
    model: str = Field(
        default="",
        description="per-request 模型覆盖（如 wan2.5-t2i-preview / google/gemini-3.1-flash-image-preview）；留空则由服务按 provider 使用默认模型",
    )


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
    prompt_sent: str = Field(default="", description="实际发送给模型的完整提示词")
    ref_image_sent: str = Field(default="", description="实际发送的参考图 URL")


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
    """多通道文生图服务：DashScope 优先，图片网关作为第二通道。"""

    def __init__(self) -> None:
        _ensure_env()
        self._image_gateway_base_url = (
            os.environ.get("IMAGE_GEN_OPENAI_BASE_URL", _DEFAULT_IMAGE_GATEWAY_BASE_URL).strip()
            or _DEFAULT_IMAGE_GATEWAY_BASE_URL
        ).rstrip("/")
        self._openai_key = os.environ.get("OPENAI_API_KEY", "")
        self._openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        self._openrouter_gpt5_image_key = os.environ.get("OPENROUTER_GPT5_IMAGE_KEY", "")
        self._openrouter_override_keys = {
            "OPENROUTER_GPT5_IMAGE_KEY": self._openrouter_gpt5_image_key,
        }
        self._openrouter_model = os.environ.get("OPENROUTER_IMAGE_MODEL", "google/gemini-3.1-flash-image-preview")
        fallbacks_raw = os.environ.get("OPENROUTER_IMAGE_MODEL_FALLBACKS", "")
        self._openrouter_fallbacks = [
            m.strip() for m in fallbacks_raw.split(",") if m.strip() and m.strip() != self._openrouter_model
        ]
        self._dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "")

    def is_available(self) -> bool:
        return self._is_openrouter_available() or self._is_dashscope_available()

    def _uses_default_openrouter_gateway(self) -> bool:
        return self._image_gateway_base_url == _DEFAULT_IMAGE_GATEWAY_BASE_URL.rstrip("/")

    def _image_gateway_provider(self) -> str:
        return "openrouter" if self._uses_default_openrouter_gateway() else "openai_compatible"

    def _image_gateway_label(self) -> str:
        if self._uses_default_openrouter_gateway():
            return "OpenRouter"
        return f"图片网关({self._image_gateway_base_url})"

    def _image_gateway_missing_key_hint(self) -> str:
        if self._uses_default_openrouter_gateway():
            return "OPENROUTER_API_KEY"
        return "OPENAI_API_KEY"

    def _is_openrouter_available(self) -> bool:
        if self._uses_default_openrouter_gateway():
            if not (self._openrouter_key or self._openrouter_gpt5_image_key):
                return False
        elif not self._openai_key:
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def _resolve_openrouter_key(self, model_name: str) -> tuple[str, str]:
        """根据模型 ID 选择 OpenRouter API key。

        返回 (api_key, key_kind)。key_kind 仅用于日志，便于排查独立配额问题。
        命中 _OPENROUTER_KEY_OVERRIDES 且独立 key 已配置 → 用独立 key；否则回落到主 key。
        """
        env_var = _OPENROUTER_KEY_OVERRIDES.get(model_name or "")
        if env_var:
            override_key = self._openrouter_override_keys.get(env_var, "")
            if override_key:
                return override_key, env_var
        return self._openrouter_key, "OPENROUTER_API_KEY"

    def _resolve_image_gateway_key(self, model_name: str) -> tuple[str, str]:
        if self._uses_default_openrouter_gateway():
            return self._resolve_openrouter_key(model_name)
        return self._openai_key, "OPENAI_API_KEY"

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
                result = self._generate_openrouter(prompt, opportunity_id, on_progress)
                if result.status == "completed":
                    return result
                logger.warning(
                    "%s failed for slot=%s: %s, fallback to DashScope",
                    self._image_gateway_label(), prompt.slot_id, result.error,
                )
                if self._is_dashscope_available():
                    return self._generate_dashscope(prompt, opportunity_id, on_progress)
                return result
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error=(
                                   f"{self._image_gateway_label()} 不可用"
                                   f"（缺少 {self._image_gateway_missing_key_hint()}）"
                               ))

        if provider == "dashscope":
            if self._is_dashscope_available():
                result = self._generate_dashscope(prompt, opportunity_id, on_progress)
                if result.status == "completed":
                    return result
                logger.warning(
                    "DashScope failed for slot=%s: %s, fallback to %s",
                    prompt.slot_id, result.error, self._image_gateway_label(),
                )
                if self._is_openrouter_available():
                    return self._generate_openrouter(prompt, opportunity_id, on_progress)
                return result
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error="通义万相不可用（缺少 DASHSCOPE_API_KEY）")

        # auto 模式：DashScope 优先（更稳定），OpenRouter 备用
        if self._is_dashscope_available():
            result = self._generate_dashscope(prompt, opportunity_id, on_progress)
            if result.status == "completed":
                return result
            logger.warning(
                "DashScope failed for slot=%s: %s, trying %s",
                prompt.slot_id, result.error, self._image_gateway_label(),
            )

        if self._is_openrouter_available():
            return self._generate_openrouter(prompt, opportunity_id, on_progress)

        return ImageResult(slot_id=prompt.slot_id, status="failed", error="所有图片生成通道不可用")

    # ── OpenRouter / Gemini ──────────────────────────────────────────

    @staticmethod
    def _normalize_ref_image_url(ref_image_url: str) -> str:
        """把历史绝对路径等参考图地址归一成当前仓库可理解的形式。"""
        if not ref_image_url:
            return ""
        normalized = ref_image_url.strip().replace("\\", "/")
        if not normalized:
            return ""
        if normalized.startswith(("http://", "https://", "/source-images/", "/generated-images/")):
            return normalized
        marker = "/data/source_images/"
        idx = normalized.find(marker)
        if idx >= 0:
            rel = normalized[idx + len(marker):].lstrip("/")
            return f"/source-images/{rel}"
        return normalized

    @staticmethod
    def _resolve_local_path(file_path: str) -> Path | None:
        """把 URL/相对路径 规整成文件系统路径。
        支持：
        - 绝对文件系统路径
        - `/generated-images/{oid}/{name}` → `_GENERATED_DIR / oid / name`
        - `/source-images/{rel}` → `data/source_images/{rel}`（含用户上传的参考图）
        - 历史绝对路径 `.../data/source_images/{rel}` → 当前仓库 `data/source_images/{rel}`
        - 其它以 '/' 开头的 URL 路径暂不支持（返回 None）
        """
        if not file_path:
            return None
        file_path = ImageGeneratorService._normalize_ref_image_url(file_path)
        if file_path.startswith("/generated-images/"):
            rel = file_path[len("/generated-images/"):]
            candidate = _GENERATED_DIR / rel
            return candidate if candidate.is_file() else None
        if file_path.startswith("/source-images/"):
            rel = file_path[len("/source-images/"):]
            candidate = _SOURCE_IMAGES_DIR / rel
            return candidate if candidate.is_file() else None
        p = Path(file_path)
        return p if p.is_file() else None

    def _resolve_openrouter_ref(self, ref_image_url: str) -> tuple[str, str]:
        """返回 (规范化参考图, 可实际发送给图片网关的 URL/data URI)。"""
        from apps.content_planning.utils.ref_image_filter import is_usable_ref_url

        normalized = self._normalize_ref_image_url(ref_image_url)
        if not normalized:
            return "", ""
        if normalized.startswith(("http://", "https://")):
            if is_usable_ref_url(normalized):
                return normalized, normalized
            return normalized, ""
        local_path = self._resolve_local_path(normalized)
        if not local_path:
            return normalized, ""
        return normalized, self._local_path_to_data_uri(normalized)

    @staticmethod
    def _local_path_to_data_uri(file_path: str) -> str:
        """将本地图片文件转为 base64 data URI，供 OpenRouter multimodal 调用。"""
        p = ImageGeneratorService._resolve_local_path(file_path)
        if not p:
            logger.warning("Local ref image not found: %s", file_path)
            return ""
        mime = "image/jpeg"
        ext = p.suffix.lower()
        if ext == ".png":
            mime = "image/png"
        elif ext == ".webp":
            mime = "image/webp"
        elif ext == ".gif":
            mime = "image/gif"
        raw = p.read_bytes()
        b64 = base64.b64encode(raw).decode()
        return f"data:{mime};base64,{b64}"

    @staticmethod
    def _sanitize_prompt_for_openrouter(text: str) -> str:
        """Clean prompt text to reduce ToS false-positive rejections."""
        import re
        cleaned = text.strip()
        cleaned = re.sub(r"[^\w\s，。、：；！？\"'（）,.:;!?()\[\]{}#@&+=/\n-]", "", cleaned)
        if len(cleaned) > 600:
            cleaned = cleaned[:600]
        return cleaned

    @staticmethod
    def _is_openrouter_tos_error(exc: Exception) -> bool:
        """识别 OpenRouter/上游 provider 内容策略拒单（403 ToS）。"""
        import openai as _openai
        if isinstance(exc, _openai.PermissionDeniedError):
            return True
        msg = str(exc)
        return ("Terms Of Service" in msg) or ("prohibited" in msg and "provider" in msg)

    def _generate_openrouter(
        self,
        prompt: ImagePrompt,
        opportunity_id: str,
        on_progress: Callable[[str, str, dict[str, Any]], None] | None = None,
    ) -> ImageResult:
        """先用主模型调 OpenRouter；若被上游内容策略 403 拒绝，按 fallback 模型链逐个重试。

        若 prompt.model 非空（用户在 onboarding 选了具体模型），把它放到链路首位，
        仍然保留默认主模型 + 环境 fallback 作为兜底。
        """
        chain: list[str] = []
        if prompt.model:
            chain.append(prompt.model)
        chain.append(self._openrouter_model)
        chain.extend(self._openrouter_fallbacks)
        # 去重但保持顺序
        seen: set[str] = set()
        model_chain: list[str] = []
        for m in chain:
            if m and m not in seen:
                seen.add(m)
                model_chain.append(m)
        last_result: ImageResult | None = None
        for idx, model_name in enumerate(model_chain):
            result = self._generate_openrouter_once(prompt, opportunity_id, on_progress, model_name)
            if result.status == "completed":
                return result
            last_result = result
            # 可继续 fallback 的错误：
            # - ToS/403（上游内容策略拒绝）
            # - 模型不存在/404（"No endpoints found"）
            # - OpenRouter 400 "is not a valid model ID"（配置里写错了 ID）
            err_msg = result.error or ""
            err_lower = err_msg.lower()
            is_tos = ("Terms Of Service" in err_msg) or ("PermissionDenied" in err_msg) or ("403" in err_msg and "prohibited" in err_lower)
            is_missing = ("no endpoints found" in err_lower) or ("404" in err_msg) or ("not found" in err_lower and "model" in err_lower)
            is_invalid_id = ("not a valid model id" in err_lower) or ("invalid model" in err_lower and "400" in err_msg)
            if not (is_tos or is_missing or is_invalid_id):
                break
            if idx + 1 < len(model_chain):
                if is_tos: reason = "ToS 403"
                elif is_missing: reason = "model unavailable (404)"
                else: reason = "invalid model id (400)"
                logger.warning(
                    "%s %s from %s, fallback to %s",
                    self._image_gateway_label(), reason, model_name, model_chain[idx + 1],
                )
        return last_result or ImageResult(slot_id=prompt.slot_id, status="failed",
                                          error=f"{self._image_gateway_label()}: 无可用模型",
                                          provider=self._image_gateway_provider())

    def _generate_openrouter_once(
        self,
        prompt: ImagePrompt,
        opportunity_id: str,
        on_progress: Callable[[str, str, dict[str, Any]], None] | None,
        model_name: str,
    ) -> ImageResult:
        import openai

        t0 = time.perf_counter()
        api_key, key_kind = self._resolve_image_gateway_key(model_name)
        try:
            if not api_key:
                elapsed = int((time.perf_counter() - t0) * 1000)
                return ImageResult(
                    slot_id=prompt.slot_id, status="failed",
                    error=f"{self._image_gateway_label()}: 缺少 API key（model={model_name}, expected={key_kind}）",
                    elapsed_ms=elapsed, provider=self._image_gateway_provider(),
                )
            client = openai.OpenAI(
                base_url=self._image_gateway_base_url,
                api_key=api_key,
                timeout=60.0,
            )

            safe_prompt = self._sanitize_prompt_for_openrouter(prompt.prompt)
            safe_negative = self._sanitize_prompt_for_openrouter(prompt.negative_prompt) if prompt.negative_prompt else ""

            text_instruction = (
                "Generate a beautiful, high-quality photograph or illustration. "
                "This is for a lifestyle social media post.\n\n"
                f"Scene description: {safe_prompt}"
            )
            if safe_negative:
                text_instruction += f"\n\nPlease avoid: {safe_negative}"

            _prompt_sent = text_instruction

            ref_url_raw, ref_url_payload = self._resolve_openrouter_ref(prompt.ref_image_url or "")
            ref_usable = bool(ref_url_payload)
            if ref_url_raw and not ref_usable:
                logger.warning(
                    "%s request: slot=%s 参考图不可用，降级为 prompt_only：%r",
                    self._image_gateway_label(),
                    prompt.slot_id, ref_url_raw,
                )

            logger.info(
                "%s request: slot=%s, model=%s, key=%s, has_ref=%s, prompt_len=%d",
                self._image_gateway_label(), prompt.slot_id, model_name, key_kind, ref_usable, len(safe_prompt),
            )

            if ref_usable:
                if prompt.mode == "edit":
                    text_instruction = (
                        "Edit the attached image according to the instruction. "
                        "Preserve overall composition, subject identity, pose, camera angle, "
                        "product details and background layout unless explicitly asked to change. "
                        "Only modify what the instruction requests.\n\n"
                        f"Instruction: {safe_prompt}"
                    )
                else:
                    text_instruction = (
                        "Using the attached image as a style and composition reference, "
                        "generate a new beautiful photograph or illustration for a lifestyle post.\n\n"
                        f"Scene description: {safe_prompt}"
                    )
                if safe_negative:
                    text_instruction += f"\n\nPlease avoid: {safe_negative}"
                _prompt_sent = text_instruction
                user_msg_content: Any = [
                    {"type": "image_url", "image_url": {"url": ref_url_payload}},
                    {"type": "text", "text": text_instruction},
                ]
            else:
                user_msg_content = text_instruction

            extra_body: dict[str, Any] = {}
            if self._uses_default_openrouter_gateway():
                extra_body["provider"] = {"allow_fallbacks": True}
            if model_name in _OPENROUTER_NEEDS_MODALITIES:
                extra_body["modalities"] = ["image", "text"]

            raw_response = client.chat.completions.with_raw_response.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": user_msg_content},
                ],
                max_tokens=4096,
                **({"extra_body": extra_body} if extra_body else {}),
            )

            raw_json = json.loads(raw_response.text.strip())
            choices = raw_json.get("choices", [])
            if not choices:
                elapsed = int((time.perf_counter() - t0) * 1000)
                return ImageResult(slot_id=prompt.slot_id, status="failed",
                                   error=f"{self._image_gateway_label()} 返回空响应",
                                   elapsed_ms=elapsed, provider=self._image_gateway_provider())

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
                            logger.info(
                                "%s image (via images[]): slot=%s elapsed=%dms",
                                self._image_gateway_label(), prompt.slot_id, elapsed,
                            )
                            if on_progress:
                                on_progress(
                                    prompt.slot_id, "completed",
                                    {"image_url": serve_url, "provider": self._image_gateway_provider()},
                                )
                            _trace = dict(prompt_sent=_prompt_sent, ref_image_sent=ref_url_raw)
                            return ImageResult(slot_id=prompt.slot_id, status="completed",
                                               image_url=serve_url, elapsed_ms=elapsed,
                                               provider=self._image_gateway_provider(), **_trace)

            content = msg.get("content") or ""
            if content:
                image_path = self._extract_and_save_image(content, opportunity_id, prompt.slot_id)
                if image_path:
                    elapsed = int((time.perf_counter() - t0) * 1000)
                    serve_url = f"/generated-images/{opportunity_id}/{image_path.name}"
                    logger.info(
                        "%s image (via content): slot=%s elapsed=%dms",
                        self._image_gateway_label(), prompt.slot_id, elapsed,
                    )
                    if on_progress:
                        on_progress(
                            prompt.slot_id, "completed",
                            {"image_url": serve_url, "provider": self._image_gateway_provider()},
                        )
                    _trace = dict(prompt_sent=_prompt_sent, ref_image_sent=ref_url_raw)
                    return ImageResult(slot_id=prompt.slot_id, status="completed",
                                       image_url=serve_url, elapsed_ms=elapsed,
                                       provider=self._image_gateway_provider(), **_trace)

            image_path = self._extract_multipart_image(msg, opportunity_id, prompt.slot_id)
            if image_path:
                elapsed = int((time.perf_counter() - t0) * 1000)
                serve_url = f"/generated-images/{opportunity_id}/{image_path.name}"
                if on_progress:
                    on_progress(
                        prompt.slot_id, "completed",
                        {"image_url": serve_url, "provider": self._image_gateway_provider()},
                    )
                _trace = dict(prompt_sent=_prompt_sent, ref_image_sent=ref_url_raw)
                return ImageResult(slot_id=prompt.slot_id, status="completed",
                                   image_url=serve_url, elapsed_ms=elapsed,
                                   provider=self._image_gateway_provider(), **_trace)

            elapsed = int((time.perf_counter() - t0) * 1000)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error=f"{self._image_gateway_label()} 响应中未找到图片数据",
                               elapsed_ms=elapsed, provider=self._image_gateway_provider(),
                               prompt_sent=_prompt_sent, ref_image_sent=ref_url_raw)

        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("%s image gen error: %s", self._image_gateway_label(), exc, exc_info=True)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error=f"{self._image_gateway_label()}: {exc}",
                               elapsed_ms=elapsed, provider=self._image_gateway_provider(),
                               prompt_sent=locals().get("_prompt_sent", prompt.prompt),
                               ref_image_sent=locals().get("ref_url_raw", self._normalize_ref_image_url(prompt.ref_image_url)))

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

    def _resolve_dashscope_image_ref(self, ref_image_url: str) -> str:
        """把参考图 URL 规整成 DashScope MultiModalConversation 可消费的形式。

        - 公网 http(s) URL（非 localhost）→ 原样返回
        - `/generated-images/...` 本地 serve path → 解析成 `file://<abs>` 供 SDK 自动上传 OSS
        - 绝对文件系统路径 → 转 `file://<abs>`
        - 历史 `.../data/source_images/...` 绝对路径 → 先映射到当前仓库后再转 `file://`
        - 无法解析 → 返回 ""
        """
        if not ref_image_url:
            return ""
        is_public = ref_image_url.startswith("http") and not ref_image_url.startswith(("http://localhost", "http://127.0.0.1"))
        if is_public:
            return ref_image_url
        local_path = self._resolve_local_path(ref_image_url)
        if local_path:
            return f"file://{local_path.resolve()}"
        return ""

    def _extract_qwen_image_edit_url(self, rsp: Any) -> str:
        """从 MultiModalConversation 响应中取出生成的图片 URL。"""
        try:
            choices = getattr(rsp.output, "choices", None) or rsp.output.get("choices", [])
            if not choices:
                return ""
            first = choices[0]
            msg = getattr(first, "message", None) or first.get("message", {})
            content = getattr(msg, "content", None) or msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("image"):
                        return item["image"]
            elif isinstance(content, str):
                # 极少数模型返回纯文本形态
                import re
                m = re.search(r"https?://\S+\.(?:png|jpg|jpeg|webp)\S*", content)
                if m:
                    return m.group(0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("parse qwen-image-edit response failed: %s", exc)
        return ""

    def _generate_dashscope_image_edit(
        self,
        prompt: ImagePrompt,
        opportunity_id: str,
        image_ref: str,
        on_progress: Callable[[str, str, dict[str, Any]], None] | None,
        t0: float,
        trace: dict[str, Any],
    ) -> ImageResult:
        """走 MultiModalConversation + qwen-image-edit，支持本地 file:// 自动上传 OSS。"""
        from dashscope import MultiModalConversation

        instruction = prompt.prompt.strip()
        if prompt.mode == "edit":
            instruction = (
                "请在保持整体构图、主体位置、相机角度与产品细节不变的前提下，"
                f"按以下指令编辑图中内容：{instruction}"
            )
        if prompt.negative_prompt:
            instruction += f"\n避免：{prompt.negative_prompt.strip()}"

        messages = [{
            "role": "user",
            "content": [
                {"image": image_ref},
                {"text": instruction},
            ],
        }]
        try:
            rsp = MultiModalConversation.call(
                model=_DASHSCOPE_IMAGE_EDIT_MODEL,
                messages=messages,
                api_key=self._dashscope_key,
                result_format="message",
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("DashScope qwen-image-edit exception: %s", exc, exc_info=True)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error=f"qwen-image-edit: {exc}", elapsed_ms=elapsed,
                               provider="dashscope-qwen-image-edit", **trace)

        status_code = getattr(rsp, "status_code", 0)
        if status_code != 200:
            _code = getattr(rsp, "code", "") or ""
            _msg = getattr(rsp, "message", "") or ""
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("DashScope qwen-image-edit failed: slot=%s code=%s msg=%s",
                           prompt.slot_id, _code, _msg)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error=f"qwen-image-edit: {_code} {_msg}".strip(),
                               elapsed_ms=elapsed,
                               provider="dashscope-qwen-image-edit", **trace)

        remote_url = self._extract_qwen_image_edit_url(rsp)
        if not remote_url:
            elapsed = int((time.perf_counter() - t0) * 1000)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error="qwen-image-edit: 响应未找到图片 URL",
                               elapsed_ms=elapsed,
                               provider="dashscope-qwen-image-edit", **trace)

        local_path = self._save_from_url(remote_url, opportunity_id, prompt.slot_id)
        if not local_path:
            elapsed = int((time.perf_counter() - t0) * 1000)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error="qwen-image-edit: 下载输出图失败",
                               elapsed_ms=elapsed,
                               provider="dashscope-qwen-image-edit", **trace)
        elapsed = int((time.perf_counter() - t0) * 1000)
        serve_url = f"/generated-images/{opportunity_id}/{local_path.name}"
        logger.warning("DashScope qwen-image-edit OK: slot=%s elapsed=%dms", prompt.slot_id, elapsed)
        if on_progress:
            on_progress(prompt.slot_id, "completed", {"image_url": serve_url, "provider": "dashscope-qwen-image-edit"})
        return ImageResult(slot_id=prompt.slot_id, status="completed",
                           image_url=serve_url, elapsed_ms=elapsed,
                           provider="dashscope-qwen-image-edit", **trace)

    def _generate_dashscope(
        self,
        prompt: ImagePrompt,
        opportunity_id: str,
        on_progress: Callable[[str, str, dict[str, Any]], None] | None = None,
    ) -> ImageResult:
        from dashscope import ImageSynthesis

        normalized_ref = self._normalize_ref_image_url(prompt.ref_image_url)
        _ds_trace = dict(prompt_sent=prompt.prompt, ref_image_sent=normalized_ref)
        t0 = time.perf_counter()
        try:
            # 有参考图 → 走 qwen-image-edit（MultiModalConversation）：公网 URL 原样；本地路径 SDK 自动传 OSS。
            if normalized_ref:
                image_ref = self._resolve_dashscope_image_ref(normalized_ref)
                if image_ref:
                    edit_result = self._generate_dashscope_image_edit(
                        prompt, opportunity_id, image_ref, on_progress, t0, _ds_trace,
                    )
                    if edit_result.status == "completed":
                        return edit_result
                    logger.warning(
                        "DashScope ref-image branch failed for slot=%s: %s, downgrade to prompt_only",
                        prompt.slot_id, edit_result.error,
                    )
                else:
                    logger.warning(
                        "DashScope ref image unavailable for slot=%s: %s, downgrade to prompt_only",
                        prompt.slot_id, normalized_ref,
                    )

            # 纯文生图：主模型 → 失败再退兜底模型；两个模型的 size 约束不同，
            # 在调用前各自映射到匹配分辨率，避免 wan2.5 拒小尺寸 / wanx 拒大尺寸。
            # prompt.model 非空 → 用户在 onboarding 选了具体模型，作为 primary；否则用环境默认。
            primary_model = prompt.model or _DASHSCOPE_DEFAULT_MODEL
            primary_size = _size_for_dashscope_model(primary_model, prompt.size)
            rsp = ImageSynthesis.async_call(
                model=primary_model,
                prompt=prompt.prompt,
                negative_prompt=prompt.negative_prompt or None,
                n=1,
                size=primary_size,
                api_key=self._dashscope_key,
            )

            if rsp.status_code != 200:
                # fallback 模型：若用户指定了主模型且与环境默认相同，退到 FALLBACK；否则退到环境默认。
                fallback_model = _DASHSCOPE_FALLBACK_MODEL if primary_model != _DASHSCOPE_FALLBACK_MODEL else _DASHSCOPE_DEFAULT_MODEL
                if fallback_model == primary_model:
                    fallback_model = _DASHSCOPE_FALLBACK_MODEL
                fallback_size = _size_for_dashscope_model(fallback_model, prompt.size)
                logger.warning(
                    "DashScope primary %s failed (code=%s), fallback to %s with size=%s",
                    primary_model,
                    getattr(rsp, "code", ""),
                    fallback_model,
                    fallback_size,
                )
                rsp = ImageSynthesis.async_call(
                    model=fallback_model,
                    prompt=prompt.prompt,
                    negative_prompt=prompt.negative_prompt or None,
                    n=1,
                    size=fallback_size,
                    api_key=self._dashscope_key,
                )

            if rsp.status_code != 200:
                elapsed = int((time.perf_counter() - t0) * 1000)
                _code = getattr(rsp, 'code', '') or ''
                _msg = getattr(rsp, 'message', '') or ''
                err_msg = f"提交任务失败: {_code} {_msg}"
                logger.warning("DashScope all models failed: slot=%s code=%s msg=%s", prompt.slot_id, _code, _msg)
                return ImageResult(slot_id=prompt.slot_id, status="failed",
                                   error=err_msg, elapsed_ms=elapsed, provider="dashscope", **_ds_trace)

            task_id = rsp.output.get("task_id", "")
            logger.warning(
                "DashScope task submitted: slot=%s task_id=%s has_ref=%s",
                prompt.slot_id, task_id, bool(normalized_ref),
            )

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
                            logger.warning("DashScope image OK: slot=%s elapsed=%dms", prompt.slot_id, elapsed)
                            if on_progress:
                                on_progress(prompt.slot_id, "completed", {"image_url": serve_url, "provider": "dashscope"})
                            return ImageResult(slot_id=prompt.slot_id, status="completed",
                                               image_url=serve_url, elapsed_ms=elapsed, provider="dashscope", **_ds_trace)
                    break

                if task_status in ("FAILED", "UNKNOWN"):
                    err = status_rsp.output.get("message", "任务失败")
                    elapsed = int((time.perf_counter() - t0) * 1000)
                    logger.warning("DashScope task %s for slot=%s: %s", task_status, prompt.slot_id, err)
                    if on_progress:
                        on_progress(prompt.slot_id, "failed", {"error": err})
                    return ImageResult(slot_id=prompt.slot_id, status="failed",
                                       error=err, elapsed_ms=elapsed, provider="dashscope", **_ds_trace)

            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("DashScope polling timeout: slot=%s task_id=%s after %dms", prompt.slot_id, task_id, elapsed)
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error="DashScope 生成超时", elapsed_ms=elapsed, provider="dashscope", **_ds_trace)

        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("DashScope image gen error: %s", exc, exc_info=True)
            if on_progress:
                on_progress(prompt.slot_id, "failed", {"error": str(exc)})
            return ImageResult(slot_id=prompt.slot_id, status="failed",
                               error=str(exc), elapsed_ms=elapsed, provider="dashscope", **_ds_trace)

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
