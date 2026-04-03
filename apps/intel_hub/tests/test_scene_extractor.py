"""场景提取器测试。"""

from __future__ import annotations

import pytest

from apps.intel_hub.extraction.scene_extractor import extract_scene_signals
from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note
from apps.intel_hub.tests.test_xhs_note_parser import (
    FIXTURE_NOTE_CREAMY,
    FIXTURE_NOTE_WATERPROOF,
)


def _make_parsed(raw_dict, comments=None):
    raw = parse_raw_note(raw_dict, comments=comments)
    return parse_note(raw)


class TestSceneExtractor:
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
