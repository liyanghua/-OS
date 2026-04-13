"""ImageGeneratorService 测试套件。

第一层: Mock 单元测试 (无需 API key，本地秒级运行)
第二层: 真实 API 集成测试 (需 .env 中的 key，标记 @pytest.mark.integration)

运行方式:
    # mock 测试
    pytest apps/content_planning/tests/test_image_generator.py -v -k "not integration"

    # 集成测试 (需要 .env key + 网络)
    pytest apps/content_planning/tests/test_image_generator.py -m integration -v
"""

from __future__ import annotations

import base64
import os
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.content_planning.services.image_generator import (
    ImageGeneratorService,
    ImagePrompt,
    ImageResult,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_REF_IMAGE = _REPO_ROOT / "data" / "source_images" / "9f82cee1a56742a0" / "cover_605bf9f00000.jpg"
_TEST_OPP_ID = "test_opp_unit"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prompt(
    slot_id: str = "cover",
    prompt: str = "北欧风格餐桌布置，柔和自然光",
    ref_image_url: str = "",
) -> ImagePrompt:
    return ImagePrompt(slot_id=slot_id, prompt=prompt, ref_image_url=ref_image_url)


def _make_dashscope_rsp(status_code: int = 200, task_id: str = "t-abc123", **overrides: Any) -> MagicMock:
    """Simulate a DashScope GenerationResponse object."""
    rsp = MagicMock()
    rsp.status_code = status_code
    rsp.output = {"task_id": task_id}
    rsp.code = overrides.get("code", "")
    rsp.message = overrides.get("message", "")
    return rsp


def _make_dashscope_fetch_rsp(task_status: str = "SUCCEEDED", url: str = "https://oss.example.com/img.png") -> MagicMock:
    rsp = MagicMock()
    rsp.output = {
        "task_status": task_status,
        "results": [{"url": url}] if task_status == "SUCCEEDED" else [],
        "message": "task failed" if task_status == "FAILED" else "",
    }
    return rsp


def _make_openrouter_raw_response(b64_img: str | None = None) -> MagicMock:
    """Simulate the OpenRouter raw_response from client.chat.completions.with_raw_response.create."""
    import json
    if b64_img is None:
        pixel = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
        b64_img = f"data:image/png;base64,{pixel}"
    body = {
        "choices": [{
            "message": {
                "content": [
                    {"type": "text", "text": "Here is the image."},
                    {"type": "image_url", "image_url": {"url": b64_img}},
                ],
            }
        }]
    }
    raw_rsp = MagicMock()
    raw_rsp.text = json.dumps(body)
    return raw_rsp


def _service_with_keys(**env: str) -> ImageGeneratorService:
    """Create a service instance with controlled env vars."""
    defaults = {"DASHSCOPE_API_KEY": "sk-test-ds", "OPENROUTER_API_KEY": "sk-test-or"}
    defaults.update(env)
    with patch.dict(os.environ, defaults, clear=False):
        return ImageGeneratorService()


# ===========================================================================
# Mock 单元测试
# ===========================================================================


class TestDashScopeRefImage:
    """Case 1: dashscope + ref_image (本地路径)"""

    @patch("dashscope.ImageSynthesis.fetch")
    @patch("dashscope.ImageSynthesis.async_call")
    def test_imageedit_called_with_local_path(self, mock_async_call: MagicMock, mock_fetch: MagicMock, tmp_path: Path) -> None:
        ref = tmp_path / "cover.jpg"
        ref.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        mock_async_call.return_value = _make_dashscope_rsp(200, task_id="t-ref1")
        mock_fetch.return_value = _make_dashscope_fetch_rsp("SUCCEEDED", "https://oss.example.com/result.png")

        svc = _service_with_keys()
        prompt = _make_prompt(ref_image_url=str(ref))

        with patch.object(svc, "_save_from_url", return_value=tmp_path / "out.png"):
            result = svc.generate_single(prompt, _TEST_OPP_ID, provider="dashscope")

        assert result.status == "completed"
        assert result.provider == "dashscope"
        call_kwargs = mock_async_call.call_args
        assert call_kwargs.kwargs.get("model") == "wanx2.1-imageedit"
        assert call_kwargs.kwargs.get("base_image_url") == str(ref)
        assert call_kwargs.kwargs.get("function") == "stylization_all"


class TestDashScopePromptOnly:
    """Case 2: dashscope + prompt_only"""

    @patch("dashscope.ImageSynthesis.fetch")
    @patch("dashscope.ImageSynthesis.async_call")
    def test_t2i_turbo_called_without_ref(self, mock_async_call: MagicMock, mock_fetch: MagicMock, tmp_path: Path) -> None:
        mock_async_call.return_value = _make_dashscope_rsp(200, task_id="t-txt1")
        mock_fetch.return_value = _make_dashscope_fetch_rsp("SUCCEEDED", "https://oss.example.com/result.png")

        svc = _service_with_keys()
        prompt = _make_prompt()

        with patch.object(svc, "_save_from_url", return_value=tmp_path / "out.png"):
            result = svc.generate_single(prompt, _TEST_OPP_ID, provider="dashscope")

        assert result.status == "completed"
        call_kwargs = mock_async_call.call_args
        assert "imageedit" not in call_kwargs.kwargs.get("model", "")
        assert call_kwargs.kwargs.get("base_image_url", None) is None


class TestOpenRouterRefImage:
    """Case 3: openrouter + ref_image (本地路径 -> base64 data URI)"""

    def test_local_path_to_data_uri(self, tmp_path: Path) -> None:
        jpg = tmp_path / "test.jpg"
        jpg.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)

        uri = ImageGeneratorService._local_path_to_data_uri(str(jpg))
        assert uri.startswith("data:image/jpeg;base64,")
        decoded = base64.b64decode(uri.split(",", 1)[1])
        assert decoded == jpg.read_bytes()

    def test_png_path(self, tmp_path: Path) -> None:
        png = tmp_path / "test.png"
        png.write_bytes(b"\x89PNG" + b"\x00" * 10)

        uri = ImageGeneratorService._local_path_to_data_uri(str(png))
        assert uri.startswith("data:image/png;base64,")

    @patch("openai.OpenAI")
    def test_ref_image_sent_as_base64(self, mock_openai_cls: MagicMock, tmp_path: Path) -> None:
        ref = tmp_path / "ref.jpg"
        ref.write_bytes(b"\xff\xd8\xff" + b"\x00" * 50)

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.with_raw_response.create.return_value = _make_openrouter_raw_response()

        svc = _service_with_keys()
        prompt = _make_prompt(ref_image_url=str(ref))

        with patch.object(svc, "_extract_multipart_image", return_value=None), \
             patch.object(svc, "_extract_and_save_image", return_value=tmp_path / "out.png"):
            result = svc.generate_single(prompt, _TEST_OPP_ID, provider="openrouter")

        create_call = mock_client.chat.completions.with_raw_response.create.call_args
        messages = create_call.kwargs.get("messages", [])
        user_content = messages[0]["content"]
        assert isinstance(user_content, list)
        image_part = user_content[0]
        assert image_part["type"] == "image_url"
        assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")


