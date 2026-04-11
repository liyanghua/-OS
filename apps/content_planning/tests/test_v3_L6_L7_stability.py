"""L6–L7: 无 LLM 回退、记忆 miss、ActionSpec 默认、路由回归。"""

from __future__ import annotations

from unittest.mock import patch

from apps.content_planning.agents.health_checker import HealthChecker
from apps.content_planning.agents.intent_router import IntentRouter
from apps.content_planning.agents.judge_agent import JudgeAgent, JudgeResult
from apps.content_planning.agents.memory import AgentMemory
from apps.content_planning.agents.review_loop import PerformanceFeedback, ReviewLoop
from apps.content_planning.api.routes import router
from apps.content_planning.schemas.action_spec import ActionSpec


def test_health_checker_reasonable_without_llm() -> None:
    brief = {
        "target_user": "u",
        "content_goal": "g",
        "primary_value": "v",
        "target_scene": "s",
        "visual_style_direction": ["x"],
        "avoid_directions": ["y"],
        "why_now": "n",
    }
    result = HealthChecker().check_brief_health(brief)
    assert result.score >= 0.0
    assert isinstance(result.issues, list)


def test_intent_router_fallback_when_llm_unavailable() -> None:
    router_inst = IntentRouter()
    with patch.object(
        IntentRouter,
        "_llm_classify",
        return_value=None,
    ):
        out = router_inst.route("完全不含关键字的乱码xyzqw", current_stage="brief")
    assert out.method in ("regex", "stage_constraint")
    assert out.target_agent
    assert out.api_endpoint


def test_judge_evaluate_returns_result_without_llm() -> None:
    asset_bundle = {
        "title_candidates": [{"t": 1}],
        "body_draft": "正文" * 50,
    }
    with patch(
        "apps.content_planning.agents.judge_agent.llm_router.is_any_available",
        return_value=False,
    ):
        result = JudgeAgent().evaluate(
            asset_bundle,
            plan={"theme": "x"},
            strategy=None,
            opportunity_id="o1",
        )
    assert isinstance(result, JudgeResult)
    assert hasattr(result, "overall_score")
    assert hasattr(result, "plan_consistency")
    assert hasattr(result, "risk_level")
    assert isinstance(result.risks, list)
    assert isinstance(result.dimensions, list)
    assert isinstance(result.recommendation, str)
    assert isinstance(result.actions, list)


def test_agent_memory_recall_and_search_empty(tmp_path) -> None:
    mem = AgentMemory(str(tmp_path / "test_empty.sqlite"))
    assert mem.recall(opportunity_id="nonexistent", category="test") == []
    assert mem.search("nonexistent query") == []


def test_review_loop_completes_with_memory_miss(tmp_path) -> None:
    loop = ReviewLoop(memory=AgentMemory(str(tmp_path / "test_review.sqlite")))
    fb = PerformanceFeedback(
        opportunity_id="ghost-opp",
        asset_id="a1",
        brand_id="b1",
        publish_date="2026-04-11",
        metrics={"views": 10.0, "saves": 1.0},
        performance_tier="average",
        human_notes="",
    )
    result = loop.process_feedback(fb)
    assert result.insights is not None
    assert isinstance(result.memories_stored, int)


def test_action_spec_regenerate_confirmation_default() -> None:
    spec = ActionSpec(action_type="regenerate", target_object="brief", label="test")
    assert spec.confirmation_required is True


def test_legacy_route_patterns_exist_on_router() -> None:
    """Verify V1 endpoints still exist by checking route paths on the router."""
    raw_paths: list[str] = []
    for route in router.routes:
        path = getattr(route, "path", "")
        if path:
            raw_paths.append(path)
    assert any("run-agent" in p for p in raw_paths), f"run-agent not found in {raw_paths[:5]}..."
    assert any("chat" in p and "opportunity_id" in p for p in raw_paths)
    assert any("discuss" in p for p in raw_paths)
    assert any("agent-pipeline" in p for p in raw_paths)
