"""Tests for the DeepSeek provider integration in ``llm_router``.

Network is mocked at the ``openai.OpenAI`` boundary so tests are offline.
"""
from __future__ import annotations

import importlib
import os
import unittest
from types import SimpleNamespace
from unittest import mock

router_mod = importlib.import_module("apps.content_planning.adapters.llm_router")
from apps.content_planning.adapters.llm_router import (
    DeepSeekProvider,
    LLMMessage,
    _PROVIDERS,
)


class DeepSeekProviderRegistrationTests(unittest.TestCase):
    def test_provider_registered_in_global_dict(self) -> None:
        self.assertIn("deepseek", _PROVIDERS)
        self.assertIsInstance(_PROVIDERS["deepseek"], DeepSeekProvider)

    def test_is_available_requires_api_key(self) -> None:
        provider = DeepSeekProvider()
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
            os.environ.pop("DEEPSEEK_API_KEY", None)
            self.assertFalse(provider.is_available())
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=False):
            self.assertTrue(provider.is_available())


class _FakeOpenAIClient:
    """Captures kwargs and returns a deterministic fake completion."""

    def __init__(self, captured: dict, *, content: str = '{"ok": true}',
                 model_returned: str = "deepseek-chat") -> None:
        self._captured = captured
        self._content = content
        self._model = model_returned

        class _Completions:
            def __init__(self_inner) -> None:
                self_inner._captured = captured
                self_inner._content = content
                self_inner._model = model_returned

            def create(self_inner, **kwargs):
                self_inner._captured["create_kwargs"] = kwargs
                message = SimpleNamespace(content=self_inner._content, tool_calls=None)
                choice = SimpleNamespace(message=message, finish_reason="stop")
                usage = SimpleNamespace(prompt_tokens=10, completion_tokens=20)
                return SimpleNamespace(
                    choices=[choice],
                    usage=usage,
                    model=self_inner._model,
                    model_dump=lambda: {"model": self_inner._model},
                )

        class _Chat:
            def __init__(self_inner) -> None:
                self_inner.completions = _Completions()

        self.chat = _Chat()


class DeepSeekProviderChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self._captured: dict = {}

    def _patched_openai(self):
        captured = self._captured

        def fake_openai(**kwargs):
            captured["client_kwargs"] = kwargs
            return _FakeOpenAIClient(captured)

        return fake_openai

    def test_chat_uses_env_base_url_and_model(self) -> None:
        provider = DeepSeekProvider()
        env = {
            "DEEPSEEK_API_KEY": "sk-test",
            "DEEPSEEK_BASE_URL": "https://example.deepseek/v1",
            "DEEPSEEK_MODEL": "deepseek-reasoner",
        }
        fake_openai_module = SimpleNamespace(OpenAI=self._patched_openai())
        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch.dict("sys.modules", {"openai": fake_openai_module}):
            response = provider.chat([LLMMessage(role="user", content="hi")])

        self.assertEqual(self._captured["client_kwargs"]["api_key"], "sk-test")
        self.assertEqual(self._captured["client_kwargs"]["base_url"],
                         "https://example.deepseek/v1")
        self.assertEqual(self._captured["create_kwargs"]["model"], "deepseek-reasoner")
        self.assertEqual(response.provider, "deepseek")
        self.assertEqual(response.model, "deepseek-reasoner")
        self.assertIn("ok", response.content)

    def test_chat_falls_back_to_default_model_when_env_unset(self) -> None:
        provider = DeepSeekProvider()
        env = {"DEEPSEEK_API_KEY": "sk-test"}
        fake_openai_module = SimpleNamespace(OpenAI=self._patched_openai())
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("DEEPSEEK_BASE_URL", None)
            os.environ.pop("DEEPSEEK_MODEL", None)
            with mock.patch.dict("sys.modules", {"openai": fake_openai_module}):
                provider.chat([LLMMessage(role="user", content="hi")])

        self.assertEqual(self._captured["client_kwargs"]["base_url"],
                         "https://api.deepseek.com")
        self.assertEqual(self._captured["create_kwargs"]["model"], "deepseek-chat")

    def test_chat_raises_without_api_key(self) -> None:
        provider = DeepSeekProvider()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEEPSEEK_API_KEY", None)
            with self.assertRaises(RuntimeError):
                provider.chat([LLMMessage(role="user", content="hi")])

    def test_explicit_model_arg_overrides_env(self) -> None:
        provider = DeepSeekProvider()
        env = {
            "DEEPSEEK_API_KEY": "sk-test",
            "DEEPSEEK_MODEL": "deepseek-reasoner",
        }
        fake_openai_module = SimpleNamespace(OpenAI=self._patched_openai())
        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch.dict("sys.modules", {"openai": fake_openai_module}):
            provider.chat(
                [LLMMessage(role="user", content="hi")],
                model="deepseek-v4-pro",
            )
        self.assertEqual(self._captured["create_kwargs"]["model"], "deepseek-v4-pro")


class DeepSeekFallbackChainTests(unittest.TestCase):
    def test_default_fallback_chain_includes_deepseek(self) -> None:
        # Default chain when LLM_FALLBACK_CHAIN unset is "openai,dashscope,anthropic,deepseek".
        # We just assert deepseek is reachable from chain at module load time.
        self.assertIn("deepseek", _PROVIDERS)
        # Module-level constant should mention deepseek by default name.
        # We don't compare full chain to allow user env overrides; instead check the
        # raw default literal in source-of-truth form via current chain content.
        chain_str = ",".join(router_mod._DEFAULT_FALLBACK_CHAIN)
        self.assertIn("deepseek", chain_str)


if __name__ == "__main__":
    unittest.main()
