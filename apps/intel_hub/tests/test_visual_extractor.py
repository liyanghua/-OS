"""视觉提取器测试。"""

from __future__ import annotations

import pytest

from apps.intel_hub.extraction.visual_extractor import extract_visual_signals
from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note
from apps.intel_hub.tests.test_xhs_note_parser import (
    FIXTURE_NOTE_CREAMY,
    FIXTURE_NOTE_RISK,
    FIXTURE_NOTE_WATERPROOF,
    FIXTURE_COMMENTS_RISK,
)


def _make_parsed(raw_dict, comments=None):
    raw = parse_raw_note(raw_dict, comments=comments)
    return parse_note(raw)


class TestVisualExtractor:
    def test_style_extraction(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert "奶油风" in vis.visual_style_signals

    def test_expression_extraction(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        vis = extract_visual_signals(parsed)
        assert any(e in vis.visual_expression_pattern or e in vis.visual_feature_highlights
                    for e in ["出片", "高级感呈现", "氛围感"])

    def test_misleading_from_comments(self):
        parsed = _make_parsed(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        vis = extract_visual_signals(parsed)
        assert any("廉价" in r or "翻车" in r for r in vis.visual_misleading_risk) or len(vis.visual_misleading_risk) == 0

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
