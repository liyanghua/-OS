"""ontology_projector 子函数 + 完整映射测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apps.intel_hub.extraction.cross_modal_validator import validate_cross_modal_consistency
from apps.intel_hub.extraction.scene_extractor import extract_scene_signals
from apps.intel_hub.extraction.selling_theme_extractor import extract_selling_theme_signals
from apps.intel_hub.extraction.visual_extractor import extract_visual_signals
from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note
from apps.intel_hub.projector.ontology_projector import (
    build_evidence_refs,
    build_source_signal_summary,
    map_audiences,
    map_content_patterns,
    map_needs,
    map_risks,
    map_scenes,
    map_styles,
    map_value_propositions,
    map_visual_patterns,
    project_xhs_signals,
)
from apps.intel_hub.schemas.xhs_validation import CrossModalValidation
from apps.intel_hub.tests.test_xhs_note_parser import (
    FIXTURE_COMMENTS_RISK,
    FIXTURE_NOTE_CREAMY,
    FIXTURE_NOTE_RISK,
    FIXTURE_NOTE_WATERPROOF,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def ontology_config():
    with open(ROOT / "config" / "ontology_mapping.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _extract_signals(raw_dict, comments=None):
    raw = parse_raw_note(raw_dict, comments=comments)
    parsed = parse_note(raw)
    visual = extract_visual_signals(parsed)
    selling = extract_selling_theme_signals(parsed)
    scene = extract_scene_signals(parsed, visual_signals=visual)
    validation = validate_cross_modal_consistency(visual, selling, scene, parsed)
    return visual, selling, scene, validation


class TestMapStyles:
    def test_creamy_note_maps_to_style_creamy(self, ontology_config):
        visual, _, scene, _ = _extract_signals(FIXTURE_NOTE_CREAMY)
        refs = map_styles(visual, scene, ontology_config)
        assert any("creamy" in r for r in refs), f"Expected style_creamy in {refs}"


class TestMapScenes:
    def test_creamy_note_maps_to_rental_room(self, ontology_config):
        visual, _, scene, _ = _extract_signals(FIXTURE_NOTE_CREAMY)
        refs = map_scenes(scene, visual, ontology_config)
        assert any("rental_room" in r for r in refs), f"Expected scene_rental_room in {refs}"


class TestMapNeeds:
    def test_waterproof_note_maps_to_need_waterproof(self, ontology_config):
        _, selling, scene, _ = _extract_signals(FIXTURE_NOTE_WATERPROOF)
        refs = map_needs(selling, scene, ontology_config)
        assert any("waterproof" in r for r in refs), f"Expected need_waterproof in {refs}"


class TestMapRisks:
    def test_risk_note_maps_risks(self, ontology_config):
        visual, selling, _, _ = _extract_signals(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        refs = map_risks(selling, visual, None, ontology_config)
        assert len(refs) > 0, "Expected at least one risk ref"

    def test_cross_modal_unsupported_adds_claim_unverified(self, ontology_config):
        visual, selling, _, _ = _extract_signals(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        fake_cm = CrossModalValidation(
            note_id="test_risk_003",
            unsupported_claims=["假的卖点"],
        )
        refs = map_risks(selling, visual, fake_cm, ontology_config)
        assert "risk_claim_unverified" in refs


class TestMapVisualPatterns:
    def test_creamy_visual_patterns(self, ontology_config):
        visual, _, _, _ = _extract_signals(FIXTURE_NOTE_CREAMY)
        refs = map_visual_patterns(visual, ontology_config)
        assert isinstance(refs, list)


class TestMapValuePropositions:
    def test_value_propositions_generated(self, ontology_config):
        visual, selling, scene, _ = _extract_signals(FIXTURE_NOTE_WATERPROOF)
        refs = map_value_propositions(selling, visual, scene, ontology_config)
        assert len(refs) > 0, "Expected at least one VP ref"


class TestBuildSourceSignalSummary:
    def test_summary_includes_keywords(self):
        visual, selling, scene, _ = _extract_signals(FIXTURE_NOTE_CREAMY)
        summary = build_source_signal_summary(visual, selling, scene)
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestBuildEvidenceRefs:
    def test_evidence_refs_collected(self):
        visual, selling, scene, _ = _extract_signals(FIXTURE_NOTE_CREAMY)
        evidence = build_evidence_refs(visual, selling, scene)
        assert len(evidence) > 0


class TestProjectXHSSignals:
    def test_full_mapping_creamy(self, ontology_config):
        visual, selling, scene, validation = _extract_signals(FIXTURE_NOTE_CREAMY)
        mapping = project_xhs_signals(visual, selling, scene, ontology_config, cross_modal=validation)
        assert mapping.note_id == "test_creamy_001"
        assert any("creamy" in s for s in mapping.style_refs)
        assert any("rental_room" in s for s in mapping.scene_refs)
        assert mapping.source_signal_summary
        assert len(mapping.evidence_refs) > 0

    def test_full_mapping_waterproof(self, ontology_config):
        visual, selling, scene, validation = _extract_signals(FIXTURE_NOTE_WATERPROOF)
        mapping = project_xhs_signals(visual, selling, scene, ontology_config, cross_modal=validation)
        assert mapping.note_id == "test_waterproof_002"
        assert any("waterproof" in n for n in mapping.need_refs)
        assert len(mapping.value_proposition_refs) > 0

    def test_full_mapping_risk(self, ontology_config):
        visual, selling, scene, validation = _extract_signals(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        mapping = project_xhs_signals(visual, selling, scene, ontology_config, cross_modal=validation)
        assert len(mapping.risk_refs) > 0
