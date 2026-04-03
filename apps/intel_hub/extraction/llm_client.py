"""统一 LLM / VLM 客户端封装。

直接使用 DashScope SDK（项目已有依赖），不依赖 litellm。
当 DASHSCOPE_API_KEY 缺失或 SDK 未安装时静默降级，返回空结果。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """从项目根 .env 文件加载环境变量（不覆盖已有值）。"""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

_DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
_TEXT_MODEL = os.environ.get("DASHSCOPE_TEXT_MODEL", "qwen-max")
_VLM_MODEL = os.environ.get("DASHSCOPE_VLM_MODEL", "qwen-vl-max")


def is_llm_available() -> bool:
    if not _DASHSCOPE_API_KEY:
        return False
    try:
        import dashscope  # noqa: F401
        return True
    except ImportError:
        return False


def is_vlm_available() -> bool:
    return is_llm_available()


def call_text_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """调用文本 LLM，返回原始响应文本。失败时返回空字符串。"""
    if not is_llm_available():
        return ""
    try:
        import dashscope
        from dashscope import Generation

        dashscope.api_key = _DASHSCOPE_API_KEY
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        response = Generation.call(
            model=model or _TEXT_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format="message",
        )
        if response.status_code != 200:
            logger.warning("llm_client text: status %d: %s", response.status_code, response.message)
            return ""
        return response.output.choices[0].message.content or ""
    except Exception:
        logger.warning("llm_client text: call failed", exc_info=True)
        return ""


def call_vlm(
    image_urls: list[str],
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    max_images: int = 3,
) -> str:
    """调用视觉 LLM，返回原始响应文本。失败时返回空字符串。"""
    if not is_vlm_available():
        return ""
    if not image_urls:
        return ""
    try:
        import dashscope
        from dashscope import MultiModalConversation

        dashscope.api_key = _DASHSCOPE_API_KEY

        content: list[dict[str, Any]] = []
        for url in image_urls[:max_images]:
            content.append({"image": url})
        content.append({"text": user_prompt})

        messages = [
            {"role": "system", "content": [{"text": system_prompt}]},
            {"role": "user", "content": content},
        ]

        response = MultiModalConversation.call(
            model=model or _VLM_MODEL,
            messages=messages,
        )
        if response.status_code != 200:
            logger.warning("llm_client vlm: status %d: %s", response.status_code, response.message)
            return ""
        return response.output.choices[0].message.content[0]["text"] or ""
    except Exception:
        logger.warning("llm_client vlm: call failed", exc_info=True)
        return ""


def parse_json_response(raw_text: str) -> dict[str, Any]:
    """从 LLM 响应中解析 JSON，容忍 markdown 代码块包裹。"""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        text = "\n".join(lines[1:end])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.debug("parse_json_response: failed to parse: %s", text[:200])
        return {}
