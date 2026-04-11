"""L5 Workspace API: V2 content-planning endpoints (TestClient + mocked flow)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.content_planning.api.routes import router, set_flow
from apps.content_planning.services.agent_pipeline_runner import PipelineRun, PipelineStatus

OPP_ID = "test-opp-001"


def _make_session() -> SimpleNamespace:
    """Session 满足 health / inspect / plan-consistency / judge 等端点的最小字段。"""
    return SimpleNamespace(
        brief={
            "target_user": "测试用户",
            "content_goal": "测试目标",
            "primary_value": "核心价值",
            "target_scene": "场景",
            "visual_style_direction": ["风格"],
            "avoid_directions": ["避免"],
            "why_now": "时机",
        },
        strategy={
            "positioning_statement": "定位包含测试目标",
            "tone_of_voice": "专业",
            "new_hook": "钩子",
        },
        note_plan={"theme": "主题"},
        asset_bundle=SimpleNamespace(
            title_candidates=[{"text": "标题含钩子"}],
            body_draft="x" * 120,
        ),
        titles=[{"text": "标题含钩子"}],
        body="正文草稿足够长度用于一致性检查" * 5,
        image_briefs=[{"slot_index": i} for i in range(5)],
    )


@pytest.fixture
def api_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)

    mock_flow = MagicMock()
    mock_flow.get_session_data.return_value = {
        "brief": {"target_user": "test"},
        "strategy": {},
        "note_plan": {},
    }
    mock_flow._get_session.return_value = _make_session()

    mock_adapter = MagicMock()
    mock_adapter.get_card.return_value = SimpleNamespace(source_note_ids=[])
    mock_adapter.get_source_notes.return_value = []
    mock_adapter.get_review_summary.return_value = {"consensus": "已对齐"}
    mock_flow._adapter = mock_adapter

    set_flow(mock_flow)
    client = TestClient(app)
    yield client
    set_flow(None)


def test_health_check_returns_issues_and_score(api_client: TestClient) -> None:
    r = api_client.post(
        f"/content-planning/{OPP_ID}/health-check",
        json={"stage": "brief"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "issues" in data
    assert "score" in data


def test_readiness_returns_score_and_blockers(api_client: TestClient) -> None:
    r = api_client.get(f"/content-planning/{OPP_ID}/readiness")
    assert r.status_code == 200
    data = r.json()
    assert "readiness_score" in data
    assert "blockers" in data


def test_inspect_returns_quality_score_and_actions(api_client: TestClient) -> None:
    r = api_client.post(
        f"/content-planning/{OPP_ID}/inspect",
        json={"object_type": "brief", "object_content": {"note": "x"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert "quality_score" in data
    assert "actions" in data


def test_plan_consistency_returns_is_consistent(api_client: TestClient) -> None:
    r = api_client.post(
        f"/content-planning/{OPP_ID}/plan-consistency",
        json={},
    )
    assert r.status_code == 200
    data = r.json()
    assert "is_consistent" in data


def test_judge_returns_200(api_client: TestClient) -> None:
    r = api_client.post(
        f"/content-planning/{OPP_ID}/judge",
        json={"variants": []},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("mode") in ("evaluate", "comparison")


def test_review_feedback_returns_insights(api_client: TestClient) -> None:
    r = api_client.post(
        f"/content-planning/{OPP_ID}/review-feedback",
        json={
            "asset_id": "a1",
            "brand_id": "b1",
            "metrics": {"views": 100.0},
            "performance_tier": "average",
            "human_notes": "",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "insights" in data


def test_strategy_block_analyze_returns_200(api_client: TestClient) -> None:
    """路由使用扁平字段 + action=analyze（非嵌套 block / mode）。"""
    r = api_client.post(
        f"/content-planning/{OPP_ID}/strategy-block",
        json={
            "action": "analyze",
            "block_name": "tone",
            "block_type": "tone",
            "content": "test",
        },
    )
    assert r.status_code == 200


@patch("apps.content_planning.api.routes._get_pipeline_runner")
def test_agent_pipeline_rerun_returns_200(
    mock_get_runner: MagicMock,
    api_client: TestClient,
) -> None:
    mock_runner = MagicMock()
    run = PipelineRun(
        run_id="run-test",
        opportunity_id=OPP_ID,
        graph_id="g1",
        status=PipelineStatus.PENDING,
    )
    mock_runner.rerun_from_node = AsyncMock(return_value=run)
    mock_get_runner.return_value = mock_runner

    r = api_client.post(
        f"/content-planning/{OPP_ID}/agent-pipeline/rerun",
        json={"node_id": "brief_gen"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data
    assert data.get("rerun_from") == "brief_gen"
