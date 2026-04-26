"""Tests for ``apps.intel_hub.services.lens_generator``.

LLM is mocked via a fake LLMRouter so tests don't hit network.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

import yaml

from apps.content_planning.adapters.llm_router import (
    LLMMessage,
    LLMResponse,
    LLMRouter,
)
from apps.intel_hub.domain.category_lens import CategoryLens
from apps.intel_hub.services import lens_generator


def _make_valid_lens_dict() -> dict[str, Any]:
    return {
        "lens_id": "children_desk_mat",
        "category_cn": "儿童桌垫",
        "version": "1.0.0",
        "core_consumption_logic": "学习场景 + 儿童安全 + 易清洁",
        "keyword_aliases": ["儿童桌垫", "宝宝桌垫", "学习桌垫", "儿童学习桌垫", "幼儿桌垫"],
        "primary_user_jobs": ["保护桌面", "防水易清洁"],
        "key_pain_dimensions": ["难擦", "异味"],
        "trust_barriers": ["真的无毒吗"],
        "product_feature_taxonomy": ["防水", "防滑", "圆角"],
        "content_patterns": ["改造", "测评"],
        "audience_personas": ["宝妈", "学龄家长"],
        "scene_tasks": ["写作业", "画画"],
        "price_bands": [
            {"band": "白菜价", "range_cny": [9, 39],
             "user_mindset": "试水", "strategy": "强调防水"},
        ],
        "visual_prompt_hints": {
            "focus": ["材质特写"],
            "risk_flags": ["塑料感"],
            "people_state_taxonomy": [],
            "trust_signal_taxonomy": ["检测证书"],
            "content_format_taxonomy": ["改造前后"],
            "sample_strategy": {"max_images_per_note": 2, "prefer_cover": True,
                                "prefer_first_and_last": False},
        },
        "text_lexicons": {
            "pain_words": ["难擦"],
            "emotion_words": ["放心"],
            "trust_barrier_words": ["真的无毒吗"],
            "scene_words": {"学习桌": ["学习桌", "书桌"]},
            "style_words": {"护眼柔色": ["护眼", "柔光"]},
            "audience_words": {"宝妈": ["宝妈", "妈妈"]},
            "product_feature_words": {"防水": ["防水", "不怕水"]},
            "content_pattern_words": {"测评": ["测评", "实测"]},
            "comment_question_words": ["有没有味道"],
            "comment_trust_barrier_words": ["收到有异味怎么办"],
        },
        "user_expression_map": [
            {"user_phrase": "孩子总把桌子画脏",
             "product_features": ["可擦洗"],
             "proof_shots": ["一擦即净动图"]},
        ],
        "scoring_weights": {
            "pain_score": 0.20, "heat_score": 0.10, "trust_gap_score": 0.25,
            "product_fit_score": 0.15, "execution_score": 0.10,
            "competition_gap_score": 0.05, "scene_heat_score": 0.10,
            "style_trend_score": 0.05,
        },
        "linked_prompt_profile": "children_desk_mat_v1",
    }


class _ScriptedRouter(LLMRouter):
    """Minimal fake LLMRouter that yields scripted responses sequentially."""

    def __init__(self, responses: list[LLMResponse]) -> None:  # noqa: D401
        super().__init__(default_provider="deepseek", fallback_chain=["deepseek"])
        self._responses = list(responses)
        self.calls: list[list[LLMMessage]] = []

    def chat(self, messages, **kwargs):  # type: ignore[override]
        self.calls.append(list(messages))
        if not self._responses:
            return LLMResponse(content="", provider="deepseek", degraded=True,
                               degraded_reason="exhausted")
        return self._responses.pop(0)


class LensGeneratorTests(unittest.TestCase):
    def _ok_response(self, payload: dict[str, Any] | None = None) -> LLMResponse:
        return LLMResponse(
            content=json.dumps(payload or _make_valid_lens_dict(), ensure_ascii=False),
            model="deepseek-chat",
            provider="deepseek",
            elapsed_ms=42,
        )

    def test_generate_lens_with_mock_llm_succeeds_on_first_try(self) -> None:
        router = _ScriptedRouter([self._ok_response()])
        with self._tempdir() as drafts:
            path = lens_generator.generate_lens(
                category_cn="儿童桌垫",
                lens_id="children_desk_mat",
                router=router,
                output_dir=drafts,
            )
            self.assertTrue(path.exists())
            self.assertTrue(path.with_name(path.stem + ".review.md").exists())
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            lens = CategoryLens.model_validate(data)
            self.assertEqual(lens.lens_id, "children_desk_mat")
            self.assertEqual(lens.category_cn, "儿童桌垫")
            self.assertEqual(len(router.calls), 1)

    def test_generate_lens_retries_on_validation_error(self) -> None:
        bad = self._ok_response({"category_cn": "儿童桌垫"})  # 缺 lens_id 不会，因 normalize 会注入；改为 user_expression_map 里缺 user_phrase
        bad_payload = _make_valid_lens_dict()
        bad_payload["user_expression_map"] = [{"product_features": ["可擦洗"]}]  # 缺 user_phrase 必填
        bad = LLMResponse(
            content=json.dumps(bad_payload, ensure_ascii=False),
            model="deepseek-chat",
            provider="deepseek",
            elapsed_ms=42,
        )
        good = self._ok_response()
        router = _ScriptedRouter([bad, good])
        with self._tempdir() as drafts:
            path = lens_generator.generate_lens(
                category_cn="儿童桌垫",
                lens_id="children_desk_mat",
                router=router,
                output_dir=drafts,
                max_retries=2,
            )
            self.assertTrue(path.exists())
            self.assertEqual(len(router.calls), 2)
            second_user_msg = next(m for m in router.calls[1] if m.role == "user")
            self.assertIn("schema 校验", second_user_msg.content)

    def test_generate_lens_raises_after_max_retries(self) -> None:
        bad_payload = _make_valid_lens_dict()
        bad_payload["price_bands"] = [{"range_cny": [9, 39]}]  # PriceBand.band 必填
        bad = LLMResponse(
            content=json.dumps(bad_payload, ensure_ascii=False),
            model="deepseek-chat",
            provider="deepseek",
            elapsed_ms=42,
        )
        router = _ScriptedRouter([bad, bad, bad])
        with self._tempdir() as drafts:
            with self.assertRaises(lens_generator.LensGenerationError):
                lens_generator.generate_lens(
                    category_cn="儿童桌垫",
                    lens_id="children_desk_mat",
                    router=router,
                    output_dir=drafts,
                    max_retries=2,
                )
            self.assertEqual(len(router.calls), 3)  # 1 初始 + 2 重试

    def test_post_normalize_overrides_lens_id_and_category(self) -> None:
        """LLM 万一改了 lens_id / category_cn，post_normalize 必须强制纠正。"""
        rogue_payload = _make_valid_lens_dict()
        rogue_payload["lens_id"] = "wrong_id"
        rogue_payload["category_cn"] = "错误品类"
        router = _ScriptedRouter([self._ok_response(rogue_payload)])
        with self._tempdir() as drafts:
            path = lens_generator.generate_lens(
                category_cn="儿童桌垫",
                lens_id="children_desk_mat",
                router=router,
                output_dir=drafts,
            )
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(data["lens_id"], "children_desk_mat")
            self.assertEqual(data["category_cn"], "儿童桌垫")

    def test_review_report_contains_checklist(self) -> None:
        router = _ScriptedRouter([self._ok_response()])
        with self._tempdir() as drafts:
            path = lens_generator.generate_lens(
                category_cn="儿童桌垫",
                lens_id="children_desk_mat",
                router=router,
                output_dir=drafts,
            )
            review = path.with_name(path.stem + ".review.md").read_text(encoding="utf-8")
            self.assertIn("必检 checklist", review)
            self.assertIn("keyword_aliases 不要含上位品类词", review)
            self.assertIn("scoring_weights", review)

    def _tempdir(self):
        import tempfile
        return _CleanupDir(tempfile.mkdtemp(prefix="lens_gen_test_"))


class _CleanupDir:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, exc_type, exc, tb) -> None:
        import shutil
        shutil.rmtree(self.path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
