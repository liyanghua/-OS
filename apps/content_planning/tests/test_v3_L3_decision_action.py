"""L3 Decision OS / Action OS：IntentRouter、Council 合成结构、ActionSpec 覆盖。"""

import pytest

from apps.content_planning.agents.base import AgentMessage
from apps.content_planning.agents.discussion import CouncilSynthesisBundle, DiscussionRound
from apps.content_planning.agents.intent_router import IntentRouter, RoutingResult
from apps.content_planning.schemas.action_spec import ActionSpec, ActionSpecBundle


def test_intent_router_instantiates():
    assert IntentRouter() is not None


def test_route_analyze_at_brief_stage():
    r = IntentRouter().route("帮我分析一下这个机会", "brief")
    assert isinstance(r, RoutingResult)
    assert r.intent == "analyze"
    assert r.target_agent == "brief_synthesizer"
    assert r.confidence > 0.0


def test_route_generate_at_strategy_stage():
    r = IntentRouter().route("生成内容策略", "strategy")
    assert r.intent == "generate"
    assert r.target_agent == "strategy_director"
    assert r.confidence > 0.0


def test_route_discuss_at_plan_stage():
    r = IntentRouter().route("讨论一下标题方案", "plan")
    assert r.intent == "discuss"
    assert r.target_agent == "council"
    assert r.confidence > 0.0


def test_route_evaluate_at_asset_stage():
    r = IntentRouter().route("评估一下这个资产包", "asset")
    assert r.intent == "evaluate"
    assert r.target_agent == "judge_agent"
    assert r.confidence > 0.0


def test_stage_constraint_generate_at_brief_still_uses_brief_agent():
    r = IntentRouter().route("生成", "brief")
    assert r.intent == "generate"
    assert r.target_agent == "brief_synthesizer"
    assert r.confidence > 0.0


@pytest.mark.parametrize(
    "message,stage,expected_intent,expected_agent",
    [
        ("深入研究竞品打法", "opportunity", "analyze", "trend_analyst"),
        ("帮我写一版 Brief 草稿", "brief", "generate", "brief_synthesizer"),
        ("圆桌讨论一下策略分歧", "strategy", "discuss", "council"),
        ("检查一下计划健康度", "plan", "evaluate", "health_checker"),
        ("输出新的视觉方案", "visual", "generate", "visual_director"),
        ("审查资产一致性风险", "asset", "evaluate", "judge_agent"),
    ],
)
def test_intent_router_at_least_six_samples_classified(
    message: str, stage: str, expected_intent: str, expected_agent: str
):
    r = IntentRouter().route(message, stage)
    assert r.intent == expected_intent
    assert r.target_agent == expected_agent
    assert r.confidence > 0.0


def test_council_synthesis_bundle_has_diff_lists():
    bundle = CouncilSynthesisBundle(
        consensus="一致",
        proposed_updates={},
        agreements=[],
        disagreements=[],
        open_questions=[],
        recommended_next_steps=[],
        alternatives=[],
        strategy_block_diffs=[{"field": "hook", "before": "a", "after": "b"}],
        plan_field_diffs=[{"path": "theme"}],
        asset_diffs=[{"slot": 1}],
    )
    assert bundle.strategy_block_diffs
    assert bundle.plan_field_diffs
    assert bundle.asset_diffs


def test_discussion_round_instantiates_with_required_fields():
    rnd = DiscussionRound(
        round_id="r1",
        opportunity_id="opp_1",
        stage="brief",
        topic="是否加强 CTA",
        participants=["brand_guardian", "growth_strategist"],
        messages=[AgentMessage(role="user", content="怎么看？")],
        consensus="倾向加强",
        proposed_updates={"content_goal": "更明确"},
        overall_score=0.72,
        status="concluded",
    )
    assert rnd.opportunity_id == "opp_1"
    assert rnd.stage == "brief"
    assert len(rnd.messages) == 1


def test_action_spec_all_action_types_instantiate():
    types = (
        "regenerate",
        "refine",
        "lock",
        "compare",
        "apply",
        "discuss",
        "evaluate",
        "export",
    )
    for i, at in enumerate(types):
        spec = ActionSpec(action_type=at, label=f"L{i}", target_object="brief")
        assert spec.action_type == at


def test_action_spec_all_target_objects_instantiate():
    targets = (
        "brief",
        "strategy",
        "template",
        "plan",
        "asset",
        "image_slot",
        "title",
        "body",
    )
    for to in targets:
        spec = ActionSpec(target_object=to, label=f"T-{to}")
        assert spec.target_object == to


def test_action_spec_confirmation_required_defaults_true():
    spec = ActionSpec(label="x")
    assert spec.confirmation_required is True


def test_action_spec_bundle_groups_metadata():
    bundle = ActionSpecBundle(
        source="health_checker",
        stage="plan",
        opportunity_id="opp_z",
        actions=[ActionSpec(action_type="refine", label="补主题", target_object="plan")],
    )
    assert bundle.source == "health_checker"
    assert bundle.stage == "plan"
    assert bundle.opportunity_id == "opp_z"
    assert len(bundle.actions) == 1
