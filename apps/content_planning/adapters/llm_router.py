"""Multi-LLM Router: unified interface for DashScope, OpenAI, Anthropic.

Default provider read from env LLM_PROVIDER (default: dashscope).
Each provider is optional -- import errors are caught and the provider is skipped.
"""
from __future__ import annotations

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


class LLMRouter:
    """Unified LLM call entry point supporting multiple providers."""

    def __init__(self, default_provider: str | None = None):
        self._default = default_provider or _DEFAULT_PROVIDER

    @property
    def available_providers(self) -> list[str]:
        return [name for name, p in _PROVIDERS.items() if p.is_available()]

    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             provider: str | None = None, temperature: float = 0.3,
             max_tokens: int = 2000) -> LLMResponse:
        prov_name = provider or self._default
        prov = _PROVIDERS.get(prov_name)
        if prov is None or not prov.is_available():
            for fallback_name in ("dashscope", "openai", "anthropic"):
                fb = _PROVIDERS.get(fallback_name)
                if fb and fb.is_available():
                    prov = fb
                    break
        if prov is None or not prov.is_available():
            logger.warning("No LLM provider available")
            return LLMResponse(content="", provider="none")
        return prov.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)

    def chat_json(self, messages: list[LLMMessage], **kwargs: Any) -> dict[str, Any]:
        prov_name = kwargs.pop("provider", None) or self._default
        prov = _PROVIDERS.get(prov_name)
        if prov is None or not prov.is_available():
            for fb_name in ("dashscope", "openai", "anthropic"):
                fb = _PROVIDERS.get(fb_name)
                if fb and fb.is_available():
                    prov = fb
                    break
        if prov is None or not prov.is_available():
            return {}
        return prov.chat_json(messages, **kwargs)

    def is_any_available(self) -> bool:
        return any(p.is_available() for p in _PROVIDERS.values())


llm_router = LLMRouter()
