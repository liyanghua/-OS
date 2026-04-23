"""VLMClient — 视觉工作台共享的多模态调用客户端。

封装 OpenAI 兼容的多模态 chat.completions 调用，支持：
- DashScope Qwen-VL（国内直连）
- 用户自建 OPENAI_BASE_URL 代理
- OpenRouter Gemini

统一本地路径 → data URI 转换、直连 httpx 客户端（避开 macOS 代理残留），
并按回退链依次尝试，任一 provider 成功就返回。

由 competitor_deconstructor、workspace_copilot 的 analyze-edit 等共用，
避免多份 VLM 调用代码各自演化。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_VLM_MODEL = "google/gemini-2.5-flash"
_DEFAULT_QWEN_VL_MODEL = "qwen-vl-max-latest"


@dataclass
class VLMResponse:
    content: str
    provider: str = ""
    model: str = ""
    raw_reason: str = ""


def resolve_image_ref(image_url: str) -> str:
    """本地服务路径（/source-images/, /generated-images/, 裸路径）→ data URI；http(s)/data 原样返回。

    失败返回空串，调用方自行决定是否跳过这张图。
    """
    if not image_url:
        return ""
    if image_url.startswith(("http://", "https://", "data:")):
        return image_url
    try:
        from apps.content_planning.services.image_generator import ImageGeneratorService
    except Exception as exc:  # pragma: no cover
        logger.warning("[VLMClient] 无法导入 ImageGeneratorService: %s", exc)
        return ""
    data_uri = ImageGeneratorService._local_path_to_data_uri(image_url)
    return data_uri or ""


def candidate_providers() -> list[tuple[str, str, str, str]]:
    """按优先级返回候选 VLM 提供方列表 [(provider, model, api_key, base_url), ...]。"""
    candidates: list[tuple[str, str, str, str]] = []
    default_vlm = os.environ.get("COMPETITOR_VLM_MODEL", "").strip() or _DEFAULT_VLM_MODEL

    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if dashscope_key:
        qwen_model = (
            os.environ.get("COMPETITOR_VLM_MODEL_QWEN", "").strip()
            or _DEFAULT_QWEN_VL_MODEL
        )
        qwen_base = (
            os.environ.get("DASHSCOPE_BASE_URL", "").strip()
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        candidates.append(("dashscope_qwen_vl", qwen_model, dashscope_key, qwen_base))

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    openai_base = os.environ.get("OPENAI_BASE_URL", "").strip()
    if openai_key and openai_base:
        openai_model = os.environ.get("OPENAI_MODEL", "").strip() or default_vlm
        candidates.append(("openai_proxy", openai_model, openai_key, openai_base))

    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        candidates.append(("openrouter", default_vlm, openrouter_key, "https://openrouter.ai/api/v1"))

    return candidates


def _call_openai_multimodal_sync(
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.3,
    max_tokens: int = 2048,
    force_json: bool = True,
) -> str:
    """同步调用 OpenAI 兼容的 chat.completions（多模态 messages），返回 message.content 字符串。

    用显式直连的 httpx.Client（trust_env=False），避免进程误继承系统代理。
    """
    import httpx
    from openai import OpenAI

    proxy_env = {
        k: os.environ.get(k, "")
        for k in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy",
            "NO_PROXY", "no_proxy",
        )
        if os.environ.get(k)
    }
    if proxy_env:
        logger.info(
            "[VLMClient] detected proxy env in process: %s — 将以直连覆盖",
            proxy_env,
        )

    http_client = httpx.Client(
        trust_env=False,
        timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0),
    )
    client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if force_json:
        kwargs["response_format"] = {"type": "json_object"}
    if provider == "openrouter":
        kwargs["extra_body"] = {"provider": {"allow_fallbacks": True}}

    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:
        msg = str(exc)
        if force_json and ("response_format" in msg or "json_object" in msg):
            kwargs.pop("response_format", None)
            resp = client.chat.completions.create(**kwargs)
        else:
            raise

    choices = getattr(resp, "choices", []) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", "") if message is not None else ""
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts).strip()
    return (content or "").strip()


def build_multimodal_messages(
    *,
    system_prompt: str,
    user_text: str,
    image_urls: list[str],
) -> list[dict[str, Any]]:
    """组装标准的多模态 messages（OpenAI image_url 内容块格式）。

    传入的 image_urls 若是本地路径会自动转 data URI；为空/无法解析的会被跳过。
    """
    user_content: list[dict[str, Any]] = []
    for url in image_urls or []:
        ref = resolve_image_ref(url)
        if ref:
            user_content.append({"type": "image_url", "image_url": {"url": ref}})
    if user_text:
        user_content.append({"type": "text", "text": user_text})
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content or [{"type": "text", "text": user_text or ""}]},
    ]


async def call_vlm_multimodal(
    *,
    system_prompt: str,
    user_text: str,
    image_urls: list[str] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    force_json: bool = True,
    provider_override: list[tuple[str, str, str, str]] | None = None,
) -> VLMResponse:
    """调用多模态 VLM，按候选 provider 链回退。

    返回 VLMResponse；若全链失败，content 为空、raw_reason 含最后一次错误类型。
    """
    providers = provider_override or candidate_providers()
    if not providers:
        logger.warning("[VLMClient] 未配置任何 VLM 提供方 (DashScope / OpenAI 代理 / OpenRouter)")
        return VLMResponse(content="", raw_reason="no_vision_provider")

    messages = build_multimodal_messages(
        system_prompt=system_prompt,
        user_text=user_text,
        image_urls=list(image_urls or []),
    )

    last_reason = "vlm_error"
    for provider, model, api_key, base_url in providers:
        try:
            content = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda p=provider, m=model, k=api_key, b=base_url: _call_openai_multimodal_sync(
                    provider=p, model=m, api_key=k, base_url=b,
                    messages=messages,
                    temperature=temperature, max_tokens=max_tokens,
                    force_json=force_json,
                ),
            )
        except Exception as exc:
            last_reason = f"vlm_error:{type(exc).__name__}:{exc}"
            logger.warning(
                "[VLMClient] VLM 调用失败 provider=%s model=%s base=%s err=%s(%s); 尝试下一个",
                provider, model, base_url, type(exc).__name__, exc,
            )
            continue
        if not content:
            last_reason = "empty_content"
            continue
        return VLMResponse(content=content, provider=provider, model=model)

    return VLMResponse(content="", raw_reason=last_reason)


def safe_json_obj(text: str) -> dict:
    """尽力从 text 里解析 JSON 对象；失败返回空 dict。"""
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}
