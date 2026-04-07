"""NewNotePlanCompiler 单元测试。"""

from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.template_match_result import (
    TemplateMatchEntry,
    TemplateMatchResult,
)
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.services.new_note_plan_compiler import NewNotePlanCompiler
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


def _make_brief() -> OpportunityBrief:
    return OpportunityBrief(
        opportunity_id="opp_001",
        brief_id="br_001",
        opportunity_summary="法式桌布早餐场景种草",
        content_goal="种草收藏",
        target_user=["精致宝妈"],
        target_scene=["早餐", "下午茶"],
        primary_value="氛围感强",
    )


def _make_strategy() -> RewriteStrategy:
    return RewriteStrategy(
        strategy_id="st_001",
        opportunity_id="opp_001",
        brief_id="br_001",
        template_id="tpl_001_scene_seed",
        positioning_statement="以氛围感为核心的场景种草",
        new_hook="场景氛围吸引——聚焦氛围感强",
        tone_of_voice="分享感、真实感",
        keep_elements=["桌布", "餐具"],
        title_strategy=["场景化标题", "利益点前置"],
        body_strategy=["围绕种草展开", "场景代入开头"],
        image_strategy=["图组: 吸睛→风格→质感→场景→转化"],
        risk_notes=["避免色差过大"],
        avoid_elements=["强促销"],
    )


def _make_template() -> TableclothMainImageStrategyTemplate:
    return TableclothMainImageStrategyTemplate(
        template_id="tpl_001_scene_seed",
        template_name="氛围感场景种草型",
        template_version="1.0",
        template_goal="场景代入激发收藏",
        cover_role="hook_click",
        image_sequence_pattern=["hook_click", "style_expand", "texture_expand", "usage_expand", "guide_expand"],
        hook_mechanism=["场景氛围吸引"],
        visual_rules=VisualRules(
            preferred_shots=["topdown"],
            required_elements=["桌布", "餐具"],
            color_direction=["warm"],
        ),
        copy_rules=CopyRules(
            title_style=["场景代入"],
            recommended_phrases=["氛围感拉满"],
            avoid_phrases=["全网最低"],
        ),
        scene_rules=SceneRules(must_have_scene=True),
        product_visibility_rules=ProductVisibilityRules(),
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
        ),
    )


def test_compile_full_plan():
    compiler = NewNotePlanCompiler()
    brief = _make_brief()
    strategy = _make_strategy()
    match_result = _make_match_result()
    template = _make_template()

    plan = compiler.compile(brief, strategy, match_result, template)

    assert plan.opportunity_id == "opp_001"
    assert plan.brief_id == "br_001"
    assert plan.strategy_id == "st_001"
    assert plan.template_id == "tpl_001_scene_seed"
    assert plan.note_goal == "种草收藏"
    assert len(plan.title_plan.title_axes) > 0
    assert plan.body_plan.opening_hook
    assert plan.image_plan is not None
    assert len(plan.image_plan.image_slots) == 5


def test_plan_backtrace_ids():
    compiler = NewNotePlanCompiler()
    plan = compiler.compile(_make_brief(), _make_strategy(), _make_match_result(), _make_template())

    assert plan.image_plan is not None
    assert plan.image_plan.opportunity_id == "opp_001"
    assert plan.image_plan.brief_id == "br_001"
    assert plan.image_plan.strategy_id == "st_001"


def test_plan_title_do_not_use():
    compiler = NewNotePlanCompiler()
    plan = compiler.compile(_make_brief(), _make_strategy(), _make_match_result(), _make_template())

    assert "全网最低" in plan.title_plan.do_not_use_phrases or "强促销" in plan.title_plan.do_not_use_phrases
