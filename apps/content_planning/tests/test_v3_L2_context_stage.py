"""L2 Context OS / Stage OS：PlanningContextAssembler、HealthChecker、ActionSpec 转换。"""

import pytest

from apps.content_planning.agents.base import AgentContext
from apps.content_planning.agents.context_assembler import PlanningContextAssembler, PlanningContext
from apps.content_planning.agents.health_checker import HealthChecker, HealthCheckResult, HealthIssue
from apps.content_planning.agents.memory import AgentMemory, MemoryEntry
from apps.content_planning.schemas.action_spec import (
    ActionSpec,
    actions_from_council_synthesis,
    actions_from_health_issues,
)
from apps.content_planning.schemas.asset_bundle import AssetBundle
from apps.content_planning.schemas.note_plan import NewNotePlan
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy


@pytest.fixture
def isolated_memory(tmp_path):
    """AgentMemory 每次 connect 使用新库；:memory: 会导致表不可见，故用临时文件库。"""
    return AgentMemory(str(tmp_path / "agent_memory.sqlite"))


def test_agent_memory_can_instantiate_with_colon_memory_string():
    """文档示例 AgentMemory(':memory:') 可构造；跨连接 recall 需用文件库（见 isolated_memory）。"""
    mem = AgentMemory(":memory:")
    assert mem is not None


def test_planning_context_assembler_instantiates_with_memory(isolated_memory):
    assembler = PlanningContextAssembler(memory=isolated_memory)
    assert assembler is not None


@pytest.mark.parametrize("stage", ["brief", "strategy", "plan", "asset"])
def test_assemble_returns_planning_context_with_stage_and_opportunity(stage: str, isolated_memory):
    assembler = PlanningContextAssembler(memory=isolated_memory)
    opp_id = "opp_l2_ctx_001"
    ctx = assembler.assemble(opp_id, stage, mode="deep")
    assert isinstance(ctx, PlanningContext)
    assert ctx.opportunity_id == opp_id
    assert ctx.stage == stage
    assert ctx.mode == "deep"


def test_enrich_agent_context_adds_planning_context_to_extra(isolated_memory):
    assembler = PlanningContextAssembler(memory=isolated_memory)
    planning_ctx = assembler.assemble("opp_x", "brief", mode="deep")
    agent_ctx = AgentContext(opportunity_id="opp_x", extra={})
    out = assembler.enrich_agent_context(agent_ctx, planning_ctx)
    assert "planning_context" in out.extra
    block = out.extra["planning_context"]
    assert block["stage"] == "brief"
    assert "upstream_summary" in block
    assert "downstream_completeness" in block
    assert "recent_council_consensuses" in block
    assert "open_questions" in block
    assert "scoring_shortfalls" in block
    assert "project_memory_context" in block
    assert "brand_preferences" in block


def test_build_context_prompt_block_returns_non_empty_when_memory_has_project_consensus(isolated_memory):
    mem = isolated_memory
    mem.store(
        MemoryEntry(
            opportunity_id="opp_prompt",
            category="project_consensus",
            content="项目共识：保持品牌调性一致",
            source_agent="test",
        )
    )
    assembler = PlanningContextAssembler(memory=mem)
    planning_ctx = assembler.assemble("opp_prompt", "strategy", mode="deep")
    block = assembler.build_context_prompt_block(planning_ctx)
    assert isinstance(block, str)
    assert len(block) > 0
    assert "项目" in block or "品牌" in block


def test_health_checker_instantiates():
    assert HealthChecker() is not None


def test_check_brief_health_returns_brief_stage_and_score():
    hc = HealthChecker()
    brief = OpportunityBrief(
        opportunity_id="opp_1",
        target_user=["白领"],
        content_goal="种草",
        primary_value="性价比",
    )
    result = hc.check_brief_health(brief)
    assert isinstance(result, HealthCheckResult)
    assert result.stage == "brief"
    assert isinstance(result.score, float)
    assert isinstance(result.issues, list)