class TestOpenRouterPromptOnly:
    """Case 4: openrouter + prompt_only"""

    @patch("openai.OpenAI")
    def test_text_only_prompt(self, mock_openai_cls: MagicMock, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.with_raw_response.create.return_value = _make_openrouter_raw_response()

        svc = _service_with_keys()
        prompt = _make_prompt()

        with patch.object(svc, "_extract_multipart_image", return_value=None), \
             patch.object(svc, "_extract_and_save_image", return_value=tmp_path / "out.png"):
            result = svc.generate_single(prompt, _TEST_OPP_ID, provider="openrouter")

        create_call = mock_client.chat.completions.with_raw_response.create.call_args
        messages = create_call.kwargs.get("messages", [])
        user_content = messages[0]["content"]
        assert isinstance(user_content, str)
        assert "Scene description:" in user_content


class TestAutoFallback:
    """Case 5: auto 模式 fallback 链——DashScope 失败后 fallback 到 OpenRouter"""

    @patch("openai.OpenAI")
    @patch("dashscope.ImageSynthesis.fetch")
    @patch("dashscope.ImageSynthesis.async_call")
    def test_dashscope_fails_then_openrouter_succeeds(
        self,
        mock_ds_async: MagicMock,
        mock_ds_fetch: MagicMock,
        mock_openai_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_ds_async.return_value = _make_dashscope_rsp(200, task_id="t-fail")
        mock_ds_fetch.return_value = _make_dashscope_fetch_rsp("FAILED")

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.with_raw_response.create.return_value = _make_openrouter_raw_response()

        svc = _service_with_keys()
        prompt = _make_prompt()

        with patch.object(svc, "_extract_multipart_image", return_value=None), \
             patch.object(svc, "_extract_and_save_image", return_value=tmp_path / "out.png"):
            result = svc.generate_single(prompt, _TEST_OPP_ID, provider="auto")

        assert mock_ds_async.called
        assert mock_openai_cls.called


class TestDashScopeErrorHandling:
    """Case 6: DashScope 非 200 时不崩溃，正确降级 text-only"""

    @patch("dashscope.ImageSynthesis.fetch")
    @patch("dashscope.ImageSynthesis.async_call")
    def test_imageedit_non200_falls_back_to_t2i(self, mock_async_call: MagicMock, mock_fetch: MagicMock, tmp_path: Path) -> None:
        rsp_fail = _make_dashscope_rsp(400, message="invalid image")
        rsp_ok = _make_dashscope_rsp(200, task_id="t-fallback")
        mock_async_call.side_effect = [rsp_fail, rsp_ok]
        mock_fetch.return_value = _make_dashscope_fetch_rsp("SUCCEEDED", "https://oss.example.com/result.png")

        svc = _service_with_keys()
        ref = tmp_path / "cover.jpg"
        ref.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
        prompt = _make_prompt(ref_image_url=str(ref))

        with patch.object(svc, "_save_from_url", return_value=tmp_path / "out.png"):
            result = svc.generate_single(prompt, _TEST_OPP_ID, provider="dashscope")

        assert result.status == "completed"
        assert mock_async_call.call_count == 2
        second_call = mock_async_call.call_args_list[1]
        assert "imageedit" not in second_call.kwargs.get("model", "")

    @patch("openai.OpenAI")
    @patch("dashscope.ImageSynthesis.async_call")
    def test_all_models_fail_returns_error(self, mock_async_call: MagicMock, mock_openai_cls: MagicMock) -> None:
        mock_async_call.return_value = _make_dashscope_rsp(500, code="InternalError", message="server error")
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.with_raw_response.create.side_effect = Exception("openrouter also fails")

        svc = _service_with_keys()
        prompt = _make_prompt()

        result = svc.generate_single(prompt, _TEST_OPP_ID, provider="dashscope")

        assert result.status == "failed"


class TestOnProgressCallback:
    """Verify on_progress is invoked with correct arguments."""

    @patch("dashscope.ImageSynthesis.fetch")
    @patch("dashscope.ImageSynthesis.async_call")
    def test_progress_called_on_generate_and_complete(self, mock_async_call: MagicMock, mock_fetch: MagicMock, tmp_path: Path) -> None:
        mock_async_call.return_value = _make_dashscope_rsp(200, task_id="t-cb")
        mock_fetch.return_value = _make_dashscope_fetch_rsp("SUCCEEDED", "https://oss.example.com/result.png")

        svc = _service_with_keys()
        prompt = _make_prompt(slot_id="content_1")
        progress_calls: list[tuple] = []

        def _on_progress(slot_id: str, status: str, data: dict) -> None:
            progress_calls.append((slot_id, status, data))

        with patch.object(svc, "_save_from_url", return_value=tmp_path / "out.png"):
            result = svc.generate_single(prompt, _TEST_OPP_ID, on_progress=_on_progress, provider="dashscope")

        assert len(progress_calls) >= 2
        assert progress_calls[0][1] == "generating"
        assert progress_calls[-1][1] == "completed"
        assert progress_calls[-1][0] == "content_1"


class TestBatchGeneration:
    """generate_batch routes each prompt and collects results."""

    @patch("dashscope.ImageSynthesis.fetch")
    @patch("dashscope.ImageSynthesis.async_call")
    def test_batch_returns_all_results(self, mock_async_call: MagicMock, mock_fetch: MagicMock, tmp_path: Path) -> None:
        mock_async_call.return_value = _make_dashscope_rsp(200, task_id="t-batch")
        mock_fetch.return_value = _make_dashscope_fetch_rsp("SUCCEEDED", "https://oss.example.com/r.png")

        svc = _service_with_keys()
        prompts = [_make_prompt(slot_id=f"slot_{i}") for i in range(3)]

        with patch.object(svc, "_save_from_url", return_value=tmp_path / "out.png"):
            results = svc.generate_batch(prompts, _TEST_OPP_ID, provider="dashscope")

        assert len(results) == 3
        assert all(r.status == "completed" for r in results)


# ===========================================================================
# 集成测试 (需要真实 API key)
# ===========================================================================

def _has_dashscope_key() -> bool:
    from apps.content_planning.services.image_generator import _ensure_env
    _ensure_env()
    return bool(os.environ.get("DASHSCOPE_API_KEY"))


def _has_openrouter_key() -> bool:
    from apps.content_planning.services.image_generator import _ensure_env
    _ensure_env()
    return bool(os.environ.get("OPENROUTER_API_KEY"))


_skip_no_dashscope = pytest.mark.skipif(not _has_dashscope_key(), reason="DASHSCOPE_API_KEY not set")
_skip_no_openrouter = pytest.mark.skipif(not _has_openrouter_key(), reason="OPENROUTER_API_KEY not set")
_skip_no_ref_image = pytest.mark.skipif(not _REAL_REF_IMAGE.is_file(), reason="Real ref image not downloaded")


@pytest.mark.integration
class TestIntegrationDashScopeRef:
    """Case A: dashscope + ref_image with real local image."""

    @_skip_no_dashscope
    @_skip_no_ref_image
    def test_dashscope_ref_image_real(self) -> None:
        svc = ImageGeneratorService()
        prompt = _make_prompt(
            slot_id="int_cover",
            prompt="北欧风格餐桌上的桌布，柔和自然光，氛围感",
            ref_image_url=str(_REAL_REF_IMAGE),
        )
        result = svc.generate_single(prompt, "test_integration", provider="dashscope")

        assert result.status == "completed", f"Expected completed, got {result.status}: {result.error}"
        assert result.provider == "dashscope"
        assert result.image_url
        assert result.elapsed_ms > 0
        generated = _REPO_ROOT / "data" / "generated_images" / "test_integration"
        assert generated.exists()


@pytest.mark.integration
class TestIntegrationDashScopePrompt:
    """Case B: dashscope + prompt_only."""

    @_skip_no_dashscope
    def test_dashscope_prompt_only_real(self) -> None:
        svc = ImageGeneratorService()
        prompt = _make_prompt(
            slot_id="int_txt",
            prompt="A cozy Nordic-style dining table with soft natural light, tablecloth and flowers",
        )
        result = svc.generate_single(prompt, "test_integration", provider="dashscope")

        assert result.status == "completed", f"Expected completed, got {result.status}: {result.error}"
        assert result.provider == "dashscope"
        assert result.elapsed_ms > 0


@pytest.mark.integration
class TestIntegrationOpenRouterPrompt:
    """Case C: openrouter + prompt_only.
    
    OpenRouter may return 403 ToS for certain prompts; when that happens
    the service falls back to DashScope. We accept either provider as long
    as the final result is completed.
    """

    @_skip_no_openrouter
    def test_openrouter_prompt_only_real(self) -> None:
        svc = ImageGeneratorService()
        prompt = _make_prompt(
            slot_id="int_or_txt",
            prompt="A warm cozy living room with soft lighting and plants",
        )
        result = svc.generate_single(prompt, "test_integration", provider="openrouter")

        assert result.status == "completed", f"Expected completed, got {result.status}: {result.error}"
        assert result.provider in ("openrouter", "dashscope")


@pytest.mark.integration
class TestIntegrationAutoFallback:
    """Case D: auto 模式 with ref_image，验证 fallback 链完整性."""

    @_skip_no_dashscope
    @_skip_no_ref_image
    def test_auto_with_ref_image_real(self) -> None:
        svc = ImageGeneratorService()
        prompt = _make_prompt(
            slot_id="int_auto",
            prompt="Nordic dining scene, tablecloth with flowers and warm light",
            ref_image_url=str(_REAL_REF_IMAGE),
        )
        result = svc.generate_single(prompt, "test_integration", provider="auto")

        assert result.status == "completed", f"Expected completed, got {result.status}: {result.error}"
        assert result.provider in ("dashscope", "openrouter")
        assert result.elapsed_ms > 0
