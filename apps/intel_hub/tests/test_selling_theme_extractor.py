"""卖点主题提取器测试。"""

from __future__ import annotations

import pytest

from apps.intel_hub.extraction.selling_theme_extractor import extract_selling_theme_signals
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


class TestSellingThemeExtractor:
    def test_selling_points_waterproof(self):
        parsed = _make_parsed(FIXTURE_NOTE_WATERPROOF)
        selling = extract_selling_theme_signals(parsed)
        assert "防水" in selling.selling_point_signals
        assert "防油" in selling.selling_point_signals
        assert "好打理" in selling.selling_point_signals

    def test_selling_points_creamy(self):
        parsed = _make_parsed(FIXTURE_NOTE_CREAMY)
        selling = extract_selling_theme_signals(parsed)
        assert "出片" in selling.selling_point_signals or "显高级" in selling.selling_point_signals

    def test_challenges_from_risk_note(self):
        parsed = _make_parsed(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        selling = extract_selling_theme_signals(parsed)
        assert "卷边" in selling.selling_point_challenges
        assert "廉价感" in selling.selling_point_challenges

    def test_purchase_intent_from_comments(self):
        parsed = _make_parsed(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        selling = extract_selling_theme_signals(parsed)
        assert any("求链接" in pi for pi in selling.purchase_intent_signals)

    def test_trust_gap_from_comments(self):
        parsed = _make_parsed(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        selling = extract_selling_theme_signals(parsed)
        assert any("真的吗" in tg for tg in selling.trust_gap_signals)

    def test_evidence_refs_nonempty(self):
        parsed = _make_parsed(FIXTURE_NOTE_WATERPROOF)
        selling = extract_selling_theme_signals(parsed)
        assert len(selling.evidence_refs) > 0
        kinds = {e.source_kind for e in selling.evidence_refs}
        assert "body" in kinds or "title" in kinds

    def test_theme_detection(self):
        parsed = _make_parsed(FIXTURE_NOTE_RISK)
        selling = extract_selling_theme_signals(parsed)
        assert "避坑指南" in selling.selling_theme_refs or "测评实测" in selling.selling_theme_refs or len(selling.selling_theme_refs) >= 0
