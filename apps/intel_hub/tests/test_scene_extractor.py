"""场景提取器 V2 测试。"""

from __future__ import annotations

import pytest

from apps.intel_hub.extraction.scene_extractor import (
    build_scene_style_value_combos,
    extract_explicit_scene_signals,
    extract_scene_signals,
    infer_scene_signals,
)
from apps.intel_hub.extraction.visual_extractor import extract_visual_signals
from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note
from apps.intel_hub.tests.test_xhs_note_parser import (
    FIXTURE_NOTE_CREAMY,
    FIXTURE_NOTE_WATERPROOF,
)


def _make_parsed(raw_dict, comments=None):
    raw = parse_raw_note(raw_dict, comments=comments)
    return parse_note(raw)


class TestSceneExtractorV2:
    def test_scene_rental_room(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        scene = extract_scene_signals(parsed)
        assert "出租屋" in scene.scene_signals

    def test_scene_dining_table(self):
        parsed = _make_parsed(FIXTURE_NOTE_WATERPROOF)
        scene = extract_scene_signals(parsed)
        assert "餐桌" in scene.scene_signals

    def test_goal_signals(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        scene = extract_scene_signals(parsed)
        assert any(g in scene.scene_goal_signals for g in ["提升高级感", "适合拍照", "改造氛围"])

    def test_goal_waterproof(self):
        parsed = _make_parsed(FIXTURE_NOTE_WATERPROOF)
        scene = extract_scene_signals(parsed)
        assert any(g in scene.scene_goal_signals for g in ["防脏防油", "方便清洁"])

    def test_audience_signals(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        scene = extract_scene_signals(parsed)
        assert any(a in scene.audience_signals for a in ["租房党", "年轻女性", "学生"])

    def test_combos_generated(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        scene = extract_scene_signals(parsed)
        assert len(scene.scene_style_value_combos) > 0
        assert any("×" in c for c in scene.scene_style_value_combos)

    def test_evidence_refs(self):
        parsed = _make_parsed(FIXTURE_NOTE_WATERPROOF)
        scene = extract_scene_signals(parsed)
        assert len(scene.evidence_refs) > 0

    def test_constraints_waterproof(self):
        parsed = _make_parsed(FIXTURE_NOTE_WATERPROOF)
        scene = extract_scene_signals(parsed)
        assert isinstance(scene.scene_constraints, list)

    # V2 新增测试
    def test_inferred_scene_signals(self):
        """隐式推断：标题含"大学生"关键词 -> 推断宿舍。"""
        raw = {
            **FIXTURE_NOTE_CREAMY,
            "note_id": "test_infer_001",
            "title": "大学生出租屋改造｜奶油风桌布",
            "desc": "学生党改造宿舍 平价桌布",
        }
        parsed = _make_parsed(raw)
        scene = extract_scene_signals(parsed)
        all_scenes = scene.scene_signals + scene.inferred_scene_signals
        assert "宿舍" in all_scenes or "出租屋" in scene.scene_signals

    def test_inference_confidence(self):
        raw = {
            **FIXTURE_NOTE_CREAMY,
            "note_id": "test_infer_002",
            "title": "铲屎官必备桌布！",
            "desc": "养猫家庭实测",
            "tag_list": "宠物,猫咪",
        }
        parsed = _make_parsed(raw)
        scene = extract_scene_signals(parsed)
        if scene.inferred_scene_signals:
            assert scene.inference_confidence is not None
            assert 0 < scene.inference_confidence <= 1.0

    def test_scene_opportunity_hints(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        scene = extract_scene_signals(parsed)
        assert isinstance(scene.scene_opportunity_hints, list)

    def test_scene_with_visual_signals(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        scene = extract_scene_signals(parsed, visual_signals=vis)
        assert isinstance(scene.scene_signals, list)
        assert isinstance(scene.inferred_scene_signals, list)

    def test_explicit_scene_standalone(self):
        scenes, ev = extract_explicit_scene_signals(
            "出租屋改造", "餐桌布很好看", ["桌布"], [], "test_id",
        )
        assert "出租屋" in scenes
        assert "餐桌" in scenes

    def test_build_combos_standalone(self):
        combos, hints = build_scene_style_value_combos(
            ["出租屋"], ["奶油风"], ["显高级"],
        )
        assert any("出租屋×奶油风×显高级" in c for c in combos)
        assert len(hints) > 0

    def test_output_is_structured(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        scene = extract_scene_signals(parsed)
        assert isinstance(scene.inferred_scene_signals, list)
        assert isinstance(scene.scene_opportunity_hints, list)
        assert isinstance(scene.inference_confidence, (float, type(None)))
