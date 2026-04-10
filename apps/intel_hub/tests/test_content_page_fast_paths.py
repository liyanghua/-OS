from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from apps.content_planning.api.routes import _get_flow
from apps.content_planning.storage.plan_store import ContentPlanStore
from apps.intel_hub.api.app import create_app
from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
from apps.intel_hub.storage.xhs_review_store import XHSReviewStore


def _write_runtime(tmp: Path) -> Path:
    runtime_path = tmp / "runtime.yaml"
    runtime_path.write_text(
        "\n".join(
            [
                f"trendradar_output_dir: {(tmp / 'empty-output').as_posix()}",
                f"storage_path: {(tmp / 'intel_hub.sqlite').as_posix()}",
                "default_page_size: 20",
                "fixture_fallback_dir: ''",
            ]
        ),
        encoding="utf-8",
    )
    (tmp / "empty-output").mkdir(parents=True, exist_ok=True)
    return runtime_path


def _seed_review_store(tmp: Path) -> XHSReviewStore:
    review_store = XHSReviewStore(tmp / "xhs_review.sqlite")
    card = XHSOpportunityCard(
        opportunity_id="opp_perf_page_001",
        title="桌布早餐场景机会卡",
        summary="法式奶油风桌布在早餐场景里兼具氛围感和实用性。",
        opportunity_type="visual",
        scene_refs=["早餐", "餐桌"],
        style_refs=["奶油风", "法式"],
        need_refs=["提升餐桌颜值"],
        visual_pattern_refs=["暖光", "出片"],
        audience_refs=["精致宝妈"],
        value_proposition_refs=["氛围感强", "好打理"],
        evidence_refs=[XHSEvidenceRef(snippet="这块桌布防水又出片，早餐拍照很稳。")],
        source_note_ids=["note_stage_perf_page_001"],
        confidence=0.91,
        opportunity_status="promoted",
    )
    cards_json = tmp / "cards.json"
    cards_json.write_text(f"[{card.model_dump_json()}]", encoding="utf-8")
    review_store.sync_cards_from_json(cards_json)
    return review_store


def test_content_pages_expose_render_timing_headers() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        runtime_path = _write_runtime(tmp)
        review_store = _seed_review_store(tmp)
        client = TestClient(
            create_app(
                runtime_path,
                review_store=review_store,
                content_plan_store=ContentPlanStore(tmp / "plan.sqlite"),
            )
        )

        client.post("/content-planning/xhs-opportunities/opp_perf_page_001/generate-note-plan")

        for path in (
            "/content-planning/brief/opp_perf_page_001",
            "/content-planning/strategy/opp_perf_page_001",
            "/content-planning/plan/opp_perf_page_001",
            "/content-planning/assets/opp_perf_page_001",
        ):
            response = client.get(path, headers={"accept": "text/html"})
            assert response.status_code == 200
            assert "X-Render-Timing-Ms" in response.headers
            assert int(response.headers["X-Render-Timing-Ms"]) >= 0


