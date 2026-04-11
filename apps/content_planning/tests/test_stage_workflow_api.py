from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.content_planning.api.routes import _get_flow
from apps.content_planning.schemas.evaluation import DimensionScore, StageEvaluation
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


def _seed_review_store(tmp: Path) -> tuple[XHSReviewStore, XHSOpportunityCard]:
    review_store = XHSReviewStore(tmp / "xhs_review.sqlite")
    card = XHSOpportunityCard(
        opportunity_id="opp_stage_001",
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
        source_note_ids=["note_stage_001"],
        confidence=0.91,
        opportunity_status="promoted",
    )
    cards_json = tmp / "cards.json"
    cards_json.write_text(f"[{card.model_dump_json()}]", encoding="utf-8")
    review_store.sync_cards_from_json(cards_json)
    return review_store, card


@pytest.fixture()
def stage_client() -> TestClient:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        runtime_path = _write_runtime(tmp)
        review_store, _ = _seed_review_store(tmp)
        client = TestClient(
            create_app(
                runtime_path,
                review_store=review_store,
                content_plan_store=ContentPlanStore(tmp / "plan.sqlite"),
            )
        )
        yield client


def test_brief_stage_evaluation_is_persisted(stage_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_evaluate_stage(stage: str, opportunity_id: str, context: dict) -> StageEvaluation:
        score = StageEvaluation(
            opportunity_id=opportunity_id,
            stage="brief",
            dimensions=[
                DimensionScore(name="audience_clarity", name_zh="受众清晰度", score=0.82, weight=1.0, explanation="受众明确"),
                DimensionScore(name="brand_fit", name_zh="品牌适配", score=0.76, weight=1.0, explanation="品牌语气适配"),
            ],
            evaluator="rule",
            explanation="Brief quality looks solid.",
        )
        score.compute_overall()
        return score

    monkeypatch.setattr(
        "apps.content_planning.api.routes.evaluate_stage",
        _fake_evaluate_stage,
        raising=False,
    )

    run_response = stage_client.post("/content-planning/evaluations/brief/opp_stage_001/run")
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["stage"] == "brief"
    assert payload["eval_type"] == "stage_run"

    history_response = stage_client.get("/content-planning/evaluations/opp_stage_001")
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["total"] >= 1
    assert history["items"][0]["eval_type"] == "stage_run"
    assert history["items"][0]["payload"]["stage"] == "brief"


def test_stage_discussion_creates_persisted_brief_proposal(stage_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post("/content-planning/xhs-opportunities/opp_stage_001/generate-brief")

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        round_data = DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="brief",
            topic="让 brief 更聚焦早餐桌布场景",
            participants=["trend_analyst", "brief_synthesizer", "strategy_director"],
            messages=[
                AgentMessage(role="user", content="让 brief 更聚焦早餐桌布场景"),
                AgentMessage(role="agent", agent_role="brief_synthesizer", content="建议强调早餐桌景与防水清洁。"),
            ],
            consensus="建议聚焦早餐餐桌场景，并强化防水好打理的价值表达。",
            proposed_updates={
                "primary_value": "防水好打理，早餐场景更出片",
                "target_scene": ["早餐", "居家餐桌"],
            },
            overall_score=0.88,
            status="concluded",
        )
        return round_data

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    response = stage_client.post(
        "/content-planning/stages/brief/opp_stage_001/discussions",
        json={"question": "让 brief 更聚焦早餐桌布场景"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "brief"
    assert payload["discussion_id"]
    assert payload["proposal_id"]
    assert payload["proposal"]["base_version"] == 1
    assert payload["proposal"]["proposed_updates"]["primary_value"].startswith("防水好打理")
    assert payload.get("session", {}).get("session_id")
    assert payload.get("observability", {}).get("trace_id")

    discussion_detail = stage_client.get(f"/content-planning/discussions/{payload['discussion_id']}")
    assert discussion_detail.status_code == 200
    assert discussion_detail.json()["proposal_id"] == payload["proposal_id"]

    proposal_detail = stage_client.get(f"/content-planning/proposals/{payload['proposal_id']}")
    assert proposal_detail.status_code == 200
    assert proposal_detail.json()["stage"] == "brief"
    assert proposal_detail.json()["base_version"] == 1

    from apps.content_planning.gateway.event_bus import event_bus

    hist_types = {e.event_type for e in event_bus.get_history("opp_stage_001")}
    assert "council_proposal_ready" in hist_types
    assert "council_session_completed" in hist_types


def test_apply_brief_proposal_respects_locks_and_marks_downstream_stale(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post("/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan")
    brief_before = stage_client.get("/content-planning/session/opp_stage_001").json()["brief"]
    original_content_goal = brief_before["content_goal"]

    lock_response = stage_client.post(
        "/content-planning/lock/opp_stage_001",
        json={"object_type": "brief", "field": "content_goal", "locked_by": "tester"},
    )
    assert lock_response.status_code == 200

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="brief",
            topic="更新 brief",
            participants=["brief_synthesizer"],
            messages=[AgentMessage(role="user", content="更新 brief")],
            consensus="更新目标和主价值，但保留锁定字段。",
            proposed_updates={
                "content_goal": "立即转化",
                "primary_value": "早餐桌布更防水、更适合日常拍照",
            },
            overall_score=0.9,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    discuss_response = stage_client.post(
        "/content-planning/stages/brief/opp_stage_001/discussions",
        json={"question": "更新 brief"},
    )
    assert discuss_response.status_code == 200
    proposal_id = discuss_response.json()["proposal_id"]

    apply_response = stage_client.post(
        f"/content-planning/proposals/{proposal_id}/apply",
        json={"selected_fields": ["content_goal", "primary_value"]},
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert "primary_value" in apply_payload["applied_fields"]
    assert "content_goal" in apply_payload["skipped_fields"]

    session = stage_client.get("/content-planning/session/opp_stage_001").json()
    assert session["brief"]["primary_value"] == "早餐桌布更防水、更适合日常拍照"
    assert session["brief"]["content_goal"] == original_content_goal
    assert session["stale_flags"]["strategy"] is True
    assert session["stale_flags"]["plan"] is True


def test_stage_discussion_creates_persisted_strategy_proposal(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post("/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan")

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="strategy",
            topic="让策略更适合早餐场景高收藏种草",
            participants=["strategy_director", "brief_synthesizer", "visual_director"],
            messages=[
                AgentMessage(role="user", content="让策略更适合早餐场景高收藏种草"),
                AgentMessage(role="agent", agent_role="strategy_director", content="建议强化早餐场景的代入感和收藏驱动。"),
            ],
            consensus="策略建议强化早餐场景的高收藏钩子，并减少广告式表达。",
            proposed_updates={
                "new_angle": "早餐桌景的低成本氛围改造",
                "cta_strategy": "引导收藏早餐桌景灵感，而不是直接下单",
                "tone_of_voice": "分享感、灵感感、轻种草",
            },
            overall_score=0.91,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    response = stage_client.post(
        "/content-planning/stages/strategy/opp_stage_001/discussions",
        json={"question": "让策略更适合早餐场景高收藏种草"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "strategy"
    assert payload["proposal_id"]
    assert payload["proposal"]["base_version"] == 1
    assert payload["proposal"]["proposed_updates"]["new_angle"] == "早餐桌景的低成本氛围改造"

    proposal_detail = stage_client.get(f"/content-planning/proposals/{payload['proposal_id']}")
    assert proposal_detail.status_code == 200
    assert proposal_detail.json()["stage"] == "strategy"
    assert proposal_detail.json()["base_version"] == 1


def test_apply_strategy_proposal_respects_locks_and_marks_downstream_stale(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post("/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan")
    session_before = stage_client.get("/content-planning/session/opp_stage_001").json()
    original_tone = session_before["strategy"]["tone_of_voice"]

    lock_response = stage_client.post(
        "/content-planning/lock/opp_stage_001",
        json={"object_type": "strategy", "field": "tone_of_voice", "locked_by": "tester"},
    )
    assert lock_response.status_code == 200

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="strategy",
            topic="更新策略",
            participants=["strategy_director", "visual_director"],
            messages=[AgentMessage(role="user", content="更新策略")],
            consensus="把策略改成更偏收藏驱动，并保留锁定语气字段。",
            proposed_updates={
                "tone_of_voice": "更强转化、更直接下单",
                "new_angle": "早餐桌景灵感收藏 + 防水桌布平替感",
                "risk_notes": ["避免过强促销语气"],
            },
            overall_score=0.9,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    discuss_response = stage_client.post(
        "/content-planning/stages/strategy/opp_stage_001/discussions",
        json={"question": "更新策略"},
    )
    assert discuss_response.status_code == 200
    proposal_id = discuss_response.json()["proposal_id"]

    apply_response = stage_client.post(
        f"/content-planning/proposals/{proposal_id}/apply",
        json={"selected_fields": ["tone_of_voice", "new_angle", "risk_notes"]},
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert "new_angle" in apply_payload["applied_fields"]
    assert "tone_of_voice" in apply_payload["skipped_fields"]

    session = stage_client.get("/content-planning/session/opp_stage_001").json()
    assert session["strategy"]["new_angle"] == "早餐桌景灵感收藏 + 防水桌布平替感"
    assert session["strategy"]["tone_of_voice"] == original_tone
    assert session["strategy"]["strategy_version"] == 2
    assert session["stale_flags"]["strategy"] is False
    assert session["stale_flags"]["plan"] is True
    assert session["stale_flags"]["titles"] is True
    assert session["stale_flags"]["body"] is True
    assert session["stale_flags"]["image_briefs"] is True
    assert session["stale_flags"]["asset_bundle"] is True


def test_apply_strategy_proposal_fails_when_brief_is_stale(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post("/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan")

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="strategy",
            topic="更新策略",
            participants=["strategy_director"],
            messages=[AgentMessage(role="user", content="更新策略")],
            consensus="策略需要调整。",
            proposed_updates={"new_angle": "更偏早餐桌景收藏"},
            overall_score=0.86,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    proposal_id = stage_client.post(
        "/content-planning/stages/strategy/opp_stage_001/discussions",
        json={"question": "更新策略"},
    ).json()["proposal_id"]

    flow = _get_flow()
    session = flow._get_session("opp_stage_001")
    session.stale_flags["brief"] = True
    flow._persist(session, status="generated")

    apply_response = stage_client.post(
        f"/content-planning/proposals/{proposal_id}/apply",
        json={"selected_fields": ["new_angle"]},
    )
    assert apply_response.status_code == 409
    detail = apply_response.json()["detail"]
    assert "brief" in detail["message"].lower()
    assert detail["stale_flags"]["brief"] is True


def test_strategy_evaluation_uses_v2_rubric_and_comparison_skips_legacy_baseline(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_client.post("/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan")

    def _fake_evaluate_stage(stage: str, opportunity_id: str, context: dict) -> StageEvaluation:
        if stage == "strategy":
            score = StageEvaluation(
                opportunity_id=opportunity_id,
                stage="strategy",
                dimensions=[
                    DimensionScore(name="strategic_coherence", name_zh="策略一致性", score=0.82, weight=0.2, explanation="方向一致"),
                    DimensionScore(name="differentiation", name_zh="差异化程度", score=0.8, weight=0.2, explanation="有差异化"),
                    DimensionScore(name="platform_nativeness", name_zh="平台原生度", score=0.78, weight=0.2, explanation="符合小红书语境"),
                    DimensionScore(name="conversion_relevance", name_zh="转化相关性", score=0.75, weight=0.2, explanation="收藏驱动明确"),
                    DimensionScore(name="brand_guardrail_fit", name_zh="品牌守护栏适配", score=0.77, weight=0.2, explanation="品牌调性稳定"),
                ],
                evaluator="rule",
                explanation="Strategy v2 quality looks solid.",
            )
            score.compute_overall()
            return score
        score = StageEvaluation(opportunity_id=opportunity_id, stage=stage, evaluator="rule", explanation=f"{stage} ok")
        score.compute_overall()
        return score

    monkeypatch.setattr(
        "apps.content_planning.api.routes.evaluate_stage",
        _fake_evaluate_stage,
        raising=False,
    )
    monkeypatch.setattr(
        "apps.content_planning.evaluation.comparison.evaluate_stage",
        _fake_evaluate_stage,
        raising=False,
    )

    run_response = stage_client.post("/content-planning/evaluations/strategy/opp_stage_001/run")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["stage"] == "strategy"
    assert run_payload["rubric_version"] == "strategy_v2"
    assert run_payload["run_mode"] == "agent_assisted_council"
    assert [d["name"] for d in run_payload["dimensions"]] == [
        "strategic_coherence",
        "differentiation",
        "platform_nativeness",
        "conversion_relevance",
        "brand_guardrail_fit",
    ]

    flow = _get_flow()
    flow._store.save_evaluation(
        "legacy_baseline_strategy_v1",
        "opp_stage_001",
        "baseline",
        {
            "evaluation_id": "legacy_baseline_strategy_v1",
            "opportunity_id": "opp_stage_001",
            "stage_scores": {
                "strategy": {
                    "evaluation_id": "legacy_strategy_score",
                    "opportunity_id": "opp_stage_001",
                    "stage": "strategy",
                    "dimensions": [
                        {"name": "differentiation", "name_zh": "差异化程度", "score": 0.55, "weight": 0.3, "explanation": "legacy"},
                        {"name": "executability", "name_zh": "可执行性", "score": 0.5, "weight": 0.25, "explanation": "legacy"},
                        {"name": "brief_alignment", "name_zh": "Brief对齐度", "score": 0.48, "weight": 0.25, "explanation": "legacy"},
                        {"name": "creativity", "name_zh": "创意新颖度", "score": 0.52, "weight": 0.2, "explanation": "legacy"},
                    ],
                    "overall_score": 0.52,
                    "evaluator": "rule",
                    "model_used": "",
                    "explanation": "legacy strategy baseline",
                    "rubric_version": "strategy_v1",
                    "run_mode": "baseline_compiler",
                }
            },
            "pipeline_score": 0.52,
            "metrics": {"opportunity_id": "opp_stage_001"},
        },
    )

    compare_response = stage_client.post("/content-planning/compare/opp_stage_001", json={"apply_learning": False})
    assert compare_response.status_code == 200
    report = compare_response.json()
    assert "strategy" not in report["stage_deltas"]
    assert "不兼容" in report["summary"]


def test_stage_discussion_creates_persisted_plan_proposal(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post("/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan")

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="plan",
            topic="把 note plan 调成更适合收藏的早餐桌景脚本",
            participants=["strategy_director", "visual_director", "asset_producer"],
            messages=[
                AgentMessage(role="user", content="把 note plan 调成更适合收藏的早餐桌景脚本"),
                AgentMessage(role="agent", agent_role="strategy_director", content="建议把标题、正文结构和图位都收敛到早餐桌景收藏场景。"),
            ],
            consensus="Plan 建议强化早餐桌景收藏线索，并把标题、正文和图位计划重新对齐。",
            proposed_updates={
                "title_plan.candidate_titles": ["早餐桌景灵感：一块桌布就能拉满氛围感"],
                "body_plan.body_outline": ["先给出早餐桌景前后对比", "再拆防水桌布的日常使用理由"],
                "image_plan.global_notes": "首图强化桌布材质与早餐光线层次，后续图位补充清洁与收纳感。",
            },
            overall_score=0.89,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    response = stage_client.post(
        "/content-planning/stages/plan/opp_stage_001/discussions",
        json={"question": "把 note plan 调成更适合收藏的早餐桌景脚本"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "plan"
    assert payload["proposal_id"]
    assert payload["proposal"]["base_version"] == 1
    assert payload["proposal"]["proposed_updates"]["title_plan.candidate_titles"] == ["早餐桌景灵感：一块桌布就能拉满氛围感"]

    proposal_detail = stage_client.get(f"/content-planning/proposals/{payload['proposal_id']}")
    assert proposal_detail.status_code == 200
    assert proposal_detail.json()["stage"] == "plan"
    assert proposal_detail.json()["base_version"] == 1


def test_apply_plan_proposal_respects_locks_and_marks_generation_stale(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post(
        "/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan",
        json={"with_generation": True},
    )
    session_before = stage_client.get("/content-planning/session/opp_stage_001").json()
    original_outline = session_before["note_plan"]["body_plan"]["body_outline"]

    lock_response = stage_client.post(
        "/content-planning/lock/opp_stage_001",
        json={"object_type": "plan", "field": "body_plan.body_outline", "locked_by": "tester"},
    )
    assert lock_response.status_code == 200

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="plan",
            topic="更新 plan",
            participants=["strategy_director", "asset_producer"],
            messages=[AgentMessage(role="user", content="更新 plan")],
            consensus="保留锁定的正文提纲，更新标题与发布建议。",
            proposed_updates={
                "body_plan.body_outline": ["锁定字段不应被覆盖"],
                "title_plan.candidate_titles": ["早餐桌景显高级，其实只换了一块桌布"],
                "publish_notes": ["优先在早餐自然光场景下出片，首图不要过度摆拍。"],
            },
            overall_score=0.9,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    discuss_response = stage_client.post(
        "/content-planning/stages/plan/opp_stage_001/discussions",
        json={"question": "更新 plan"},
    )
    assert discuss_response.status_code == 200
    proposal_id = discuss_response.json()["proposal_id"]

    apply_response = stage_client.post(
        f"/content-planning/proposals/{proposal_id}/apply",
        json={"selected_fields": ["body_plan.body_outline", "title_plan.candidate_titles", "publish_notes"]},
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert "title_plan.candidate_titles" in apply_payload["applied_fields"]
    assert "publish_notes" in apply_payload["applied_fields"]
    assert "body_plan.body_outline" in apply_payload["skipped_fields"]

    session = stage_client.get("/content-planning/session/opp_stage_001").json()
    assert session["note_plan"]["title_plan"]["candidate_titles"] == ["早餐桌景显高级，其实只换了一块桌布"]
    assert session["note_plan"]["body_plan"]["body_outline"] == original_outline
    assert session["note_plan"]["publish_notes"] == ["优先在早餐自然光场景下出片，首图不要过度摆拍。"]
    assert session["note_plan"]["version"] == 2
    assert session["stale_flags"]["plan"] is False
    assert session["stale_flags"]["titles"] is True
    assert session["stale_flags"]["body"] is True
    assert session["stale_flags"]["image_briefs"] is True
    assert session["stale_flags"]["asset_bundle"] is True


def test_apply_plan_proposal_fails_when_strategy_is_stale(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post("/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan")

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="plan",
            topic="更新 plan",
            participants=["strategy_director"],
            messages=[AgentMessage(role="user", content="更新 plan")],
            consensus="Plan 需要调整。",
            proposed_updates={"title_plan.title_axes": ["早餐氛围改造"]},
            overall_score=0.86,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    proposal_id = stage_client.post(
        "/content-planning/stages/plan/opp_stage_001/discussions",
        json={"question": "更新 plan"},
    ).json()["proposal_id"]

    flow = _get_flow()
    session = flow._get_session("opp_stage_001")
    session.stale_flags["strategy"] = True
    flow._persist(session, status="generated")

    apply_response = stage_client.post(
        f"/content-planning/proposals/{proposal_id}/apply",
        json={"selected_fields": ["title_plan.title_axes"]},
    )
    assert apply_response.status_code == 409
    detail = apply_response.json()["detail"]
    assert "strategy" in detail["message"].lower()
    assert detail["stale_flags"]["strategy"] is True


def test_plan_evaluation_uses_v1_rubric_and_comparison_skips_legacy_baseline(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_client.post("/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan")

    def _fake_evaluate_stage(stage: str, opportunity_id: str, context: dict) -> StageEvaluation:
        if stage == "plan":
            score = StageEvaluation(
                opportunity_id=opportunity_id,
                stage="plan",
                dimensions=[
                    DimensionScore(name="structural_completeness", name_zh="结构完整性", score=0.84, weight=0.2, explanation="标题/正文/图位结构齐全"),
                    DimensionScore(name="title_body_alignment", name_zh="标题正文对齐", score=0.81, weight=0.2, explanation="标题与正文一致"),
                    DimensionScore(name="image_slot_alignment", name_zh="图位对齐", score=0.8, weight=0.2, explanation="图位和叙事一致"),
                    DimensionScore(name="execution_readiness", name_zh="执行就绪度", score=0.79, weight=0.2, explanation="可以进入生成"),
                    DimensionScore(name="human_handoff_readiness", name_zh="交接就绪度", score=0.83, weight=0.2, explanation="便于人工接手"),
                ],
                evaluator="rule",
                explanation="Plan v1 quality looks solid.",
                rubric_version="plan_v1",
            )
            score.compute_overall()
            return score
        if stage == "strategy":
            score = StageEvaluation(
                opportunity_id=opportunity_id,
                stage="strategy",
                dimensions=[DimensionScore(name="strategic_coherence", name_zh="策略一致性", score=0.8, weight=1.0, explanation="ok")],
                evaluator="rule",
                explanation="Strategy ok",
                rubric_version="strategy_v2",
            )
            score.compute_overall()
            return score
        score = StageEvaluation(opportunity_id=opportunity_id, stage=stage, evaluator="rule", explanation=f"{stage} ok")
        score.compute_overall()
        return score

    monkeypatch.setattr(
        "apps.content_planning.api.routes.evaluate_stage",
        _fake_evaluate_stage,
        raising=False,
    )
    monkeypatch.setattr(
        "apps.content_planning.evaluation.comparison.evaluate_stage",
        _fake_evaluate_stage,
        raising=False,
    )

    run_response = stage_client.post("/content-planning/evaluations/plan/opp_stage_001/run")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["stage"] == "plan"
    assert run_payload["rubric_version"] == "plan_v1"
    assert run_payload["run_mode"] == "agent_assisted_council"
    assert [d["name"] for d in run_payload["dimensions"]] == [
        "structural_completeness",
        "title_body_alignment",
        "image_slot_alignment",
        "execution_readiness",
        "human_handoff_readiness",
    ]

    flow = _get_flow()
    flow._store.save_evaluation(
        "legacy_baseline_plan_v0",
        "opp_stage_001",
        "baseline",
        {
            "evaluation_id": "legacy_baseline_plan_v0",
            "opportunity_id": "opp_stage_001",
            "stage_scores": {
                "strategy": {
                    "evaluation_id": "legacy_strategy_score",
                    "opportunity_id": "opp_stage_001",
                    "stage": "strategy",
                    "dimensions": [
                        {"name": "strategic_coherence", "name_zh": "策略一致性", "score": 0.7, "weight": 1.0, "explanation": "legacy"},
                    ],
                    "overall_score": 0.7,
                    "evaluator": "rule",
                    "model_used": "",
                    "explanation": "legacy strategy baseline",
                    "rubric_version": "strategy_v2",
                    "run_mode": "baseline_compiler",
                },
                "plan": {
                    "evaluation_id": "legacy_plan_score",
                    "opportunity_id": "opp_stage_001",
                    "stage": "plan",
                    "dimensions": [
                        {"name": "structural_completeness", "name_zh": "结构完整性", "score": 0.55, "weight": 0.2, "explanation": "legacy"},
                        {"name": "title_body_alignment", "name_zh": "标题正文对齐", "score": 0.5, "weight": 0.2, "explanation": "legacy"},
                        {"name": "image_slot_alignment", "name_zh": "图位对齐", "score": 0.48, "weight": 0.2, "explanation": "legacy"},
                        {"name": "execution_readiness", "name_zh": "执行就绪度", "score": 0.52, "weight": 0.2, "explanation": "legacy"},
                        {"name": "human_handoff_readiness", "name_zh": "交接就绪度", "score": 0.51, "weight": 0.2, "explanation": "legacy"},
                    ],
                    "overall_score": 0.51,
                    "evaluator": "rule",
                    "model_used": "",
                    "explanation": "legacy plan baseline",
                    "rubric_version": "plan_v0",
                    "run_mode": "baseline_compiler",
                },
            },
            "pipeline_score": 0.61,
            "metrics": {"opportunity_id": "opp_stage_001"},
        },
    )

    compare_response = stage_client.post("/content-planning/compare/opp_stage_001", json={"apply_learning": False})
    assert compare_response.status_code == 200
    report = compare_response.json()
    assert "plan" not in report["stage_deltas"]
    assert "不兼容" in report["summary"]


def test_plan_workspace_renders_council_and_scorecard_sections(stage_client: TestClient) -> None:
    response = stage_client.get(
        "/content-planning/plan/opp_stage_001",
        headers={"accept": "text/html"},
    )
    assert response.status_code == 200
    assert "Ask the Council" in response.text
    assert "Baseline vs Current Scorecard" in response.text


def test_stage_discussion_creates_persisted_asset_proposal(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post(
        "/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan",
        json={"with_generation": True},
    )
    stage_client.get("/content-planning/asset-bundle/opp_stage_001")

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="asset",
            topic="把资产包调得更适合早餐桌景高收藏发布",
            participants=["asset_producer", "visual_director", "strategy_director"],
            messages=[
                AgentMessage(role="user", content="把资产包调得更适合早餐桌景高收藏发布"),
                AgentMessage(role="agent", agent_role="asset_producer", content="建议把标题、正文和图位 brief 同时收敛到早餐桌景收藏导向。"),
            ],
            consensus="Asset 建议强化收藏导向的标题、正文草稿与图位执行说明，并保留早餐自然光场景。",
            proposed_updates={
                "title_candidates": [
                    {
                        "title_text": "早餐桌景显高级，其实只是换了一块桌布",
                        "axis": "收藏灵感",
                        "rationale": "更像小红书的高收藏标题表达",
                    }
                ],
                "body_draft": "先展示早餐桌景前后氛围差异，再展开防水好打理和出片感的真实使用理由。",
                "image_execution_briefs": [
                    {
                        "slot_index": 1,
                        "role": "封面图",
                        "subject": "早餐桌布与餐具组合",
                        "composition": "俯拍突出桌布纹理",
                        "color_mood": "奶油暖光",
                    }
                ],
            },
            overall_score=0.9,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    response = stage_client.post(
        "/content-planning/stages/asset/opp_stage_001/discussions",
        json={"question": "把资产包调得更适合早餐桌景高收藏发布"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "asset"
    assert payload["proposal_id"]
    assert payload["proposal"]["base_version"] == 1
    assert payload["proposal"]["proposed_updates"]["title_candidates"][0]["title_text"].startswith("早餐桌景显高级")

    proposal_detail = stage_client.get(f"/content-planning/proposals/{payload['proposal_id']}")
    assert proposal_detail.status_code == 200
    assert proposal_detail.json()["stage"] == "asset"
    assert proposal_detail.json()["base_version"] == 1


def test_apply_asset_proposal_respects_locks_and_keeps_upstream_fresh(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post(
        "/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan",
        json={"with_generation": True},
    )
    stage_client.get("/content-planning/asset-bundle/opp_stage_001")
    session_before = stage_client.get("/content-planning/session/opp_stage_001").json()
    original_body_draft = session_before["asset_bundle"]["body_draft"]

    lock_response = stage_client.post(
        "/content-planning/lock/opp_stage_001",
        json={"object_type": "asset_bundle", "field": "body_draft", "locked_by": "tester"},
    )
    assert lock_response.status_code == 200

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="asset",
            topic="更新资产包",
            participants=["asset_producer", "visual_director"],
            messages=[AgentMessage(role="user", content="更新资产包")],
            consensus="保留锁定的正文草稿，更新标题候选与图片执行说明。",
            proposed_updates={
                "body_draft": "这段正文不应该覆盖锁定字段。",
                "title_candidates": [
                    {
                        "title_text": "早餐桌景想显高级，先把桌布换对",
                        "axis": "封面钩子",
                        "rationale": "更适合首页点击",
                    }
                ],
                "image_execution_briefs": [
                    {
                        "slot_index": 1,
                        "role": "封面图",
                        "subject": "早餐桌景和桌布纹理",
                        "composition": "45 度俯拍突出桌布和餐具层次",
                        "color_mood": "早餐暖光",
                    }
                ],
            },
            overall_score=0.91,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    proposal_id = stage_client.post(
        "/content-planning/stages/asset/opp_stage_001/discussions",
        json={"question": "更新资产包"},
    ).json()["proposal_id"]

    apply_response = stage_client.post(
        f"/content-planning/proposals/{proposal_id}/apply",
        json={"selected_fields": ["body_draft", "title_candidates", "image_execution_briefs"]},
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert "title_candidates" in apply_payload["applied_fields"]
    assert "image_execution_briefs" in apply_payload["applied_fields"]
    assert "body_draft" in apply_payload["skipped_fields"]

    session = stage_client.get("/content-planning/session/opp_stage_001").json()
    assert session["asset_bundle"]["title_candidates"][0]["title_text"] == "早餐桌景想显高级，先把桌布换对"
    assert session["asset_bundle"]["body_draft"] == original_body_draft
    assert session["asset_bundle"]["version"] == 2
    assert session["stale_flags"]["brief"] is False
    assert session["stale_flags"]["strategy"] is False
    assert session["stale_flags"]["plan"] is False
    assert session["stale_flags"]["titles"] is False
    assert session["stale_flags"]["body"] is False
    assert session["stale_flags"]["image_briefs"] is False
    assert session["stale_flags"]["asset_bundle"] is False


def test_apply_asset_proposal_fails_when_generation_inputs_are_stale(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.content_planning.agents.base import AgentMessage
    from apps.content_planning.agents.discussion import DiscussionRound

    stage_client.post(
        "/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan",
        json={"with_generation": True},
    )
    stage_client.get("/content-planning/asset-bundle/opp_stage_001")

    def _fake_discuss(*args, **kwargs) -> DiscussionRound:
        return DiscussionRound(
            opportunity_id="opp_stage_001",
            stage="asset",
            topic="更新资产包",
            participants=["asset_producer"],
            messages=[AgentMessage(role="user", content="更新资产包")],
            consensus="Asset 需要调整。",
            proposed_updates={"title_candidates": [{"title_text": "新的封面标题", "axis": "钩子"}]},
            overall_score=0.84,
            status="concluded",
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    proposal_id = stage_client.post(
        "/content-planning/stages/asset/opp_stage_001/discussions",
        json={"question": "更新资产包"},
    ).json()["proposal_id"]

    flow = _get_flow()
    session = flow._get_session("opp_stage_001")
    session.stale_flags["titles"] = True
    flow._persist(session, status="generated")

    apply_response = stage_client.post(
        f"/content-planning/proposals/{proposal_id}/apply",
        json={"selected_fields": ["title_candidates"]},
    )
    assert apply_response.status_code == 409
    detail = apply_response.json()["detail"]
    assert "stale" in detail["message"].lower()
    assert detail["stale_flags"]["titles"] is True


def test_asset_evaluation_uses_v1_rubric_and_comparison_skips_legacy_baseline(
    stage_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_client.post(
        "/content-planning/xhs-opportunities/opp_stage_001/generate-note-plan",
        json={"with_generation": True},
    )
    stage_client.get("/content-planning/asset-bundle/opp_stage_001")

    def _fake_evaluate_stage(stage: str, opportunity_id: str, context: dict) -> StageEvaluation:
        if stage == "asset":
            score = StageEvaluation(
                opportunity_id=opportunity_id,
                stage="asset",
                dimensions=[
                    DimensionScore(name="headline_quality", name_zh="标题质量", score=0.83, weight=0.2, explanation="标题更像小红书首页表达"),
                    DimensionScore(name="body_persuasiveness", name_zh="正文说服力", score=0.8, weight=0.2, explanation="正文保留种草说服力"),
                    DimensionScore(name="visual_instruction_specificity", name_zh="视觉指令具体度", score=0.79, weight=0.2, explanation="图位说明具体"),
                    DimensionScore(name="brand_compliance", name_zh="品牌合规度", score=0.82, weight=0.2, explanation="品牌表达稳定"),
                    DimensionScore(name="production_readiness", name_zh="生产就绪度", score=0.85, weight=0.2, explanation="可直接进入交付"),
                ],
                evaluator="rule",
                explanation="Asset v1 quality looks solid.",
                rubric_version="asset_v1",
            )
            score.compute_overall()
            return score
        if stage == "plan":
            score = StageEvaluation(
                opportunity_id=opportunity_id,
                stage="plan",
                dimensions=[DimensionScore(name="structural_completeness", name_zh="结构完整性", score=0.8, weight=1.0, explanation="ok")],
                evaluator="rule",
                explanation="Plan ok",
                rubric_version="plan_v1",
            )
            score.compute_overall()
            return score
        if stage == "strategy":
            score = StageEvaluation(
                opportunity_id=opportunity_id,
                stage="strategy",
                dimensions=[DimensionScore(name="strategic_coherence", name_zh="策略一致性", score=0.8, weight=1.0, explanation="ok")],
                evaluator="rule",
                explanation="Strategy ok",
                rubric_version="strategy_v2",
            )
            score.compute_overall()
            return score
        score = StageEvaluation(opportunity_id=opportunity_id, stage=stage, evaluator="rule", explanation=f"{stage} ok")
        score.compute_overall()
        return score

    monkeypatch.setattr(
        "apps.content_planning.api.routes.evaluate_stage",
        _fake_evaluate_stage,
        raising=False,
    )
    monkeypatch.setattr(
        "apps.content_planning.evaluation.comparison.evaluate_stage",
        _fake_evaluate_stage,
        raising=False,
    )

    run_response = stage_client.post("/content-planning/evaluations/asset/opp_stage_001/run")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["stage"] == "asset"
    assert run_payload["rubric_version"] == "asset_v1"
    assert run_payload["run_mode"] == "agent_assisted_council"
    assert [d["name"] for d in run_payload["dimensions"]] == [
        "headline_quality",
        "body_persuasiveness",
        "visual_instruction_specificity",
        "brand_compliance",
        "production_readiness",
    ]

    flow = _get_flow()
    flow._store.save_evaluation(
        "legacy_baseline_content_v1",
        "opp_stage_001",
        "baseline",
        {
            "evaluation_id": "legacy_baseline_content_v1",
            "opportunity_id": "opp_stage_001",
            "stage_scores": {
                "strategy": {
                    "evaluation_id": "legacy_strategy_score",
                    "opportunity_id": "opp_stage_001",
                    "stage": "strategy",
                    "dimensions": [{"name": "strategic_coherence", "name_zh": "策略一致性", "score": 0.7, "weight": 1.0, "explanation": "legacy"}],
                    "overall_score": 0.7,
                    "evaluator": "rule",
                    "model_used": "",
                    "explanation": "legacy strategy baseline",
                    "rubric_version": "strategy_v2",
                    "run_mode": "baseline_compiler",
                },
                "plan": {
                    "evaluation_id": "legacy_plan_score",
                    "opportunity_id": "opp_stage_001",
                    "stage": "plan",
                    "dimensions": [{"name": "structural_completeness", "name_zh": "结构完整性", "score": 0.7, "weight": 1.0, "explanation": "legacy"}],
                    "overall_score": 0.7,
                    "evaluator": "rule",
                    "model_used": "",
                    "explanation": "legacy plan baseline",
                    "rubric_version": "plan_v1",
                    "run_mode": "baseline_compiler",
                },
                "asset": {
                    "evaluation_id": "legacy_asset_score",
                    "opportunity_id": "opp_stage_001",
                    "stage": "asset",
                    "dimensions": [
                        {"name": "title_appeal", "name_zh": "标题吸引力", "score": 0.55, "weight": 0.25, "explanation": "legacy"},
                        {"name": "body_structure", "name_zh": "正文结构性", "score": 0.54, "weight": 0.25, "explanation": "legacy"},
                        {"name": "image_brief_quality", "name_zh": "图片Brief可执行度", "score": 0.52, "weight": 0.25, "explanation": "legacy"},
                        {"name": "overall_coherence", "name_zh": "整体一致性", "score": 0.5, "weight": 0.25, "explanation": "legacy"},
                    ],
                    "overall_score": 0.53,
                    "evaluator": "rule",
                    "model_used": "",
                    "explanation": "legacy asset baseline",
                    "rubric_version": "content_v1",
                    "run_mode": "baseline_compiler",
                },
            },
            "pipeline_score": 0.64,
            "metrics": {"opportunity_id": "opp_stage_001"},
        },
    )

    compare_response = stage_client.post("/content-planning/compare/opp_stage_001", json={"apply_learning": False})
    assert compare_response.status_code == 200
    report = compare_response.json()
    assert "asset" not in report["stage_deltas"]
    assert "不兼容" in report["summary"]


def test_asset_workspace_renders_council_and_scorecard_sections(stage_client: TestClient) -> None:
    response = stage_client.get(
        "/content-planning/assets/opp_stage_001",
        headers={"accept": "text/html"},
    )
    assert response.status_code == 200
    assert "Council" in response.text
    assert "Baseline vs Current Scorecard" in response.text
