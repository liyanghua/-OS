"""XHS 机会卡编译器端到端测试 — 验证从笔记到机会卡的完整流程。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apps.intel_hub.compiler.opportunity_compiler import (
    compile_xhs_opportunities,
    merge_opportunities,
)
from apps.intel_hub.extraction.cross_modal_validator import validate_cross_modal_consistency
from apps.intel_hub.extraction.scene_extractor import extract_scene_signals
from apps.intel_hub.extraction.selling_theme_extractor import extract_selling_theme_signals
from apps.intel_hub.extraction.visual_extractor import extract_visual_signals
from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note
from apps.intel_hub.projector.ontology_projector import project_xhs_signals
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
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


def _run_pipeline_for_note(raw_dict, comments=None):
    raw = parse_raw_note(raw_dict, comments=comments)
    parsed = parse_note(raw)
    visual = extract_visual_signals(parsed)
    selling = extract_selling_theme_signals(parsed)
    scene = extract_scene_signals(parsed, visual_signals=visual)
    validation = validate_cross_modal_consistency(visual, selling, scene, parsed)
    ontology, rules = _load_configs()
    mapping = project_xhs_signals(visual, selling, scene, ontology, cross_modal=validation)
    cards = compile_xhs_opportunities(mapping, visual, selling, scene, rules, cross_modal=validation)
    return parsed, visual, selling, scene, mapping, cards, validation


class TestXHSOpportunityCompiler:
    def test_creamy_generates_cards(self):
        _, visual, selling, scene, mapping, cards, _ = _run_pipeline_for_note(FIXTURE_NOTE_CREAMY)
        assert len(cards) >= 1, f"Expected at least 1 card, got {len(cards)}"

    def test_waterproof_generates_selling_card(self):
        comments = [
            {"comment_id": "cw1", "note_id": "test_waterproof_002", "content": "防水效果真的好！一擦就干净", "nickname": "买家A", "like_count": "20", "sub_comment_count": "0", "parent_comment_id": 0},
            {"comment_id": "cw2", "note_id": "test_waterproof_002", "content": "求链接！想入手", "nickname": "买家B", "like_count": "8", "sub_comment_count": "0", "parent_comment_id": 0},
        ]
        _, _, selling, _, _, cards, _ = _run_pipeline_for_note(FIXTURE_NOTE_WATERPROOF, comments=comments)
        selling_cards = [c for c in cards if c.opportunity_type in ("demand", "product", "content")]
        assert len(selling_cards) >= 1

    def test_creamy_visual_card(self):
        _, _, _, _, _, cards, _ = _run_pipeline_for_note(FIXTURE_NOTE_CREAMY)
        visual_cards = [c for c in cards if c.opportunity_type == "visual"]
        assert len(visual_cards) >= 1

    def test_evidence_refs_on_all_cards(self):
        _, _, _, _, _, cards, _ = _run_pipeline_for_note(FIXTURE_NOTE_CREAMY)
        for card in cards:
            assert len(card.evidence_refs) > 0, f"Card '{card.title}' has no evidence_refs"

    def test_ontology_mapping_scene(self):
        _, _, _, _, mapping, _, _ = _run_pipeline_for_note(FIXTURE_NOTE_CREAMY)
        assert any("scene_rental_room" in r for r in mapping.scene_refs)

    def test_ontology_mapping_style(self):
        _, _, _, _, mapping, _, _ = _run_pipeline_for_note(FIXTURE_NOTE_CREAMY)
        assert any("style_creamy" in r for r in mapping.style_refs)

    def test_ontology_mapping_need_waterproof(self):
        _, _, _, _, mapping, _, _ = _run_pipeline_for_note(FIXTURE_NOTE_WATERPROOF)
        assert any("need_waterproof" in r for r in mapping.need_refs)

    def test_risk_note_has_risk_refs(self):
        _, _, _, _, mapping, _, _ = _run_pipeline_for_note(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        assert len(mapping.risk_refs) > 0

    def test_card_has_confidence_and_next_step(self):
        _, _, _, _, _, cards, _ = _run_pipeline_for_note(FIXTURE_NOTE_WATERPROOF)
        for card in cards:
            assert 0.0 < card.confidence <= 1.0
            assert card.suggested_next_step
            assert card.review_status == "pending"

    def test_scene_card_generated(self):
        _, _, _, _, _, cards, _ = _run_pipeline_for_note(FIXTURE_NOTE_CREAMY)
        scene_cards = [c for c in cards if c.opportunity_type == "scene"]
        assert len(scene_cards) >= 1

    def test_waterproof_scene_card(self):
        _, _, _, _, _, cards, _ = _run_pipeline_for_note(FIXTURE_NOTE_WATERPROOF)
        scene_cards = [c for c in cards if c.opportunity_type == "scene"]
        assert len(scene_cards) >= 1

    def test_new_fields_populated(self):
        _, _, _, _, _, cards, _ = _run_pipeline_for_note(FIXTURE_NOTE_CREAMY)
        for card in cards:
            assert isinstance(card.content_pattern_refs, list)
            assert isinstance(card.value_proposition_refs, list)
            assert isinstance(card.audience_refs, list)

    def test_suggested_next_step_is_list(self):
        _, _, _, _, _, cards, _ = _run_pipeline_for_note(FIXTURE_NOTE_CREAMY)
        for card in cards:
            assert isinstance(card.suggested_next_step, list)


class TestMergeOpportunities:
    def test_empty_list(self):
        assert merge_opportunities([]) == []

    def test_no_duplicates_passthrough(self):
        cards = [
            XHSOpportunityCard(opportunity_type="visual", scene_refs=["s1"], need_refs=["n1"]),
            XHSOpportunityCard(opportunity_type="demand", scene_refs=["s1"], need_refs=["n1"]),
        ]
        result = merge_opportunities(cards)
        assert len(result) == 2

    def test_duplicates_merged(self):
        cards = [
            XHSOpportunityCard(opportunity_type="visual", scene_refs=["s1"], need_refs=["n1"], source_note_ids=["a"]),
            XHSOpportunityCard(opportunity_type="visual", scene_refs=["s1"], need_refs=["n1"], source_note_ids=["b"]),
        ]
        result = merge_opportunities(cards)
        assert len(result) == 1
        assert "a" in result[0].source_note_ids
        assert "b" in result[0].source_note_ids

    def test_max_cards_limit(self):
        cards = [
            XHSOpportunityCard(opportunity_type=f"visual", scene_refs=[f"s{i}"], need_refs=[f"n{i}"])
            for i in range(10)
        ]
        result = merge_opportunities(cards, merge_rules={"max_cards_per_note": 3})
        assert len(result) == 3
