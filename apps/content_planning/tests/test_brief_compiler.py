"""BriefCompiler 单元测试。"""

from apps.content_planning.services.brief_compiler import BriefCompiler
from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard


def _make_card(**overrides) -> XHSOpportunityCard:
    defaults = {
        "opportunity_id": "opp_test_001",
        "title": "法式奶油风桌布·居家早餐氛围感拉满",
        "summary": "多篇笔记围绕法式奶油风桌布在早餐/下午茶场景的搭配，视觉一致性高，用户收藏率突出。",
        "opportunity_type": "visual",
        "scene_refs": ["早餐", "下午茶", "居家"],
        "style_refs": ["法式", "奶油风", "ins风"],
        "need_refs": ["提升餐桌颜值", "拍照出片"],
        "visual_pattern_refs": ["暖调", "柔光", "平铺构图"],
        "audience_refs": ["精致生活宝妈", "租房女生"],
        "value_proposition_refs": ["氛围感强", "百搭不挑桌"],
        "content_pattern_refs": ["场景种草"],
        "evidence_refs": [
            XHSEvidenceRef(source_kind="body", snippet="这块桌布太出片了！"),
            XHSEvidenceRef(source_kind="title", snippet="法式奶油风桌布"),
        ],
        "source_note_ids": ["note_001", "note_002"],
        "risk_refs": ["过度滤镜导致色差"],
        "suggested_next_step": ["制作场景种草笔记"],
        "confidence": 0.85,
    }
    defaults.update(overrides)
    return XHSOpportunityCard(**defaults)


def test_compile_basic():
    compiler = BriefCompiler()
    card = _make_card()
    brief = compiler.compile(card)

    assert brief.opportunity_id == "opp_test_001"
    assert brief.opportunity_type == "visual"
    assert "早餐" in brief.target_scene
    assert "精致生活宝妈" in brief.target_user
    assert brief.content_goal == "种草收藏"
    assert brief.primary_value == "氛围感强"
    assert len(brief.visual_style_direction) > 0
    assert len(brief.proof_from_source) > 0


def test_compile_demand_type():
    compiler = BriefCompiler()
    card = _make_card(opportunity_type="demand", need_refs=["性价比高", "百元内"])
    brief = compiler.compile(card)

    assert brief.content_goal == "转化"
    assert brief.core_motive == "性价比高"


def test_compile_with_review():
    compiler = BriefCompiler()
    card = _make_card()
    review = {"review_count": 3, "avg_quality_score": 8.5}
    brief = compiler.compile(card, review_summary=review)
    assert brief.opportunity_id == "opp_test_001"


def test_template_hints_visual():
    compiler = BriefCompiler()
    card = _make_card(opportunity_type="visual")
    brief = compiler.compile(card)
    assert "style_anchor" in brief.template_hints or "texture_proof" in brief.template_hints


def test_template_hints_scene():
    compiler = BriefCompiler()
    card = _make_card(opportunity_type="scene")
    brief = compiler.compile(card)
    assert "scene_seed" in brief.template_hints
