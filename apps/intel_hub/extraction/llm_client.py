"""统一 LLM / VLM 客户端封装。

直接使用 DashScope SDK（项目已有依赖），不依赖 litellm。
当 DASHSCOPE_API_KEY 缺失或 SDK 未安装时静默降级，返回空结果。
设置 LOG_LEVEL=DEBUG 可查看完整 prompt / response。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import json
import logging
import os
import time
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


def _timeout_seconds(*, timeout_seconds: float | None = None, fast_mode: bool = False) -> float:
    if timeout_seconds is not None:
        return max(float(timeout_seconds), 0.01)
    env_name = "LLM_FAST_MODE_TIMEOUT_SECONDS" if fast_mode else "LLM_TIMEOUT_SECONDS"
    default = "2.0" if fast_mode else "8.0"
    try:
        return max(float(os.environ.get(env_name, default)), 0.01)
    except (TypeError, ValueError):
        return float(default)


def _run_with_timeout(fn: Any, *, timeout_seconds: float) -> Any:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


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
    timeout_seconds: float | None = None,
    fast_mode: bool = False,
) -> str:
    """调用文本 LLM，返回原始响应文本。失败时返回空字符串。"""
    if not is_llm_available():
        return ""
    used_model = model or _TEXT_MODEL
    t0 = time.perf_counter()
    try:
        import dashscope
        from dashscope import Generation

        dashscope.api_key = _DASHSCOPE_API_KEY
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        logger.debug(
            "[LLM-REQ] text model=%s\n--- SYSTEM ---\n%s\n--- USER ---\n%s",
            used_model,
            (system_prompt or "")[:500],
            user_prompt[:800],
        )

        timeout_value = _timeout_seconds(timeout_seconds=timeout_seconds, fast_mode=fast_mode)

        response = _run_with_timeout(
            lambda: Generation.call(
                model=used_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                result_format="message",
            ),
            timeout_seconds=timeout_value,
        )
        elapsed = time.perf_counter() - t0
        if response.status_code != 200:
            logger.warning(
                "[LLM-ERR] text model=%s status=%d elapsed=%.1fs msg=%s",
                used_model, response.status_code, elapsed, response.message,
            )
            return ""
        result = response.output.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        logger.debug(
            "[LLM-OK] text model=%s elapsed=%.1fs tokens=%s\n--- RESPONSE (first 500) ---\n%s",
            used_model, elapsed, usage, result[:500],
        )
        return result
    except FuturesTimeoutError:
        elapsed = time.perf_counter() - t0
        logger.warning("[LLM-TIMEOUT] text model=%s timeout=%.2fs elapsed=%.1fs", used_model, _timeout_seconds(timeout_seconds=timeout_seconds, fast_mode=fast_mode), elapsed)
        return ""
    except Exception:
        elapsed = time.perf_counter() - t0
        logger.warning("[LLM-EXC] text model=%s elapsed=%.1fs", used_model, elapsed, exc_info=True)
        return ""


def call_vlm(
    image_urls: list[str],
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    max_images: int = 3,
    timeout_seconds: float | None = None,
    fast_mode: bool = False,
) -> str:
    """调用视觉 LLM，返回原始响应文本。失败时返回空字符串。"""
    if not is_vlm_available():
        return ""
    if not image_urls:
        return ""
    used_model = model or _VLM_MODEL
    t0 = time.perf_counter()
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

        logger.debug(
            "[VLM-REQ] model=%s images=%d\n--- SYSTEM ---\n%s\n--- USER ---\n%s",
            used_model, len(image_urls[:max_images]),
            system_prompt[:500], user_prompt[:800],
        )

        timeout_value = _timeout_seconds(timeout_seconds=timeout_seconds, fast_mode=fast_mode)
        response = _run_with_timeout(
            lambda: MultiModalConversation.call(
                model=used_model,
                messages=messages,
            ),
            timeout_seconds=timeout_value,
        )
        elapsed = time.perf_counter() - t0
        if response.status_code != 200:
            logger.warning(
                "[VLM-ERR] model=%s status=%d elapsed=%.1fs msg=%s",
                used_model, response.status_code, elapsed, response.message,
            )
            return ""
        result = response.output.choices[0].message.content[0]["text"] or ""
        usage = getattr(response, "usage", None)
        logger.debug(
            "[VLM-OK] model=%s elapsed=%.1fs tokens=%s\n--- RESPONSE (first 500) ---\n%s",
            used_model, elapsed, usage, result[:500],
        )
        return result
    except FuturesTimeoutError:
        elapsed = time.perf_counter() - t0
        logger.warning("[VLM-TIMEOUT] model=%s timeout=%.2fs elapsed=%.1fs", used_model, _timeout_seconds(timeout_seconds=timeout_seconds, fast_mode=fast_mode), elapsed)
        return ""
    except Exception:
        elapsed = time.perf_counter() - t0
        logger.warning("[VLM-EXC] model=%s elapsed=%.1fs", used_model, elapsed, exc_info=True)
        return ""


def parse_json_response(raw_text: str) -> dict[str, Any]:
    """从 LLM 响应中解析 JSON，容忍 markdown 代码块包裹。"""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        text = "\n".join(lines[1:end])
    try:
        result = json.loads(text)
        logger.debug("[JSON-OK] parse_json_response: keys=%s", list(result.keys()) if isinstance(result, dict) else type(result).__name__)
        return result
    except json.JSONDecodeError:
        logger.debug("[JSON-ERR] parse_json_response: failed to parse: %s", text[:200])
        return {}
