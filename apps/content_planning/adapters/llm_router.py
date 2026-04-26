"""Multi-LLM Router v2: async + streaming + tool_calls + configurable fallback.

Inspired by Hermes Agent's unified internal message format (three api_modes converging
to one format) and DeerFlow's model factory pattern.

Backward compatible: sync `chat()` still works. New: `achat()`, `achat_stream()`,
`chat_with_tools()`, `achat_with_tools()`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Message & Response Models ──────────────────────────────────────

class LLMMessage(BaseModel):
    role: str = "user"
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""


class ToolCall(BaseModel):
    id: str = ""
    type: str = "function"
    function: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str = ""
    model: str = ""
    provider: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    elapsed_ms: int = 0
    degraded: bool = False
    degraded_reason: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str = ""


class ToolCallResult(BaseModel):
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    content: str = ""
    model: str = ""
    provider: str = ""


class StreamChunk(BaseModel):
    content: str = ""
    tool_calls_delta: list[dict[str, Any]] = Field(default_factory=list)
    finish_reason: str = ""
    done: bool = False


# ── Provider Base ──────────────────────────────────────────────────

class BaseLLMProvider(ABC):
    name: str

    @abstractmethod
    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             temperature: float = 0.3, max_tokens: int = 2000,
             tools: list[dict] | None = None) -> LLMResponse: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    async def achat(self, messages: list[LLMMessage], *, model: str | None = None,
                    temperature: float = 0.3, max_tokens: int = 2000,
                    tools: list[dict] | None = None) -> LLMResponse:
        """Default async impl delegates to sync in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.chat(messages, model=model, temperature=temperature,
                                    max_tokens=max_tokens, tools=tools))

    async def achat_stream(self, messages: list[LLMMessage], *, model: str | None = None,
                           temperature: float = 0.3, max_tokens: int = 2000,
                           tools: list[dict] | None = None) -> AsyncIterator[StreamChunk]:
        """Default streaming: single chunk from full response."""
        resp = await self.achat(messages, model=model, temperature=temperature,
                                max_tokens=max_tokens, tools=tools)
        yield StreamChunk(content=resp.content, done=True,
                          finish_reason=resp.finish_reason or "stop")

    def chat_json(self, messages: list[LLMMessage], **kwargs: Any) -> dict[str, Any]:
        resp = self.chat(messages, **kwargs)
        return _lenient_json_parse(resp.content)


# ── Concrete Providers ─────────────────────────────────────────────

