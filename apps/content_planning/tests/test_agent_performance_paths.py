from __future__ import annotations

import importlib
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.content_planning.adapters.llm_router import LLMMessage, LLMResponse, LLMRouter
from apps.content_planning.agents.base import AgentMessage, AgentResult
from apps.content_planning.agents.discussion import DiscussionRound
from apps.content_planning.evaluation.stage_evaluator import evaluate_stage
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
        opportunity_id="opp_perf_001",
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
        source_note_ids=["note_stage_perf_001"],
        confidence=0.91,
        opportunity_status="promoted",
    )
    cards_json = tmp / "cards.json"
    cards_json.write_text(f"[{card.model_dump_json()}]", encoding="utf-8")
    review_store.sync_cards_from_json(cards_json)
    return review_store, card


@pytest.fixture()
def performance_client() -> TestClient:
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


def test_run_agent_exposes_timing_metadata(performance_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run(self, context):
        return AgentResult(
            agent_role="trend_analyst",
            agent_name="趋势分析师",
            explanation="快速分析完成",
            confidence=0.88,
        )

    monkeypatch.setattr(
        "apps.content_planning.agents.trend_analyst.TrendAnalystAgent.run",
        _fake_run,
        raising=True,
    )

    response = performance_client.post(
        "/content-planning/run-agent/opp_perf_001",
        json={"agent_role": "trend_analyst", "extra": {"hint": "快速分析"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("timing_ms"), int)
    assert payload["timing_ms"] >= 0
    assert set(payload.get("timing_breakdown", {}).keys()) >= {"context_ms", "agent_ms", "persist_ms"}


def test_chat_exposes_timing_metadata(performance_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run_turn(self, context, thread):
        return AgentResult(
            agent_role="lead_agent",
            agent_name="总调度",
            explanation="已给出快速回复",
            confidence=0.77,
        )

    monkeypatch.setattr(
        "apps.content_planning.agents.lead_agent.LeadAgent.run_turn",
        _fake_run_turn,
        raising=True,
    )

    response = performance_client.post(
        "/content-planning/chat/opp_perf_001",
        json={"message": "帮我快速看下这个机会值不值得做", "current_stage": "brief"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("timing_ms"), int)
    assert payload["timing_ms"] >= 0
    assert set(payload.get("timing_breakdown", {}).keys()) >= {"context_ms", "agent_ms", "persist_ms"}


def test_stage_discussion_exposes_timing_metadata(performance_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_discuss(self, *args, **kwargs):
        return DiscussionRound(
            opportunity_id="opp_perf_001",
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

    monkeypatch.setattr(
        "apps.content_planning.api.routes.DiscussionOrchestrator.discuss",
        _fake_discuss,
        raising=True,
    )

    response = performance_client.post(
        "/content-planning/stages/brief/opp_perf_001/discussions",
        json={"question": "让 brief 更聚焦早餐桌布场景"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("timing_ms"), int)
    assert payload["timing_ms"] >= 0
    assert set(payload.get("timing_breakdown", {}).keys()) >= {"context_ms", "discussion_ms", "persist_ms"}


def test_run_agent_default_fast_mode_skips_deep_enhancement(
    performance_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_core(self, context):
        return AgentResult(
            agent_role="trend_analyst",
            agent_name="趋势分析师",
            explanation="仅执行核心分析",
            confidence=0.6,
        )

    def _boom(self, context, base_result):
        raise AssertionError("fast mode should skip _enhance_with_llm")

    monkeypatch.setattr(
        "apps.content_planning.agents.trend_analyst.TrendAnalystAgent._run_core",
        _fake_core,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.trend_analyst.TrendAnalystAgent._enhance_with_llm",
        _boom,
        raising=True,
    )

    response = performance_client.post(
        "/content-planning/run-agent/opp_perf_001",
        json={"agent_role": "trend_analyst"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_role"] == "trend_analyst"
    assert "仅执行核心分析" in payload["explanation"]


def test_chat_default_fast_mode_skips_llm_routing(
    performance_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(self, message, stage, context):
        raise AssertionError("fast mode should skip LeadAgent._route_llm")

    def _fake_run(self, context):
        return AgentResult(
            agent_role="brief_synthesizer",
            agent_name="Brief 编译师",
            explanation="快速回复：建议保持早餐桌景定位。",
            confidence=0.72,
        )

    monkeypatch.setattr(
        "apps.content_planning.agents.lead_agent.LeadAgent._route_llm",
        _boom,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.brief_synthesizer.BriefSynthesizerAgent.run",
        _fake_run,
        raising=True,
    )

    response = performance_client.post(
        "/content-planning/chat/opp_perf_001",
        json={"message": "帮我快速看下 brief 方向", "current_stage": "brief"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_role"] == "lead_agent"
    assert "快速回复" in payload["explanation"]


def test_stage_discussion_single_run_mode_reduces_participants(
    performance_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_agent_opinion_structured(self, **kwargs):
        return "建议保持早餐桌景场景，同时避免过强广告感。", {"stance": "neutral", "claim": "保持场景", "agent_name": "", "stage": kwargs.get("stage", "")}

    def _fake_synthesize(self, question, stage, statements, object_context):
        from apps.content_planning.agents.discussion import CouncilSynthesisBundle

        return CouncilSynthesisBundle(
            consensus="综合意见：先优化场景表达。",
            proposed_updates={"primary_value": "早餐桌景更有氛围感"},
            agreements=[],
            disagreements=[],
            open_questions=[],
            recommended_next_steps=[],
            alternatives=[],
        )

    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._get_agent_opinion_structured",
        _fake_agent_opinion_structured,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._synthesize_consensus",
        _fake_synthesize,
        raising=True,
    )

    response = performance_client.post(
        "/content-planning/stages/brief/opp_perf_001/discussions",
        json={
            "question": "给我一个更快的 brief 建议",
            "run_mode": "agent_assisted_single",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["discussion"]["stage"] == "brief"
    assert len(payload["discussion"]["participants"]) == 1


def test_run_agent_builds_context_bundle_once_per_request(
    performance_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_inject_context(self, opportunity_id: str, agent_role: str = "", limit: int = 5) -> str:
        assert opportunity_id == "opp_perf_001"
        return "预计算记忆上下文"

    def _fake_run(self, context):
        bundle = context.extra.get("request_context_bundle")
        assert bundle is not None
        assert bundle["card"] is not None
        assert bundle["source_notes"] == context.source_notes
        assert bundle["review_summary"] == context.review_summary
        assert bundle["memory_context"] == "预计算记忆上下文"
        assert "桌布早餐场景机会卡" in bundle["object_summary"]
        return AgentResult(
            agent_role="trend_analyst",
            agent_name="趋势分析师",
            explanation="读取 request-scoped bundle 成功",
            confidence=0.81,
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.AgentMemory.inject_context",
        _fake_inject_context,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.trend_analyst.TrendAnalystAgent.run",
        _fake_run,
        raising=True,
    )

    response = performance_client.post(
        "/content-planning/run-agent/opp_perf_001",
        json={"agent_role": "trend_analyst", "mode": "deep"},
    )

    assert response.status_code == 200
    assert "读取 request-scoped bundle 成功" in response.json()["explanation"]


def test_chat_deep_mode_reuses_precomputed_deerflow_context(
    performance_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_inject_context(self, opportunity_id: str, agent_role: str = "", limit: int = 5) -> str:
        return "来自 routes 的共享记忆"

    def _boom_recall(self, opportunity_id: str, query: str = "", limit: int = 5) -> str:
        raise AssertionError("deep chat should reuse precomputed memory context")

    def _boom_summary(self, context) -> str:
        raise AssertionError("deep chat should reuse precomputed object summary")

    def _fake_route_with_llm(self, user_message: str, stage: str, **kwargs):
        assert kwargs["memory_context"] == "来自 routes 的共享记忆"
        assert "桌布早餐场景机会卡" in kwargs["object_summary"]
        return {
            "target_agents": ["brief_synthesizer"],
            "reasoning": "brief 阶段优先交给 Brief 编译师",
            "subtasks": [],
        }

    def _fake_run(self, context):
        return AgentResult(
            agent_role="brief_synthesizer",
            agent_name="Brief 编译师",
            explanation="deep chat 已复用预计算上下文",
            confidence=0.74,
        )

    monkeypatch.setattr(
        "apps.content_planning.api.routes.AgentMemory.inject_context",
        _fake_inject_context,
        raising=True,
    )
    from apps.content_planning.adapters.llm_router import llm_router

    monkeypatch.setattr(
        llm_router,
        "is_any_available",
        lambda: True,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.adapters.deerflow_adapter.DeerFlowAdapter.recall_relevant_memory",
        _boom_recall,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.adapters.deerflow_adapter.DeerFlowAdapter.build_object_summary",
        _boom_summary,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.adapters.deerflow_adapter.DeerFlowAdapter.route_with_llm",
        _fake_route_with_llm,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.brief_synthesizer.BriefSynthesizerAgent.run",
        _fake_run,
        raising=True,
    )

    response = performance_client.post(
        "/content-planning/chat/opp_perf_001",
        json={
            "message": "请深入看一下 brief 方向",
            "current_stage": "brief",
            "mode": "deep",
        },
    )

    assert response.status_code == 200
    assert "deep chat 已复用预计算上下文" in response.json()["explanation"]


def test_discussion_reuses_shared_memory_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.content_planning.agents.base import AgentContext
    from apps.content_planning.agents.discussion import DiscussionOrchestrator

    def _boom_memory(self, opportunity_id: str) -> str:
        raise AssertionError("discussion should reuse shared memory context")

    def _boom_object(self, stage: str, context: AgentContext | None) -> str:
        raise AssertionError("discussion should reuse shared object summary")

    def _fake_agent_opinion_structured(self, **kwargs):
        assert kwargs["memory_context"] == "共享记忆"
        assert kwargs["object_context"] == "共享对象摘要"
        return "建议先调整 brief 的主价值表达。", {"stance": "neutral", "claim": "调主价值", "agent_name": "", "stage": ""}

    def _fake_synthesize(self, question, stage, statements, object_context):
        from apps.content_planning.agents.discussion import CouncilSynthesisBundle

        assert object_context == "共享对象摘要"
        return CouncilSynthesisBundle(
            consensus="综合意见：先改价值表达。",
            proposed_updates={"primary_value": "早餐桌景更出片、更好打理"},
            agreements=[],
            disagreements=[],
            open_questions=[],
            recommended_next_steps=[],
            alternatives=[],
        )

    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._get_memory_context",
        _boom_memory,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._build_object_context",
        _boom_object,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._get_agent_opinion_structured",
        _fake_agent_opinion_structured,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._synthesize_consensus",
        _fake_synthesize,
        raising=True,
    )

    context = AgentContext(
        opportunity_id="opp_perf_001",
        extra={
            "request_context_bundle": {
                "memory_context": "共享记忆",
                "object_summary": "共享对象摘要",
            }
        },
    )
    orchestrator = DiscussionOrchestrator()

    discussion = orchestrator.discuss(
        opportunity_id="opp_perf_001",
        stage="brief",
        user_question="帮我看看 brief 该怎么改",
        context=context,
    )

    assert discussion.consensus == "综合意见：先改价值表达。"


def test_discussion_parallelizes_specialist_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.content_planning.agents.discussion import DiscussionOrchestrator

    def _fake_agent_opinion_structured(self, **kwargs):
        time.sleep(0.08)
        return f"{kwargs['agent_role']} 建议", {"stance": "neutral", "claim": "...", "agent_name": "", "stage": ""}

    def _fake_synthesize(self, question, stage, statements, object_context):
        from apps.content_planning.agents.discussion import CouncilSynthesisBundle

        return CouncilSynthesisBundle(
            consensus="综合意见：保留多角度观点。",
            proposed_updates={"primary_value": "x"},
            agreements=[],
            disagreements=[],
            open_questions=[],
            recommended_next_steps=[],
            alternatives=[],
        )

    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._get_agent_opinion_structured",
        _fake_agent_opinion_structured,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._synthesize_consensus",
        _fake_synthesize,
        raising=True,
    )

    orchestrator = DiscussionOrchestrator()
    started = time.perf_counter()
    discussion = orchestrator.discuss(
        opportunity_id="opp_perf_001",
        stage="brief",
        user_question="帮我并行看一下 brief 方向",
    )
    elapsed = time.perf_counter() - started

    assert discussion.consensus == "综合意见：保留多角度观点。"
    assert elapsed < 0.18


def test_discussion_keeps_partial_results_when_one_specialist_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.content_planning.agents.discussion import DiscussionOrchestrator

    def _fake_agent_opinion_structured(self, **kwargs):
        if kwargs["agent_role"] == "brief_synthesizer":
            raise RuntimeError("temporary llm error")
        return f"{kwargs['agent_role']} 成功建议", {"stance": "neutral", "claim": "...", "agent_name": "", "stage": ""}

    def _fake_synthesize(self, question, stage, statements, object_context):
        from apps.content_planning.agents.discussion import CouncilSynthesisBundle

        assert len(statements) == 2
        return CouncilSynthesisBundle(
            consensus="综合意见：先采用成功观点。",
            proposed_updates={"primary_value": "保留成功建议"},
            agreements=[],
            disagreements=[],
            open_questions=[],
            recommended_next_steps=[],
            alternatives=[],
        )

    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._get_agent_opinion_structured",
        _fake_agent_opinion_structured,
        raising=True,
    )
    monkeypatch.setattr(
        "apps.content_planning.agents.discussion.DiscussionOrchestrator._synthesize_consensus",
        _fake_synthesize,
        raising=True,
    )

    discussion = DiscussionOrchestrator().discuss(
        opportunity_id="opp_perf_001",
        stage="brief",
        user_question="一个 specialist 失败时也继续收敛",
    )

    assert discussion.consensus == "综合意见：先采用成功观点。"
    assert discussion.failed_participants == ["brief_synthesizer"]
    failed_messages = [
        message for message in discussion.messages
        if message.agent_role == "brief_synthesizer" and message.metadata.get("status") == "failed"
    ]
    assert len(failed_messages) == 1


def test_llm_timeout_returns_degraded_response_quickly(monkeypatch: pytest.MonkeyPatch) -> None:
    llm_router_module = importlib.import_module("apps.content_planning.adapters.llm_router")

    class SlowProvider:
        name = "slow"

        def is_available(self) -> bool:
            return True

        def chat(self, messages, *, model=None, temperature=0.3, max_tokens=2000):
            time.sleep(0.2)
            return LLMResponse(content="slow result", provider=self.name, model=model or "slow-model")

    monkeypatch.setitem(llm_router_module._PROVIDERS, "slow", SlowProvider())

    router = LLMRouter(default_provider="slow")
    started = time.perf_counter()
    response = router.chat(
        [LLMMessage(role="user", content="请快速返回")],
        provider="slow",
        timeout_seconds=0.05,
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.15
    assert response.content == ""
    assert response.provider == "slow"
    assert response.degraded is True
    assert response.degraded_reason == "timeout"
    assert response.raw.get("degraded") is True


def test_evaluation_falls_back_to_rule_when_llm_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "apps.content_planning.evaluation.stage_evaluator.llm_router.is_any_available",
        lambda: True,
        raising=True,
    )

    def _fake_chat(*args, **kwargs):
        return LLMResponse(
            content="",
            provider="fake",
            model="fake-model",
            degraded=True,
            degraded_reason="timeout",
            raw={"degraded": True, "reason": "timeout"},
        )

    monkeypatch.setattr(
        "apps.content_planning.evaluation.stage_evaluator.llm_router.chat",
        _fake_chat,
        raising=True,
    )

    evaluation = evaluate_stage(
        "brief",
        "opp_perf_001",
        {
            "card": {"title": "桌布早餐场景机会卡", "summary": "早餐桌布场景"},
            "brief": {
                "target_user": ["精致宝妈"],
                "target_scene": ["早餐", "餐桌"],
                "content_goal": "种草收藏",
                "competitive_angle": "防水且出片",
            },
        },
    )

    assert evaluation.evaluator == "rule"
    assert evaluation.model_used == ""
    assert evaluation.overall_score > 0
