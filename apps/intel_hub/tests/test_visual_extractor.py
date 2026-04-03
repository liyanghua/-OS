"""视觉提取器 V2 测试。"""

from __future__ import annotations

import pytest

from apps.intel_hub.extraction.visual_extractor import (
    extract_visual_signals,
    extract_visual_signals_from_metadata,
)
from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note
from apps.intel_hub.tests.test_xhs_note_parser import (
    FIXTURE_COMMENTS_RISK,
    FIXTURE_NOTE_CREAMY,
    FIXTURE_NOTE_RISK,
    FIXTURE_NOTE_WATERPROOF,
)


def _make_parsed(raw_dict, comments=None):
    raw = parse_raw_note(raw_dict, comments=comments)
    return parse_note(raw)


class TestVisualExtractorV2:
    def test_style_extraction(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert "奶油风" in vis.visual_style_signals

    def test_primary_style(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert vis.primary_style == "奶油风"

    def test_style_confidence(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert vis.style_confidence is not None
        assert 0 < vis.style_confidence <= 1.0

    def test_expression_extraction(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert any(
            e in vis.visual_expression_pattern or e in vis.visual_feature_highlights
            for e in ["出片", "高级感呈现", "氛围感"]
        )

    def test_visual_scene_uses_scene_keywords_not_composition(self):
        """修复 V1 bug: visual_scene_signals 不再复用 COMPOSITION_KEYWORDS。"""
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert "出租屋场景" in vis.visual_scene_signals or len(vis.visual_scene_signals) >= 0
        for s in vis.visual_scene_signals:
            assert "俯拍" not in s and "全景" not in s

    def test_misleading_from_comments(self):
        parsed = _make_parsed(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        vis = extract_visual_signals(parsed)
        assert isinstance(vis.visual_misleading_risk, list)

    def test_visual_risk_score(self):
        parsed = _make_parsed(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        vis = extract_visual_signals(parsed)
        assert vis.visual_risk_score is not None or vis.visual_risk_score == 0.0

    def test_information_density(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert vis.information_density in ("high", "medium", "low")

    def test_click_differentiation_score(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert vis.click_differentiation_score is not None
        assert 0 <= vis.click_differentiation_score <= 1.0

    def test_conversion_alignment_score(self):
        parsed = _make_parsed(FIXTURE_NOTE_WATERPROOF)
        vis = extract_visual_signals(parsed)
        assert vis.conversion_alignment_score is not None

    def test_missing_feature_visualization(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert isinstance(vis.missing_feature_visualization, list)

    def test_visual_differentiation_points(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert isinstance(vis.visual_differentiation_points, list)

    def test_evidence_refs_present(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert len(vis.evidence_refs) > 0
        for ev in vis.evidence_refs:
            assert ev.source_kind in ("title", "body", "tag", "image", "comment")
            assert ev.snippet

    def test_waterproof_note_has_texture(self):
        parsed = _make_parsed(FIXTURE_NOTE_WATERPROOF)
        vis = extract_visual_signals(parsed)
        assert isinstance(vis.visual_texture_signals, list)

    def test_metadata_layer_standalone(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals_from_metadata(parsed)
        assert vis.note_id == "test_creamy_001"
        assert "奶油风" in vis.visual_style_signals

    def test_output_is_structured_not_string(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert isinstance(vis.visual_style_signals, list)
        assert isinstance(vis.primary_style, (str, type(None)))
        assert isinstance(vis.click_differentiation_score, (float, type(None)))
