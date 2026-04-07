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
    assert brief.opportunity_type == "视觉"
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
    assert "风格定锚" in brief.template_hints or "质感佐证" in brief.template_hints


def test_template_hints_scene():
    compiler = BriefCompiler()
    card = _make_card(opportunity_type="scene")
    brief = compiler.compile(card)
    assert "场景种草" in brief.template_hints


def test_insight_fields_with_pipeline_data():
    compiler = BriefCompiler()
    card = _make_card()
    parsed_note = {
        "note_context": {
            "like_count": 200,
            "collect_count": 300,
            "comment_count": 50,
            "share_count": 20,
        },
        "cross_modal_validation": {
            "overall_consistency_score": 0.75,
            "high_confidence_claims": ["好看", "百搭"],
            "unsupported_claims": ["耐用"],
            "challenged_claims": [],
        },
        "selling_theme_signals": {
            "validated_selling_points": ["氛围感", "百搭"],
        },
    }
    brief = compiler.compile(card, parsed_note=parsed_note)

    assert brief.why_worth_doing is not None
    assert "藏赞比" in brief.why_worth_doing
    assert brief.competitive_angle is not None
    assert "好看" in brief.competitive_angle or "百搭" in brief.competitive_angle
    assert brief.engagement_proof is not None
    assert "300 收藏" in brief.engagement_proof
    assert brief.cross_modal_confidence_label is not None
    assert "高置信" in brief.cross_modal_confidence_label


def test_insight_fields_none_without_pipeline_data():
    compiler = BriefCompiler()
    card = _make_card()
    brief = compiler.compile(card)

    assert brief.engagement_proof is None
    assert brief.cross_modal_confidence_label is None


def test_content_goal_enriched_with_engagement():
    compiler = BriefCompiler()
    card = _make_card()
    parsed_note = {
        "note_context": {
            "like_count": 200,
            "collect_count": 200,
            "comment_count": 80,
            "share_count": 20,
        },
        "cross_modal_validation": {
            "overall_consistency_score": 0.8,
            "high_confidence_claims": [],
            "unsupported_claims": [],
            "challenged_claims": [],
        },
        "selling_theme_signals": {},
    }
    brief = compiler.compile(card, parsed_note=parsed_note)

    assert "收藏驱动" in brief.content_goal
    assert "已验证" in brief.content_goal


def test_cross_modal_confidence_labels():
    compiler = BriefCompiler()
    card = _make_card()

    high = {"note_context": {}, "selling_theme_signals": {},
            "cross_modal_validation": {"overall_consistency_score": 0.85, "high_confidence_claims": [], "unsupported_claims": [], "challenged_claims": []}}
    brief_h = compiler.compile(card, parsed_note=high)
    assert "高置信" in (brief_h.cross_modal_confidence_label or "")

    mid = {"note_context": {}, "selling_theme_signals": {},
           "cross_modal_validation": {"overall_consistency_score": 0.55, "high_confidence_claims": [], "unsupported_claims": ["x"], "challenged_claims": []}}
    brief_m = compiler.compile(card, parsed_note=mid)
    assert "中置信" in (brief_m.cross_modal_confidence_label or "")

    low = {"note_context": {}, "selling_theme_signals": {},
           "cross_modal_validation": {"overall_consistency_score": 0.2, "high_confidence_claims": [], "unsupported_claims": ["x", "y"], "challenged_claims": ["z"]}}
    brief_l = compiler.compile(card, parsed_note=low)
    assert "低置信" in (brief_l.cross_modal_confidence_label or "")
