"""XHS 机会卡流水线端到端测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apps.intel_hub.workflow.xhs_opportunity_pipeline import PipelineResult, run_xhs_opportunity_pipeline
from apps.intel_hub.tests.test_xhs_note_parser import (
    FIXTURE_COMMENTS_RISK,
    FIXTURE_NOTE_CREAMY,
    FIXTURE_NOTE_RISK,
    FIXTURE_NOTE_WATERPROOF,
)

ROOT = Path(__file__).resolve().parents[3]


def _load_configs():
    with open(ROOT / "config" / "ontology_mapping.yaml", encoding="utf-8") as f:
        ontology = yaml.safe_load(f)
    with open(ROOT / "config" / "opportunity_rules.yaml", encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    return ontology, rules


class TestXHSOpportunityPipeline:
    def test_single_note_produces_result(self):
        results = run_xhs_opportunity_pipeline([FIXTURE_NOTE_CREAMY])
        assert len(results) == 1
        r = results[0]
        assert r.note_id == "test_creamy_001"
        assert r.parsed_note is not None
        assert r.visual_signals is not None
        assert r.selling_theme_signals is not None
        assert r.scene_signals is not None
        assert r.cross_modal_validation is not None
        assert r.ontology_mapping is not None

    def test_creamy_generates_at_least_one_card(self):
        results = run_xhs_opportunity_pipeline([FIXTURE_NOTE_CREAMY])
        r = results[0]
        assert len(r.opportunity_cards) >= 1, f"Expected at least 1 card, got {len(r.opportunity_cards)}"

    def test_pipeline_output_has_ontology_mapping(self):
        results = run_xhs_opportunity_pipeline([FIXTURE_NOTE_CREAMY])
        mapping = results[0].ontology_mapping
        assert mapping is not None
        assert mapping.note_id == "test_creamy_001"
        assert mapping.source_signal_summary

    def test_pipeline_output_has_opportunities(self):
        results = run_xhs_opportunity_pipeline([FIXTURE_NOTE_CREAMY])
        cards = results[0].opportunity_cards
        assert len(cards) >= 1

    def test_card_confidence_in_range(self):
        results = run_xhs_opportunity_pipeline([FIXTURE_NOTE_CREAMY])
        for card in results[0].opportunity_cards:
            assert 0.0 <= card.confidence <= 1.0

    def test_card_evidence_refs_non_empty(self):
        results = run_xhs_opportunity_pipeline([FIXTURE_NOTE_CREAMY])
        for card in results[0].opportunity_cards:
            assert len(card.evidence_refs) > 0, f"Card '{card.title}' has no evidence_refs"

    def test_card_new_fields_populated(self):
        results = run_xhs_opportunity_pipeline([FIXTURE_NOTE_CREAMY])
        for card in results[0].opportunity_cards:
            assert isinstance(card.content_pattern_refs, list)
            assert isinstance(card.value_proposition_refs, list)
            assert isinstance(card.audience_refs, list)

    def test_batch_pipeline_multiple_notes(self):
        notes = [FIXTURE_NOTE_CREAMY, FIXTURE_NOTE_WATERPROOF, FIXTURE_NOTE_RISK]
        comment_index = {"test_risk_003": FIXTURE_COMMENTS_RISK}
        results = run_xhs_opportunity_pipeline(notes, comment_index=comment_index)
        assert len(results) == 3
        total_cards = sum(len(r.opportunity_cards) for r in results)
        assert total_cards >= 2, f"Expected at least 2 cards total, got {total_cards}"

    def test_cross_modal_validation_present(self):
        results = run_xhs_opportunity_pipeline([FIXTURE_NOTE_WATERPROOF])
        r = results[0]
        assert r.cross_modal_validation is not None
        assert hasattr(r.cross_modal_validation, "overall_consistency_score")

    def test_suggested_next_step_is_list(self):
        results = run_xhs_opportunity_pipeline([FIXTURE_NOTE_CREAMY])
        for card in results[0].opportunity_cards:
            assert isinstance(card.suggested_next_step, list), (
                f"Expected list for suggested_next_step, got {type(card.suggested_next_step)}"
            )