def test_check_strategy_health_returns_strategy_stage():
    hc = HealthChecker()
    strategy = RewriteStrategy(
        opportunity_id="opp_1",
        positioning_statement="面向年轻用户",
        tone_of_voice="轻松",
        new_hook="痛点开场",
    )
    result = hc.check_strategy_health(strategy)
    assert result.stage == "strategy"
    assert isinstance(result.score, float)


def test_check_plan_health_returns_plan_stage():
    hc = HealthChecker()
    plan = NewNotePlan(opportunity_id="opp_1", theme="春日主题")
    result = hc.check_plan_health(plan)
    assert result.stage == "plan"


def test_check_asset_health_returns_asset_stage():
    hc = HealthChecker()
    bundle = AssetBundle(opportunity_id="opp_1")
    result = hc.check_asset_health(bundle)
    assert result.stage == "asset"
    assert result.score >= 0.6


def test_check_dispatches_by_stage_keyword():
    hc = HealthChecker()
    brief = OpportunityBrief(
        opportunity_id="opp_1",
        target_user=["用户"],
        content_goal="目标",
        primary_value="价值",
    )
    r = hc.check(stage="brief", brief=brief)
    assert r.stage == "brief"

    strategy = RewriteStrategy(
        positioning_statement="x", tone_of_voice="y", new_hook="z", opportunity_id="opp_1"
    )
    r2 = hc.check(stage="strategy", strategy=strategy, brief=brief)
    assert r2.stage == "strategy"

    plan = NewNotePlan(theme="t", opportunity_id="opp_1")
    r3 = hc.check(stage="plan", plan=plan, strategy=strategy)
    assert r3.stage == "plan"

    asset = AssetBundle(opportunity_id="opp_1")
    r4 = hc.check(stage="asset", asset_bundle=asset, plan=plan)
    assert r4.stage == "asset"


def test_brief_missing_target_user_yields_error_level_issue():
    hc = HealthChecker()
    brief = OpportunityBrief(
        opportunity_id="opp_1",
        target_user=[],
        content_goal="有内容目标",
        primary_value="有价值",
    )
    result = hc.check_brief_health(brief)
    error_issues = [i for i in result.issues if i.severity == "error"]
    assert any(i.dimension == "target_user" or i.target_field == "target_user" for i in error_issues)
    assert result.has_errors is True


def test_health_check_result_has_errors_and_is_healthy():
    r_ok = HealthCheckResult(stage="brief", issues=[], score=0.9)
    assert r_ok.has_errors is False
    assert r_ok.is_healthy is True

    r_err = HealthCheckResult(
        stage="brief",
        issues=[HealthIssue(severity="error", dimension="x", message="bad")],
        score=0.9,
    )
    assert r_err.has_errors is True
    assert r_err.is_healthy is False

    r_low = HealthCheckResult(stage="brief", issues=[], score=0.4)
    assert r_low.has_errors is False
    assert r_low.is_healthy is False


def test_actions_from_health_issues_returns_sorted_action_specs():
    issues = [
        HealthIssue(
            severity="warning",
            dimension="theme",
            message="主题弱",
            suggestion="补充主题",
            target_field="theme",
        ),
        HealthIssue(
            severity="error",
            dimension="brief",
            message="缺失",
            suggestion="重新生成",
            target_field="content_goal",
        ),
    ]
    actions = actions_from_health_issues(issues, opportunity_id="opp_a", stage="plan")
    assert len(actions) == 2
    assert all(isinstance(a, ActionSpec) for a in actions)
    assert actions[0].priority >= actions[1].priority


def test_actions_from_council_synthesis_returns_apply_and_steps():
    proposed = {"target_user": "新用户描述"}
    steps = ["下一步细化标题", {"label": "评审", "action_type": "evaluate"}]
    actions = actions_from_council_synthesis(
        proposed_updates=proposed,
        recommended_next_steps=steps,
        opportunity_id="opp_b",
        stage="brief",
    )
    assert len(actions) >= 2
    types = {a.action_type for a in actions}
    assert "apply" in types
    assert "evaluate" in types
