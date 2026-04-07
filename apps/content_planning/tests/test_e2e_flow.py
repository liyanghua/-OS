"""端到端 flow 集成测试（plan_only 模式，mock adapter）。"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from apps.content_planning.exceptions import OpportunityNotPromotedError
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.services.opportunity_to_plan_flow import OpportunityToPlanFlow
from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard


def _make_card() -> XHSOpportunityCard:
    return XHSOpportunityCard(
        opportunity_id="opp_e2e_001",
        title="法式奶油风桌布·居家早餐氛围感拉满",
        summary="多篇笔记围绕法式奶油风桌布在早餐场景的搭配，视觉一致性高。",
        opportunity_type="visual",
        scene_refs=["早餐", "下午茶", "居家"],
        style_refs=["法式", "奶油风"],
        need_refs=["提升餐桌颜值"],
        visual_pattern_refs=["暖调"],
        audience_refs=["精致宝妈"],
        value_proposition_refs=["氛围感强"],
        evidence_refs=[XHSEvidenceRef(snippet="这块桌布太出片了")],
        source_note_ids=["note_001"],
        confidence=0.85,
        opportunity_status="promoted",
    )


@pytest.fixture()
def mock_flow() -> OpportunityToPlanFlow:
    adapter = MagicMock()
    adapter.get_card.return_value = _make_card()
    adapter.get_source_notes.return_value = []
    adapter.get_review_summary.return_value = {"review_count": 2, "avg_quality_score": 8.0}

    flow = OpportunityToPlanFlow(adapter=adapter)
    return flow


def test_build_brief(mock_flow: OpportunityToPlanFlow):
    brief = mock_flow.build_brief("opp_e2e_001")
    assert isinstance(brief, OpportunityBrief)
    assert brief.opportunity_id == "opp_e2e_001"
    assert brief.content_goal == "种草收藏"


def test_build_note_plan_plan_only(mock_flow: OpportunityToPlanFlow):
    result = mock_flow.build_note_plan("opp_e2e_001", with_generation=False)

    assert "brief" in result
    assert "match_result" in result
    assert "strategy" in result
    assert "note_plan" in result
    assert "generated" not in result

    assert result["brief"]["opportunity_id"] == "opp_e2e_001"
    assert result["match_result"]["primary_template"]["template_id"]
    assert result["strategy"]["template_id"]
    assert result["note_plan"]["opportunity_id"] == "opp_e2e_001"


def test_build_note_plan_with_generation(mock_flow: OpportunityToPlanFlow):
    result = mock_flow.build_note_plan("opp_e2e_001", with_generation=True)

    assert "generated" in result
    gen = result["generated"]
    assert "titles" in gen
    assert "body" in gen
    assert "image_briefs" in gen
    assert len(gen["titles"]["titles"]) >= 1
    assert gen["body"]["body_draft"]


def test_card_not_found():
    adapter = MagicMock()
    adapter.get_card.return_value = None
    flow = OpportunityToPlanFlow(adapter=adapter)

    with pytest.raises(ValueError, match="未找到"):
        flow.build_brief("nonexistent")


def test_card_not_promoted():
    card = _make_card()
    card = card.model_copy(update={"opportunity_status": "pending_review"})
    adapter = MagicMock()
    adapter.get_card.return_value = card
    flow = OpportunityToPlanFlow(adapter=adapter)

    with pytest.raises(OpportunityNotPromotedError):
        flow.build_brief("opp_e2e_001")


def test_generated_trace_ids(mock_flow: OpportunityToPlanFlow):
    result = mock_flow.build_note_plan("opp_e2e_001", with_generation=True)
    gen = result["generated"]
    for key in ("titles", "body", "image_briefs"):
        d = gen[key]
        assert d["opportunity_id"] == "opp_e2e_001"
        assert d["brief_id"]
        assert d["strategy_id"]
        assert d["template_id"]
