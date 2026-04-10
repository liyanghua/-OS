"""Multi-LLM Router: unified interface for DashScope, OpenAI, Anthropic.

Default provider read from env LLM_PROVIDER (default: dashscope).
Each provider is optional -- import errors are caught and the provider is skipped.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LLMMessage(BaseModel):
    role: str = "user"
    content: str = ""


class LLMResponse(BaseModel):
    content: str = ""
    model: str = ""
    provider: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    elapsed_ms: int = 0
    degraded: bool = False
    degraded_reason: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    content: str = ""
    model: str = ""
    provider: str = ""


class BaseLLMProvider(ABC):
    name: str

    @abstractmethod
    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             temperature: float = 0.3, max_tokens: int = 2000) -> LLMResponse: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    def chat_json(self, messages: list[LLMMessage], **kwargs: Any) -> dict[str, Any]:
        resp = self.chat(messages, **kwargs)
        text = resp.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            end_idx = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
            text = "\n".join(lines[1:end_idx])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}


class DashScopeProvider(BaseLLMProvider):
    name = "dashscope"

    def is_available(self) -> bool:
        from apps.intel_hub.extraction.llm_client import is_llm_available
        return is_llm_available()

    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             temperature: float = 0.3, max_tokens: int = 2000) -> LLMResponse:
        from apps.intel_hub.extraction.llm_client import call_text_llm
        system = ""
        user = ""
        for m in messages:
            if m.role == "system":
                system = m.content
            elif m.role == "user":
                user = m.content
        t0 = time.perf_counter()
        result = call_text_llm(system, user, model=model, temperature=temperature, max_tokens=max_tokens)
        elapsed = int((time.perf_counter() - t0) * 1000)
        return LLMResponse(content=result, model=model or "qwen-max",
                           provider=self.name, elapsed_ms=elapsed)


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def is_available(self) -> bool:
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             temperature: float = 0.3, max_tokens: int = 2000) -> LLMResponse:
        import openai
        client = openai.OpenAI()
        t0 = time.perf_counter()
        used_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        try:
            resp = client.chat.completions.create(
                model=used_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed = int((time.perf_counter() - t0) * 1000)
            content = resp.choices[0].message.content or ""
            usage = {}
            if resp.usage:
                usage = {"prompt_tokens": resp.usage.prompt_tokens,
                         "completion_tokens": resp.usage.completion_tokens}
            return LLMResponse(content=content, model=used_model, provider=self.name,
                               usage=usage, elapsed_ms=elapsed)
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("[OpenAI-ERR] %s elapsed=%dms", exc, elapsed)
            return LLMResponse(content="", model=used_model, provider=self.name, elapsed_ms=elapsed)


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def is_available(self) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             temperature: float = 0.3, max_tokens: int = 2000) -> LLMResponse:
        import anthropic
        client = anthropic.Anthropic()
        t0 = time.perf_counter()
        used_model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        system_text = ""
        user_msgs = []
        for m in messages:
            if m.role == "system":
                system_text = m.content
            else:
                user_msgs.append({"role": m.role, "content": m.content})
        if not user_msgs:
            user_msgs = [{"role": "user", "content": ""}]
        try:
            kwargs: dict[str, Any] = dict(model=used_model, messages=user_msgs,
                                           temperature=temperature, max_tokens=max_tokens)
            if system_text:
                kwargs["system"] = system_text
            resp = client.messages.create(**kwargs)
            elapsed = int((time.perf_counter() - t0) * 1000)
            content = resp.content[0].text if resp.content else ""
            usage = {}
            if resp.usage:
                usage = {"input_tokens": resp.usage.input_tokens,
                         "output_tokens": resp.usage.output_tokens}
            return LLMResponse(content=content, model=used_model, provider=self.name,
                               usage=usage, elapsed_ms=elapsed)
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("[Anthropic-ERR] %s elapsed=%dms", exc, elapsed)
            return LLMResponse(content="", model=used_model, provider=self.name, elapsed_ms=elapsed)


_PROVIDERS: dict[str, BaseLLMProvider] = {}

def _init_providers() -> None:
    for cls in (DashScopeProvider, OpenAIProvider, AnthropicProvider):
        p = cls()
        _PROVIDERS[p.name] = p

_init_providers()

_DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "dashscope")


def _timeout_seconds(*, timeout_seconds: float | None = None, fast_mode: bool = False) -> float:
    if timeout_seconds is not None:
        return max(float(timeout_seconds), 0.01)
    env_name = "LLM_FAST_MODE_TIMEOUT_SECONDS" if fast_mode else "LLM_TIMEOUT_SECONDS"
    default = "2.0" if fast_mode else "8.0"
    try:
        return max(float(os.environ.get(env_name, default)), 0.01)
    except (TypeError, ValueError):
        return float(default)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        end_idx = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        stripped = "\n".join(lines[1:end_idx])
    return stripped


def _degraded_response(
    *,
    provider: str,
    model: str | None,
    reason: str,
    elapsed_ms: int,
) -> LLMResponse:
    return LLMResponse(
        content="",
        model=model or "",
        provider=provider,
        elapsed_ms=elapsed_ms,
        degraded=True,
        degraded_reason=reason,
        raw={"degraded": True, "reason": reason},
    )


class LLMRouter:
    """Unified LLM call entry point supporting multiple providers."""

    def __init__(self, default_provider: str | None = None):
        self._default = default_provider or _DEFAULT_PROVIDER

    @property
    def available_providers(self) -> list[str]:
        return [name for name, p in _PROVIDERS.items() if p.is_available()]

    def _resolve_provider(self, provider: str | None = None) -> tuple[str, BaseLLMProvider | None]:
        prov_name = provider or self._default
        prov = _PROVIDERS.get(prov_name)
        if prov is None or not prov.is_available():
            for fallback_name in ("dashscope", "openai", "anthropic"):
                fb = _PROVIDERS.get(fallback_name)
                if fb and fb.is_available():
                    return fallback_name, fb
            return prov_name, None
        return prov_name, prov

    def _call_with_timeout(
        self,
        fn: Any,
        *,
        provider: str,
        model: str | None,
        timeout_seconds: float,
    ) -> LLMResponse:
        started = time.perf_counter()
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.warning("LLM provider timed out provider=%s timeout=%.2fs", provider, timeout_seconds)
            return _degraded_response(
                provider=provider,
                model=model,
                reason="timeout",
                elapsed_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.warning("LLM provider failed provider=%s: %s", provider, exc, exc_info=True)
            return _degraded_response(
                provider=provider,
                model=model,
                reason="provider_error",
                elapsed_ms=elapsed_ms,
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             provider: str | None = None, temperature: float = 0.3,
             max_tokens: int = 2000, timeout_seconds: float | None = None,
             fast_mode: bool = False) -> LLMResponse:
        prov_name, prov = self._resolve_provider(provider)
        if prov is None or not prov.is_available():
            logger.warning("No LLM provider available")
            return _degraded_response(
                provider="none",
                model=model,
                reason="no_provider",
                elapsed_ms=0,
            )
        response = self._call_with_timeout(
            lambda: prov.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens),
            provider=prov_name,
            model=model,
            timeout_seconds=_timeout_seconds(timeout_seconds=timeout_seconds, fast_mode=fast_mode),
        )
        if not response.degraded and not response.content.strip():
            response.degraded = True
            response.degraded_reason = "empty_response"
            response.raw.setdefault("degraded", True)
            response.raw.setdefault("reason", "empty_response")
        return response

    def chat_json(self, messages: list[LLMMessage], **kwargs: Any) -> dict[str, Any]:
        response = self.chat(messages, **kwargs)
        if response.degraded or not response.content.strip():
            return {}
        try:
            return json.loads(_strip_code_fences(response.content))
        except json.JSONDecodeError:
            return {}

    def is_any_available(self) -> bool:
        return any(p.is_available() for p in _PROVIDERS.values())


llm_router = LLMRouter()
