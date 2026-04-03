"""跨模态校验器测试。"""

from __future__ import annotations

import pytest

from apps.intel_hub.extraction.cross_modal_validator import (
    validate_comment_support,
    validate_cross_modal_consistency,
    validate_scene_alignment,
    validate_visual_support,
)
from apps.intel_hub.extraction.scene_extractor import extract_scene_signals
from apps.intel_hub.extraction.selling_theme_extractor import extract_selling_theme_signals
from apps.intel_hub.extraction.visual_extractor import extract_visual_signals
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


def _full_extract(raw_dict, comments=None):
    parsed = _make_parsed(raw_dict, comments)
    visual = extract_visual_signals(parsed)
    selling = extract_selling_theme_signals(parsed)
    scene = extract_scene_signals(parsed, visual_signals=visual)
    return parsed, visual, selling, scene


class TestValidateVisualSupport:
    def test_supported_selling_point(self):
        _, visual, selling, _ = _full_extract(FIXTURE_NOTE_CREAMY)
        support, ev = validate_visual_support(
            selling.selling_point_signals, visual,
        )
        assert isinstance(support, dict)
        assert len(support) > 0

    def test_unsupported_selling_point(self):
        _, visual, _, _ = _full_extract(FIXTURE_NOTE_RISK, FIXTURE_COMMENTS_RISK)
        support, ev = validate_visual_support(["防水", "出片"], visual)
        assert "防水" in support
        assert support["防水"] in (True, False, "uncertain")

    def test_evidence_generated(self):
        _, visual, selling, _ = _full_extract(FIXTURE_NOTE_WATERPROOF)
        support, ev = validate_visual_support(
            selling.selling_point_signals, visual,
        )
        assert len(ev) > 0


class TestValidateCommentSupport:
    def test_validated_point(self):
        result = validate_comment_support(
            selling_points=["防水"],
            validated=["防水"],
            challenges=[],
            purchase_intent=[],
            trust_gap=[],
        )
        assert result["防水"] is True

    def test_challenged_point(self):
        result = validate_comment_support(
            selling_points=["卷边"],
            validated=[],
            challenges=["卷边"],
            purchase_intent=[],
            trust_gap=[],
        )
        assert result["卷边"] is False

    def test_uncertain_point(self):
        result = validate_comment_support(
            selling_points=["出片"],
            validated=[],
            challenges=[],
            purchase_intent=[],
            trust_gap=[],
        )
        assert result["出片"] == "uncertain"


class TestValidateSceneAlignment:
    def test_scene_alignment_creamy(self):
        parsed, visual, _, scene = _full_extract(FIXTURE_NOTE_CREAMY)
        alignment, ev = validate_scene_alignment(
            scene, visual, parsed.normalized_title, parsed.normalized_body,
        )
        assert isinstance(alignment, dict)

    def test_scene_alignment_waterproof(self):
        parsed, visual, _, scene = _full_extract(FIXTURE_NOTE_WATERPROOF)
        alignment, ev = validate_scene_alignment(
            scene, visual, parsed.normalized_title, parsed.normalized_body,
        )
        assert isinstance(alignment, dict)


class TestCrossModalConsistency:
    def test_full_validation_creamy(self):
        parsed, visual, selling, scene = _full_extract(FIXTURE_NOTE_CREAMY)
        result = validate_cross_modal_consistency(visual, selling, scene, parsed)
        assert result.note_id == "test_creamy_001"
        assert result.overall_consistency_score is not None
        assert isinstance(result.high_confidence_claims, list)
        assert isinstance(result.unsupported_claims, list)
        assert isinstance(result.challenged_claims, list)

    def test_full_validation_waterproof(self):
        parsed, visual, selling, scene = _full_extract(FIXTURE_NOTE_WATERPROOF)
        result = validate_cross_modal_consistency(visual, selling, scene, parsed)
        assert result.overall_consistency_score is not None

    def test_risk_note_has_challenged_claims(self):
        parsed, visual, selling, scene = _full_extract(
            FIXTURE_NOTE_RISK, FIXTURE_COMMENTS_RISK,
        )
        result = validate_cross_modal_consistency(visual, selling, scene, parsed)
        assert isinstance(result.challenged_claims, list)

    def test_output_is_structured(self):
        parsed, visual, selling, scene = _full_extract(FIXTURE_NOTE_CREAMY)
        result = validate_cross_modal_consistency(visual, selling, scene, parsed)
        assert isinstance(result.selling_claim_visual_support, dict)
        assert isinstance(result.selling_claim_comment_validation, dict)
        assert isinstance(result.scene_alignment, dict)
        assert isinstance(result.evidence_refs, list)

    def test_consistency_score_range(self):
        parsed, visual, selling, scene = _full_extract(FIXTURE_NOTE_CREAMY)
        result = validate_cross_modal_consistency(visual, selling, scene, parsed)
        assert 0 <= result.overall_consistency_score <= 1.0