def test_brief_page_uses_session_snapshot_when_available(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        runtime_path = _write_runtime(tmp)
        review_store = _seed_review_store(tmp)
        client = TestClient(
            create_app(
                runtime_path,
                review_store=review_store,
                content_plan_store=ContentPlanStore(tmp / "plan.sqlite"),
            )
        )

        client.post("/content-planning/xhs-opportunities/opp_perf_page_001/generate-note-plan")
        flow = _get_flow()
        session_data = flow.get_session_data("opp_perf_page_001")
        expected_target_user = session_data["brief"]["target_user"][0]
        calls = {"build_brief": 0}

        def _boom(opportunity_id: str):
            calls["build_brief"] += 1
            raise AssertionError("build_brief should not run on plain GET")

        monkeypatch.setattr(flow, "build_brief", _boom)

        response = client.get("/content-planning/brief/opp_perf_page_001", headers={"accept": "text/html"})

        assert response.status_code == 200
        assert calls["build_brief"] == 0
        assert expected_target_user in response.text


def test_strategy_page_does_not_call_build_note_plan_on_plain_get(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        runtime_path = _write_runtime(tmp)
        review_store = _seed_review_store(tmp)
        client = TestClient(
            create_app(
                runtime_path,
                review_store=review_store,
                content_plan_store=ContentPlanStore(tmp / "plan.sqlite"),
            )
        )

        client.post("/content-planning/xhs-opportunities/opp_perf_page_001/generate-note-plan")
        flow = _get_flow()
        session_data = flow.get_session_data("opp_perf_page_001")
        expected_hook = session_data["strategy"]["new_hook"]
        calls = {"build_note_plan": 0}

        def _boom(opportunity_id: str, *, with_generation: bool = False, preferred_template_id: str | None = None):
            calls["build_note_plan"] += 1
            raise AssertionError("build_note_plan should not run on plain strategy GET")

        monkeypatch.setattr(flow, "build_note_plan", _boom)

        response = client.get("/content-planning/strategy/opp_perf_page_001", headers={"accept": "text/html"})

        assert response.status_code == 200
        assert calls["build_note_plan"] == 0
        assert expected_hook in response.text


def test_plan_page_does_not_generate_assets_on_plain_get(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        runtime_path = _write_runtime(tmp)
        review_store = _seed_review_store(tmp)
        client = TestClient(
            create_app(
                runtime_path,
                review_store=review_store,
                content_plan_store=ContentPlanStore(tmp / "plan.sqlite"),
            )
        )

        client.post("/content-planning/xhs-opportunities/opp_perf_page_001/generate-note-plan")
        flow = _get_flow()
        session_data = flow.get_session_data("opp_perf_page_001")
        expected_goal = session_data["note_plan"]["note_goal"]
        calls = {"build_note_plan": 0}

        def _boom(opportunity_id: str, *, with_generation: bool = False, preferred_template_id: str | None = None):
            calls["build_note_plan"] += 1
            raise AssertionError("build_note_plan should not run on plain plan GET")

        monkeypatch.setattr(flow, "build_note_plan", _boom)

        response = client.get("/content-planning/plan/opp_perf_page_001", headers={"accept": "text/html"})

        assert response.status_code == 200
        assert calls["build_note_plan"] == 0
        assert expected_goal in response.text


def test_content_planning_templates_use_deferred_secondary_fetches() -> None:
    """Chunk 7: 侧栏评分 / skills / SSE 等通过 scheduleDeferred 延后，不在内联脚本首屏同步执行。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        runtime_path = _write_runtime(tmp)
        review_store = _seed_review_store(tmp)
        client = TestClient(
            create_app(
                runtime_path,
                review_store=review_store,
                content_plan_store=ContentPlanStore(tmp / "plan.sqlite"),
            )
        )

        client.post("/content-planning/xhs-opportunities/opp_perf_page_001/generate-note-plan")

        for path, needle in (
            ("/content-planning/brief/opp_perf_page_001", "scheduleDeferred"),
            ("/content-planning/strategy/opp_perf_page_001", "scheduleDeferred"),
            ("/content-planning/plan/opp_perf_page_001", "scheduleDeferred"),
            ("/content-planning/assets/opp_perf_page_001", "scheduleDeferred"),
        ):
            response = client.get(path, headers={"accept": "text/html"})
            assert response.status_code == 200
            assert needle in response.text, path

        plan_html = client.get(
            "/content-planning/plan/opp_perf_page_001", headers={"accept": "text/html"}
        ).text
        assert "loadCollab();" not in plan_html
        assert "cw-load-collab" in plan_html

        assets_html = client.get(
            "/content-planning/assets/opp_perf_page_001", headers={"accept": "text/html"}
        ).text
        assert "loadSkillsPanel" in assets_html
        assert "fetch('/content-planning/skills')" in assets_html
