"""RewriteStrategyGenerator 单元测试。"""

from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.template_match_result import (
    TemplateMatchEntry,
    TemplateMatchResult,
)
from apps.content_planning.services.strategy_generator import RewriteStrategyGenerator
from apps.template_extraction.schemas.template import (
    ClusterFeatures,
    CopyRules,
    DerivationRules,
    EvaluationMetrics,
    ProductVisibilityRules,
    SceneRules,
    TableclothMainImageStrategyTemplate,
    VisualRules,
)


def _make_brief(**overrides) -> OpportunityBrief:
    defaults = {
        "opportunity_id": "opp_001",
        "opportunity_type": "visual",
        "opportunity_title": "法式奶油风桌布",
        "opportunity_summary": "法式奶油风桌布在早餐场景下氛围感拉满",
        "target_user": ["精致宝妈"],
        "target_scene": ["早餐", "下午茶"],
        "core_motive": "提升餐桌颜值",
        "content_goal": "种草收藏",
        "primary_value": "氛围感强",
        "secondary_values": ["百搭", "出片"],
        "visual_style_direction": ["法式", "奶油风"],
        "avoid_directions": ["过度滤镜"],
    }
    defaults.update(overrides)
    return OpportunityBrief(**defaults)


def _make_template() -> TableclothMainImageStrategyTemplate:
    return TableclothMainImageStrategyTemplate(
        template_id="tpl_001_scene_seed",
        template_name="氛围感场景种草型",
        template_version="1.0",
        template_goal="通过场景代入激发收藏与种草",
        cover_role="hook_click",
        image_sequence_pattern=["hook_click", "style_expand", "texture_expand", "usage_expand", "guide_expand"],
        hook_mechanism=["场景氛围吸引", "色彩视觉冲击"],
        best_for=["桌布场景种草", "氛围感展示"],
        fit_scenarios=["早餐", "下午茶", "居家"],
        fit_styles=["法式", "奶油风"],
        visual_rules=VisualRules(
            preferred_shots=["topdown", "wide_scene"],
            required_elements=["桌布", "餐具"],
            color_direction=["warm", "cream"],
        ),
        copy_rules=CopyRules(
            title_style=["场景代入", "口语化"],
            recommended_phrases=["氛围感拉满", "出片神器"],
            avoid_phrases=["全网最低", "限时秒杀"],
        ),
        scene_rules=SceneRules(must_have_scene=True, scene_types=["早餐", "下午茶"]),
        product_visibility_rules=ProductVisibilityRules(tablecloth_visibility_min=0.3),
        risk_rules=["避免色差过大"],
        avoid_when=["纯棚拍"],
        cluster_features=ClusterFeatures(),
        evaluation_metrics=EvaluationMetrics(),
        derivation_rules=DerivationRules(),
    )


def _make_match_result() -> TemplateMatchResult:
    return TemplateMatchResult(
        opportunity_id="opp_001",
        brief_id="br_001",
        primary_template=TemplateMatchEntry(
            template_id="tpl_001_scene_seed",
            template_name="氛围感场景种草型",
            score=0.8,
            reason="场景匹配",
        ),
    )


def test_generate_basic():
    gen = RewriteStrategyGenerator()
    brief = _make_brief()
    match_result = _make_match_result()
    tpl = _make_template()

    strategy = gen.generate(brief, match_result, tpl)

    assert strategy.opportunity_id == "opp_001"
    assert strategy.template_id == "tpl_001_scene_seed"
    assert "提升餐桌颜值" in strategy.positioning_statement
    assert strategy.tone_of_voice
    assert len(strategy.title_strategy) > 0
    assert len(strategy.body_strategy) > 0
    assert len(strategy.image_strategy) > 0
    assert len(strategy.keep_elements) > 0


def test_generate_avoid_elements():
    gen = RewriteStrategyGenerator()
    brief = _make_brief(avoid_directions=["过度滤镜", "强促销"])
    strategy = gen.generate(brief, _make_match_result(), _make_template())
    assert any("过度滤镜" in e or "强促销" in e for e in strategy.avoid_elements + strategy.replace_elements)


def test_generate_demand_type():
    gen = RewriteStrategyGenerator()
    brief = _make_brief(content_goal="转化")
    strategy = gen.generate(brief, _make_match_result(), _make_template())
    assert "利益点" in strategy.tone_of_voice or "转化" in strategy.tone_of_voice