class DashScopeProvider(BaseLLMProvider):
    name = "dashscope"

    def is_available(self) -> bool:
        try:
            from apps.intel_hub.extraction.llm_client import is_llm_available
            return is_llm_available()
        except Exception:
            return False

    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             temperature: float = 0.3, max_tokens: int = 2000,
             tools: list[dict] | None = None) -> LLMResponse:
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
             temperature: float = 0.3, max_tokens: int = 2000,
             tools: list[dict] | None = None) -> LLMResponse:
        import openai
        _oa_kwargs: dict[str, Any] = {}
        if os.environ.get("OPENAI_BASE_URL"):
            _oa_kwargs["base_url"] = os.environ["OPENAI_BASE_URL"]
        if os.environ.get("OPENAI_API_KEY"):
            _oa_kwargs["api_key"] = os.environ["OPENAI_API_KEY"]
        client = openai.OpenAI(**_oa_kwargs)
        t0 = time.perf_counter()
        used_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        try:
            kwargs: dict[str, Any] = dict(
                model=used_model,
                messages=self._format_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if tools:
                kwargs["tools"] = tools
            resp = client.chat.completions.create(**kwargs)
            elapsed = int((time.perf_counter() - t0) * 1000)
            content = resp.choices[0].message.content or ""
            tc = self._extract_tool_calls(resp.choices[0].message)
            usage = {}
            if resp.usage:
                usage = {"prompt_tokens": resp.usage.prompt_tokens,
                         "completion_tokens": resp.usage.completion_tokens}
            return LLMResponse(
                content=content, model=used_model, provider=self.name,
                usage=usage, elapsed_ms=elapsed, tool_calls=tc,
                finish_reason=resp.choices[0].finish_reason or "",
            )
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("[OpenAI-ERR] %s elapsed=%dms", exc, elapsed)
            return LLMResponse(content="", model=used_model, provider=self.name, elapsed_ms=elapsed)

    async def achat(self, messages: list[LLMMessage], *, model: str | None = None,
                    temperature: float = 0.3, max_tokens: int = 2000,
                    tools: list[dict] | None = None) -> LLMResponse:
        try:
            import openai
            _oa_kwargs: dict[str, Any] = {}
            if os.environ.get("OPENAI_BASE_URL"):
                _oa_kwargs["base_url"] = os.environ["OPENAI_BASE_URL"]
            if os.environ.get("OPENAI_API_KEY"):
                _oa_kwargs["api_key"] = os.environ["OPENAI_API_KEY"]
            client = openai.AsyncOpenAI(**_oa_kwargs)
            t0 = time.perf_counter()
            used_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
            kwargs: dict[str, Any] = dict(
                model=used_model,
                messages=self._format_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if tools:
                kwargs["tools"] = tools
            resp = await client.chat.completions.create(**kwargs)
            elapsed = int((time.perf_counter() - t0) * 1000)
            content = resp.choices[0].message.content or ""
            tc = self._extract_tool_calls(resp.choices[0].message)
            usage = {}
            if resp.usage:
                usage = {"prompt_tokens": resp.usage.prompt_tokens,
                         "completion_tokens": resp.usage.completion_tokens}
            return LLMResponse(
                content=content, model=used_model, provider=self.name,
                usage=usage, elapsed_ms=elapsed, tool_calls=tc,
                finish_reason=resp.choices[0].finish_reason or "",
            )
        except Exception:
            return await super().achat(messages, model=model, temperature=temperature,
                                       max_tokens=max_tokens, tools=tools)

    async def achat_stream(self, messages: list[LLMMessage], *, model: str | None = None,
                           temperature: float = 0.3, max_tokens: int = 2000,
                           tools: list[dict] | None = None) -> AsyncIterator[StreamChunk]:
        try:
            import openai
            _oa_kwargs: dict[str, Any] = {}
            if os.environ.get("OPENAI_BASE_URL"):
                _oa_kwargs["base_url"] = os.environ["OPENAI_BASE_URL"]
            if os.environ.get("OPENAI_API_KEY"):
                _oa_kwargs["api_key"] = os.environ["OPENAI_API_KEY"]
            client = openai.AsyncOpenAI(**_oa_kwargs)
            used_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
            kwargs: dict[str, Any] = dict(
                model=used_model,
                messages=self._format_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            if tools:
                kwargs["tools"] = tools
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue
                tc_delta = []
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_delta.append({"index": tc.index,
                                         "id": tc.id or "",
                                         "function": {"name": getattr(tc.function, "name", "") or "",
                                                      "arguments": getattr(tc.function, "arguments", "") or ""}})
                yield StreamChunk(
                    content=delta.content or "",
                    tool_calls_delta=tc_delta,
                    finish_reason=chunk.choices[0].finish_reason or "",
                    done=chunk.choices[0].finish_reason is not None,
                )
        except Exception:
            async for chunk in super().achat_stream(messages, model=model, temperature=temperature,
                                                     max_tokens=max_tokens, tools=tools):
                yield chunk

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict]:
        formatted = []
        for m in messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            formatted.append(msg)
        return formatted

    def _extract_tool_calls(self, message: Any) -> list[ToolCall]:
        if not hasattr(message, "tool_calls") or not message.tool_calls:
            return []
        result = []
        for tc in message.tool_calls:
            result.append(ToolCall(
                id=tc.id or "",
                type=tc.type or "function",
                function={"name": tc.function.name, "arguments": tc.function.arguments},
            ))
        return result


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
             temperature: float = 0.3, max_tokens: int = 2000,
             tools: list[dict] | None = None) -> LLMResponse:
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
            if tools:
                anthropic_tools = self._convert_tools_to_anthropic(tools)
                if anthropic_tools:
                    kwargs["tools"] = anthropic_tools
            resp = client.messages.create(**kwargs)
            elapsed = int((time.perf_counter() - t0) * 1000)
            content = ""
            tc = []
            for block in resp.content:
                if hasattr(block, "text"):
                    content += block.text
                elif hasattr(block, "type") and block.type == "tool_use":
                    tc.append(ToolCall(
                        id=block.id,
                        type="function",
                        function={"name": block.name, "arguments": json.dumps(block.input)},
                    ))
            usage = {}
            if resp.usage:
                usage = {"input_tokens": resp.usage.input_tokens,
                         "output_tokens": resp.usage.output_tokens}
            return LLMResponse(
                content=content, model=used_model, provider=self.name,
                usage=usage, elapsed_ms=elapsed, tool_calls=tc,
                finish_reason=resp.stop_reason or "",
            )
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("[Anthropic-ERR] %s elapsed=%dms", exc, elapsed)
            return LLMResponse(content="", model=used_model, provider=self.name, elapsed_ms=elapsed)

    async def achat(self, messages: list[LLMMessage], *, model: str | None = None,
                    temperature: float = 0.3, max_tokens: int = 2000,
                    tools: list[dict] | None = None) -> LLMResponse:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic()
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
            kwargs: dict[str, Any] = dict(model=used_model, messages=user_msgs,
                                           temperature=temperature, max_tokens=max_tokens)
            if system_text:
                kwargs["system"] = system_text
            if tools:
                anthropic_tools = self._convert_tools_to_anthropic(tools)
                if anthropic_tools:
                    kwargs["tools"] = anthropic_tools
            resp = await client.messages.create(**kwargs)
            elapsed = int((time.perf_counter() - t0) * 1000)
            content = ""
            tc = []
            for block in resp.content:
                if hasattr(block, "text"):
                    content += block.text
                elif hasattr(block, "type") and block.type == "tool_use":
                    tc.append(ToolCall(
                        id=block.id,
                        type="function",
                        function={"name": block.name, "arguments": json.dumps(block.input)},
                    ))
            usage = {}
            if resp.usage:
                usage = {"input_tokens": resp.usage.input_tokens,
                         "output_tokens": resp.usage.output_tokens}
            return LLMResponse(
                content=content, model=used_model, provider=self.name,
                usage=usage, elapsed_ms=elapsed, tool_calls=tc,
                finish_reason=resp.stop_reason or "",
            )
        except Exception:
            return await super().achat(messages, model=model, temperature=temperature,
                                       max_tokens=max_tokens, tools=tools)

    def _convert_tools_to_anthropic(self, openai_tools: list[dict]) -> list[dict]:
        """Convert OpenAI function-calling schema to Anthropic tool format."""
        result = []
        for tool in openai_tools:
            fn = tool.get("function", {})
            if not fn:
                continue
            result.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return result


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek provider via OpenAI-compatible API.

    Independent from OpenAIProvider so users can have both OpenAI and DeepSeek
    keys configured at the same time without env clashes.

    Env:
        DEEPSEEK_API_KEY    required
        DEEPSEEK_BASE_URL   default https://api.deepseek.com
        DEEPSEEK_MODEL      default deepseek-chat (use deepseek-reasoner or
                            user-specified latest id for reasoning model)
    """

    name = "deepseek"

    _DEFAULT_BASE_URL = "https://api.deepseek.com"
    _DEFAULT_MODEL = "deepseek-chat"

    def is_available(self) -> bool:
        if not os.environ.get("DEEPSEEK_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def _client_kwargs(self) -> dict[str, Any]:
        return {
            "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
            "base_url": os.environ.get("DEEPSEEK_BASE_URL", self._DEFAULT_BASE_URL),
        }

    def _resolve_model(self, model: str | None) -> str:
        return model or os.environ.get("DEEPSEEK_MODEL", self._DEFAULT_MODEL)

    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             temperature: float = 0.3, max_tokens: int = 2000,
             tools: list[dict] | None = None) -> LLMResponse:
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise RuntimeError("DEEPSEEK_API_KEY 未配置")
        import openai
        client = openai.OpenAI(**self._client_kwargs())
        used_model = self._resolve_model(model)
        t0 = time.perf_counter()
        try:
            kwargs: dict[str, Any] = dict(
                model=used_model,
                messages=self._format_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if tools:
                kwargs["tools"] = tools
            resp = client.chat.completions.create(**kwargs)
            elapsed = int((time.perf_counter() - t0) * 1000)
            content = resp.choices[0].message.content or ""
            tc = self._extract_tool_calls(resp.choices[0].message)
            usage = {}
            if resp.usage:
                usage = {"prompt_tokens": resp.usage.prompt_tokens,
                         "completion_tokens": resp.usage.completion_tokens}
            return LLMResponse(
                content=content, model=used_model, provider=self.name,
                usage=usage, elapsed_ms=elapsed, tool_calls=tc,
                finish_reason=resp.choices[0].finish_reason or "",
            )
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("[DeepSeek-ERR] %s elapsed=%dms", exc, elapsed)
            return LLMResponse(content="", model=used_model, provider=self.name, elapsed_ms=elapsed)

    async def achat(self, messages: list[LLMMessage], *, model: str | None = None,
                    temperature: float = 0.3, max_tokens: int = 2000,
                    tools: list[dict] | None = None) -> LLMResponse:
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise RuntimeError("DEEPSEEK_API_KEY 未配置")
        try:
            import openai
            client = openai.AsyncOpenAI(**self._client_kwargs())
            used_model = self._resolve_model(model)
            t0 = time.perf_counter()
            kwargs: dict[str, Any] = dict(
                model=used_model,
                messages=self._format_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if tools:
                kwargs["tools"] = tools
            resp = await client.chat.completions.create(**kwargs)
            elapsed = int((time.perf_counter() - t0) * 1000)
            content = resp.choices[0].message.content or ""
            tc = self._extract_tool_calls(resp.choices[0].message)
            usage = {}
            if resp.usage:
                usage = {"prompt_tokens": resp.usage.prompt_tokens,
                         "completion_tokens": resp.usage.completion_tokens}
            return LLMResponse(
                content=content, model=used_model, provider=self.name,
                usage=usage, elapsed_ms=elapsed, tool_calls=tc,
                finish_reason=resp.choices[0].finish_reason or "",
            )
        except Exception:
            return await super().achat(messages, model=model, temperature=temperature,
                                       max_tokens=max_tokens, tools=tools)

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict]:
        formatted = []
        for m in messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            formatted.append(msg)
        return formatted

    def _extract_tool_calls(self, message: Any) -> list[ToolCall]:
        if not hasattr(message, "tool_calls") or not message.tool_calls:
            return []
        result = []
        for tc in message.tool_calls:
            result.append(ToolCall(
                id=tc.id or "",
                type=tc.type or "function",
                function={"name": tc.function.name, "arguments": tc.function.arguments},
            ))
        return result


# ── Provider Registry ──────────────────────────────────────────────

_PROVIDERS: dict[str, BaseLLMProvider] = {}


def _init_providers() -> None:
    for cls in (DashScopeProvider, OpenAIProvider, AnthropicProvider, DeepSeekProvider):
        p = cls()
        _PROVIDERS[p.name] = p


_init_providers()

_DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
_DEFAULT_FALLBACK_CHAIN = os.environ.get(
    "LLM_FALLBACK_CHAIN", "openai,dashscope,anthropic,deepseek"
).split(",")


def _timeout_seconds(*, timeout_seconds: float | None = None, fast_mode: bool = False) -> float:
    if timeout_seconds is not None:
        return max(float(timeout_seconds), 0.01)
    env_name = "LLM_FAST_MODE_TIMEOUT_SECONDS" if fast_mode else "LLM_TIMEOUT_SECONDS"
    default = "2.0" if fast_mode else "90.0"
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


import re as _re

def _lenient_json_parse(text: str) -> dict[str, Any]:
    """Try hard to parse JSON from LLM output that may be malformed or truncated."""
    cleaned = _strip_code_fences(text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Some models wrap JSON in extra text; extract first { ... }
    m = _re.search(r"\{", cleaned)
    if m:
        candidate = cleaned[m.start():]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        # Truncated JSON: try closing open braces/brackets
        depth_brace = candidate.count("{") - candidate.count("}")
        depth_bracket = candidate.count("[") - candidate.count("]")
        patched = candidate.rstrip().rstrip(",")
        patched += "]" * max(depth_bracket, 0)
        patched += "}" * max(depth_brace, 0)
        try:
            return json.loads(patched)
        except json.JSONDecodeError:
            pass
    return {}


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


# ── LLM Router v2 ─────────────────────────────────────────────────

class LLMRouter:
    """Unified LLM call entry point with async, streaming, and tool_calls."""

    def __init__(
        self,
        default_provider: str | None = None,
        fallback_chain: list[str] | None = None,
    ) -> None:
        self._default = default_provider or _DEFAULT_PROVIDER
        self._fallback_chain = fallback_chain or _DEFAULT_FALLBACK_CHAIN

    @property
    def available_providers(self) -> list[str]:
        return [name for name, p in _PROVIDERS.items() if p.is_available()]

    def _resolve_provider(self, provider: str | None = None) -> tuple[str, BaseLLMProvider | None]:
        prov_name = provider or self._default
        prov = _PROVIDERS.get(prov_name)
        if prov is not None and prov.is_available():
            return prov_name, prov
        for fallback_name in self._fallback_chain:
            fb = _PROVIDERS.get(fallback_name)
            if fb and fb.is_available():
                return fallback_name, fb
        return prov_name, None

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
            return _degraded_response(provider=provider, model=model, reason="timeout", elapsed_ms=elapsed_ms)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.warning("LLM provider failed provider=%s: %s", provider, exc, exc_info=True)
            return _degraded_response(provider=provider, model=model, reason="provider_error", elapsed_ms=elapsed_ms)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    # ── Sync API (backward compatible) ──

    def chat(self, messages: list[LLMMessage], *, model: str | None = None,
             provider: str | None = None, temperature: float = 0.3,
             max_tokens: int = 2000, timeout_seconds: float | None = None,
             fast_mode: bool = False, tools: list[dict] | None = None) -> LLMResponse:
        prov_name, prov = self._resolve_provider(provider)
        if prov is None or not prov.is_available():
            return _degraded_response(provider="none", model=model, reason="no_provider", elapsed_ms=0)
        response = self._call_with_timeout(
            lambda: prov.chat(messages, model=model, temperature=temperature,
                              max_tokens=max_tokens, tools=tools),
            provider=prov_name, model=model,
            timeout_seconds=_timeout_seconds(timeout_seconds=timeout_seconds, fast_mode=fast_mode),
        )
        if not response.degraded and not response.content.strip() and not response.tool_calls:
            response.degraded = True
            response.degraded_reason = "empty_response"
        return response

    def chat_json(self, messages: list[LLMMessage], **kwargs: Any) -> dict[str, Any]:
        response = self.chat(messages, **kwargs)
        if response.degraded or not response.content.strip():
            return {}
        return _lenient_json_parse(response.content)

    def chat_with_tools(
        self,
        messages: list[LLMMessage],
        tools_schema: list[dict],
        *,
        model: str | None = None,
        provider: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        max_rounds: int = 5,
        tool_handler: Any | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        """Hermes-style tool-calling loop: model -> tool_calls -> execute -> model."""
        current_messages = list(messages)
        for _ in range(max_rounds):
            resp = self.chat(
                current_messages, model=model, provider=provider,
                temperature=temperature, max_tokens=max_tokens,
                tools=tools_schema, timeout_seconds=timeout_seconds,
            )
            if resp.degraded or not resp.tool_calls:
                return resp
            if tool_handler is None:
                return resp

            assistant_msg = LLMMessage(
                role="assistant", content=resp.content,
                tool_calls=[tc.model_dump(mode="json") for tc in resp.tool_calls],
            )
            current_messages.append(assistant_msg)

            for tc in resp.tool_calls:
                fn_name = tc.function.get("name", "")
                fn_args_str = tc.function.get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                except json.JSONDecodeError:
                    fn_args = {}
                try:
                    result = tool_handler(fn_name, fn_args)
                    result_str = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
                except Exception as exc:
                    result_str = json.dumps({"error": str(exc)})
                current_messages.append(LLMMessage(
                    role="tool", content=result_str,
                    tool_call_id=tc.id, name=fn_name,
                ))
        return resp

    # ── Async API ──

    async def achat(self, messages: list[LLMMessage], *, model: str | None = None,
                    provider: str | None = None, temperature: float = 0.3,
                    max_tokens: int = 2000, tools: list[dict] | None = None) -> LLMResponse:
        prov_name, prov = self._resolve_provider(provider)
        if prov is None or not prov.is_available():
            return _degraded_response(provider="none", model=model, reason="no_provider", elapsed_ms=0)
        try:
            response = await asyncio.wait_for(
                prov.achat(messages, model=model, temperature=temperature,
                           max_tokens=max_tokens, tools=tools),
                timeout=_timeout_seconds(fast_mode=False),
            )
            if not response.degraded and not response.content.strip() and not response.tool_calls:
                response.degraded = True
                response.degraded_reason = "empty_response"
            return response
        except asyncio.TimeoutError:
            return _degraded_response(provider=prov_name, model=model, reason="timeout", elapsed_ms=0)
        except Exception as exc:
            logger.warning("achat failed: %s", exc, exc_info=True)
            return _degraded_response(provider=prov_name, model=model, reason="provider_error", elapsed_ms=0)

    async def achat_stream(self, messages: list[LLMMessage], *, model: str | None = None,
                           provider: str | None = None, temperature: float = 0.3,
                           max_tokens: int = 2000,
                           tools: list[dict] | None = None) -> AsyncIterator[StreamChunk]:
        prov_name, prov = self._resolve_provider(provider)
        if prov is None or not prov.is_available():
            yield StreamChunk(content="", done=True, finish_reason="no_provider")
            return
        async for chunk in prov.achat_stream(messages, model=model, temperature=temperature,
                                              max_tokens=max_tokens, tools=tools):
            yield chunk

    async def achat_with_tools(
        self,
        messages: list[LLMMessage],
        tools_schema: list[dict],
        *,
        model: str | None = None,
        provider: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        max_rounds: int = 5,
        tool_handler: Any | None = None,
    ) -> LLMResponse:
        """Async version of the tool-calling loop."""
        current_messages = list(messages)
        resp = _degraded_response(provider="none", model=model, reason="no_rounds", elapsed_ms=0)
        for _ in range(max_rounds):
            resp = await self.achat(
                current_messages, model=model, provider=provider,
                temperature=temperature, max_tokens=max_tokens, tools=tools_schema,
            )
            if resp.degraded or not resp.tool_calls:
                return resp
            if tool_handler is None:
                return resp

            assistant_msg = LLMMessage(
                role="assistant", content=resp.content,
                tool_calls=[tc.model_dump(mode="json") for tc in resp.tool_calls],
            )
            current_messages.append(assistant_msg)

            for tc in resp.tool_calls:
                fn_name = tc.function.get("name", "")
                fn_args_str = tc.function.get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                except json.JSONDecodeError:
                    fn_args = {}
                try:
                    result_raw = tool_handler(fn_name, fn_args)
                    if asyncio.iscoroutine(result_raw):
                        result_raw = await result_raw
                    result_str = json.dumps(result_raw, ensure_ascii=False) if not isinstance(result_raw, str) else result_raw
                except Exception as exc:
                    result_str = json.dumps({"error": str(exc)})
                current_messages.append(LLMMessage(
                    role="tool", content=result_str,
                    tool_call_id=tc.id, name=fn_name,
                ))
        return resp

    def is_any_available(self) -> bool:
        return any(p.is_available() for p in _PROVIDERS.values())


# ── Singleton ──────────────────────────────────────────────────────

llm_router = LLMRouter()
