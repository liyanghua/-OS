"""content_planning API 路由 v2。

原子 API + 编排 API + Brief 编辑 + 局部重生成。
主路径前缀：/content-planning/...
兼容路径（与验收文档 A3 一致）：/xhs-opportunities/...（无前缀，见 router_alias）
"""

from __future__ import annotations

import time
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.content_planning.agents.base import AgentContext, AgentMessage, AgentResult, AgentThread, RequestContextBundle
from apps.content_planning.agents.discussion import DiscussionOrchestrator, DiscussionRound
from apps.content_planning.agents.memory import AgentMemory, MemoryEntry
from apps.content_planning.agents.plan_graph import PlanGraph, build_default_graph
from apps.content_planning.agents.skill_registry import SkillDefinition, skill_registry
from apps.content_planning.evaluation.pipeline_metrics import compute_pipeline_metrics
from apps.content_planning.evaluation.stage_evaluator import evaluate_stage
from apps.content_planning.exceptions import OpportunityNotPromotedError, StageApplyConflictError
from apps.content_planning.gateway.event_bus import event_bus, ObjectEvent
from apps.content_planning.gateway.session_manager import session_manager
from apps.content_planning.schemas.agent_workflow import (
    AgentDiscussionRecord,
    AgentRun,
    AgentSessionRef,
    AgentTask,
    ProposalDecision,
    ProposalDiff,
    ProposalFieldChange,
    StageProposal,
    StageScorecard,
)
from apps.content_planning.schemas.evaluation import PipelineEvaluation, StageEvaluation
from apps.content_planning.services.opportunity_to_plan_flow import OpportunityToPlanFlow

router = APIRouter(prefix="/content-planning", tags=["content_planning"])
router_alias = APIRouter(tags=["content_planning"])

_flow: OpportunityToPlanFlow | None = None
_agent_threads: dict[str, AgentThread] = {}
_STAGE_OBJECT_TYPES: dict[str, str] = {
    "brief": "brief",
    "strategy": "strategy",
    "plan": "plan",
    "asset": "asset_bundle",
}


def _get_flow() -> OpportunityToPlanFlow:
    global _flow
    if _flow is None:
        _flow = OpportunityToPlanFlow()
    return _flow


def set_flow(flow: OpportunityToPlanFlow) -> None:
    """允许外部注入（如 app.py 共享 adapter/store）。"""
    global _flow
    _flow = flow


def _normalize_stage(stage: str) -> Literal["brief", "strategy", "plan", "asset"]:
    value = (stage or "").strip().lower()
    aliases = {
        "brief": "brief",
        "strategy": "strategy",
        "plan": "plan",
        "asset": "asset",
        "assets": "asset",
        "content": "asset",
    }
    normalized = aliases.get(value)
    if normalized is None:
        raise HTTPException(status_code=400, detail=f"Unsupported stage: {stage}")
    return cast(Literal["brief", "strategy", "plan", "asset"], normalized)


def _public_to_eval_stage(stage: str) -> str:
    mapping = {
        "brief": "brief",
        "strategy": "strategy",
        "plan": "plan",
        "asset": "asset",
    }
    return mapping[stage]


def _timing_payload(total_start: float, **parts_ms: int) -> dict[str, Any]:
    return {
        "timing_ms": int((time.perf_counter() - total_start) * 1000),
        "timing_breakdown": parts_ms,
    }


def _load_session_template(flow: OpportunityToPlanFlow, session: Any) -> Any | None:
    if session.match_result and session.match_result.primary_template:
        return flow._retriever.get_template(session.match_result.primary_template.template_id)
    return None


def _build_object_summary(session: Any, card: Any | None) -> str:
    parts: list[str] = []
    if card is not None:
        title = getattr(card, "title", "") or getattr(card, "summary", "")
        if title:
            parts.append(f"Opportunity: {title}")
    if getattr(session, "brief", None):
        brief = session.brief
        brief_title = getattr(brief, "opportunity_title", "") or ""
        if brief_title:
            parts.append(f"Brief: {brief_title}")
        else:
            parts.append("Brief: 已生成")
    if getattr(session, "strategy", None):
        parts.append("Strategy: 已生成")
    if getattr(session, "note_plan", None):
        parts.append("Plan: 已生成")
    if getattr(session, "asset_bundle", None):
        parts.append("AssetBundle: 已组装")
    return "；".join(parts) if parts else "暂无对象"


def _build_request_context_bundle(
    flow: OpportunityToPlanFlow,
    opportunity_id: str,
    session: Any,
    *,
    include_deep_context: bool,
) -> RequestContextBundle:
    card = flow._adapter.get_card(opportunity_id)
    source_notes = flow._adapter.get_source_notes(card.source_note_ids) if card else []
    review_summary_raw = flow._adapter.get_review_summary(opportunity_id) if card else {}
    review_summary = review_summary_raw if isinstance(review_summary_raw, dict) else {}
    template = _load_session_template(flow, session)
    memory_context = ""
    if include_deep_context:
        memory_context = AgentMemory().inject_context(opportunity_id, limit=5)
    return RequestContextBundle(
        card=card,
        source_notes=source_notes,
        review_summary=review_summary,
        template=template,
        memory_context=memory_context,
        object_summary=_build_object_summary(session, card),
    )


def _build_agent_context_from_bundle(
    opportunity_id: str,
    session: Any,
    bundle: RequestContextBundle,
    *,
    extra: dict[str, Any] | None = None,
) -> AgentContext:
    payload_extra = dict(extra or {})
    payload_extra.setdefault("card", bundle.card)
    payload_extra.setdefault("request_context_bundle", bundle.model_dump())
    return AgentContext(
        opportunity_id=opportunity_id,
        brief=session.brief,
        strategy=session.strategy,
        plan=session.note_plan,
        match_result=session.match_result,
        template=bundle.template,
        titles=session.titles,
        body=session.body,
        image_briefs=session.image_briefs,
        asset_bundle=session.asset_bundle,
        source_notes=bundle.source_notes,
        review_summary=bundle.review_summary,
        extra=payload_extra,
    )


# ── Request Models ────────────────────────────────────────────

class GeneratePlanRequest(BaseModel):
    with_generation: bool = False
    preferred_template_id: str | None = None
    mode: Literal["plan_only", "full"] = "plan_only"


class GenerateStrategyRequest(BaseModel):
    template_id: str | None = None
    tone_hint: str | None = None


class BriefUpdateRequest(BaseModel):
    target_user: list[str] | None = None
    target_scene: list[str] | None = None
    content_goal: str | None = None
    primary_value: str | None = None
    visual_style_direction: list[str] | None = None
    avoid_directions: list[str] | None = None
    template_hints: list[str] | None = None
    core_motive: str | None = None
    price_positioning: str | None = None
    target_audience: str | None = None
    why_worth_doing: str | None = None
    competitive_angle: str | None = None


class ApprovalActionRequest(BaseModel):
    object_type: Literal["brief", "strategy", "plan", "asset_bundle"]
    decision: Literal["pending_review", "approved", "changes_requested", "rejected"]
    notes: str = ""


class RunAgentRequest(BaseModel):
    agent_role: str  # trend_analyst / brief_synthesizer / template_planner / strategy_director / visual_director / asset_producer
    mode: Literal["fast", "deep"] = "fast"
    extra: dict[str, Any] = Field(default_factory=dict)


class ChatMessageRequest(BaseModel):
    message: str
    role: str = "human"
    sender_name: str = ""
    current_stage: str = ""
    mode: Literal["fast", "deep"] = "fast"


class StageDiscussionRequest(BaseModel):
    question: str
    run_mode: Literal["agent_assisted_single", "agent_assisted_council"] = "agent_assisted_council"


class ApplyProposalRequest(BaseModel):
    selected_fields: list[str] = Field(default_factory=list)
    actor_user_id: str = ""
    notes: str = ""


class RejectProposalRequest(BaseModel):
    actor_user_id: str = ""
    notes: str = ""


# ── Error Handling ────────────────────────────────────────────

def _handle_flow_error(fn):
    """统一 flow 层异常到 HTTP 状态码。"""
    from functools import wraps

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except OpportunityNotPromotedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except StageApplyConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": exc.message,
                    "stage": exc.stage,
                    "stale_flags": exc.stale_flags,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return wrapper


def _resolve_with_generation(body: GeneratePlanRequest) -> bool:
    return body.with_generation or body.mode == "full"


def _maybe_bind_workspace_context(flow: OpportunityToPlanFlow, request: Request, opportunity_id: str) -> None:
    workspace_id = request.headers.get("x-workspace-id", "")
    if not workspace_id:
        return
    user_id = request.headers.get("x-user-id", "")
    api_token = request.headers.get("x-api-token", "")
    brand_id = request.headers.get("x-brand-id") or None
    campaign_id = request.headers.get("x-campaign-id") or None
    try:
        flow.bind_workspace_context(
            opportunity_id=opportunity_id,
            workspace_id=workspace_id,
            user_id=user_id,
            api_token=api_token,
            brand_id=brand_id,
            campaign_id=campaign_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


# ═══════════════════════════════════════════════════════════════
#  原子 API（主前缀 /content-planning/...）
# ═══════════════════════════════════════════════════════════════

@router.post("/xhs-opportunities/{opportunity_id}/generate-brief")
@_handle_flow_error
async def generate_brief(opportunity_id: str, request: Request) -> dict[str, Any]:
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    return flow.build_brief(opportunity_id).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-note-plan")
@_handle_flow_error
async def generate_note_plan(
    opportunity_id: str,
    request: Request,
    body: GeneratePlanRequest | None = None,
) -> dict[str, Any]:
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    if body is None:
        body = GeneratePlanRequest()
    return flow.build_note_plan(
        opportunity_id,
        with_generation=_resolve_with_generation(body),
        preferred_template_id=body.preferred_template_id,
    )


@router.post("/xhs-opportunities/{opportunity_id}/match-templates")
@_handle_flow_error
async def match_templates(opportunity_id: str, request: Request) -> dict[str, Any]:
    """Brief → 模板匹配。"""
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    return flow.match_templates(opportunity_id).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-strategy")
@_handle_flow_error
async def generate_strategy(
    opportunity_id: str,
    request: Request,
    body: GenerateStrategyRequest | None = None,
) -> dict[str, Any]:
    """模板 → RewriteStrategy。"""
    tid = body.template_id if body else None
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    return flow.build_strategy(
        opportunity_id, template_id=tid,
    ).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-titles")
@_handle_flow_error
async def generate_titles(opportunity_id: str, request: Request) -> dict[str, Any]:
    """局部重生成标题。"""
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    return flow.regenerate_titles(opportunity_id).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-body")
@_handle_flow_error
async def generate_body(opportunity_id: str, request: Request) -> dict[str, Any]:
    """局部重生成正文。"""
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    return flow.regenerate_body(opportunity_id).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-image-briefs")
@_handle_flow_error
async def generate_image_briefs(opportunity_id: str, request: Request) -> dict[str, Any]:
    """局部重生成图片执行指令。"""
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    return flow.regenerate_image_briefs(opportunity_id).model_dump(mode="json")


@router.put("/briefs/{opportunity_id}")
@_handle_flow_error
async def update_brief(
    opportunity_id: str,
    request: Request,
    body: BriefUpdateRequest,
) -> dict[str, Any]:
    """人工编辑 Brief（按 opportunity_id 索引）。"""
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    partial = {k: v for k, v in body.model_dump().items() if v is not None}
    return flow.update_brief(opportunity_id, partial).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/compile-note-plan")
@_handle_flow_error
async def compile_note_plan(
    opportunity_id: str,
    request: Request,
    body: GeneratePlanRequest | None = None,
) -> dict[str, Any]:
    """编排型一键全链路。"""
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    if body is None:
        body = GeneratePlanRequest(mode="full")
    return flow.compile_note_plan(
        opportunity_id,
        with_generation=_resolve_with_generation(body),
        preferred_template_id=body.preferred_template_id,
    )


@router.get("/session/{opportunity_id}")
@_handle_flow_error
async def get_session(opportunity_id: str, request: Request) -> dict[str, Any]:
    """获取当前会话缓存。"""
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    return flow.get_session_data(opportunity_id)


@router.get("/strategies/{opportunity_id}")
@_handle_flow_error
async def list_strategies(opportunity_id: str) -> dict[str, Any]:
    """获取某机会卡的所有策略列表。"""
    flow = _get_flow()
    session_data = flow.get_session_data(opportunity_id)
    strategy = session_data.get("strategy")
    if strategy is None:
        return {"strategies": [], "count": 0}
    if isinstance(strategy, list):
        return {"strategies": strategy, "count": len(strategy)}
    if isinstance(strategy, dict):
        return {"strategies": [strategy], "count": 1}
    return {"strategies": [], "count": 0}


@router.post("/xhs-opportunities/{opportunity_id}/regenerate-image-slot/{slot_index}")
@_handle_flow_error
async def regenerate_image_slot(opportunity_id: str, slot_index: int) -> dict[str, Any]:
    """单张图位重生成。"""
    flow = _get_flow()
    result = flow.regenerate_image_briefs(opportunity_id)
    briefs_data = result.model_dump(mode="json")
    slot_briefs = briefs_data.get("slot_briefs", [])
    target = None
    for sb in slot_briefs:
        if sb.get("slot_index") == slot_index:
            target = sb
            break
    if target is None:
        raise HTTPException(status_code=404, detail=f"图位 {slot_index} 未找到")
    return {"slot_index": slot_index, "slot_brief": target, "total_slots": len(slot_briefs)}


@router.get("/asset-bundle/{opportunity_id}")
@_handle_flow_error
async def get_asset_bundle(opportunity_id: str, request: Request) -> dict[str, Any]:
    """组装并返回 AssetBundle。"""
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    bundle = flow.assemble_asset_bundle(opportunity_id)
    return bundle.model_dump(mode="json")


@router.get("/asset-bundle/{opportunity_id}/export")
@_handle_flow_error
async def export_asset_bundle(opportunity_id: str, request: Request, format: str = "json") -> Any:
    """导出 AssetBundle。format: json / markdown / image_package"""
    from apps.content_planning.services.asset_exporter import AssetExporter

    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    bundle = flow.mark_asset_bundle_exported(opportunity_id)
    exporter = AssetExporter()
    if format == "markdown":
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(exporter.export_markdown(bundle), media_type="text/markdown")
    elif format == "image_package":
        return exporter.export_image_package(bundle)
    return exporter.export_json(bundle)


@router.post("/xhs-opportunities/{opportunity_id}/approve")
@_handle_flow_error
async def approve_content_object(
    opportunity_id: str,
    request: Request,
    body: ApprovalActionRequest,
) -> dict[str, Any]:
    flow = _get_flow()
    workspace_id = request.headers.get("x-workspace-id", "")
    user_id = request.headers.get("x-user-id", "")
    api_token = request.headers.get("x-api-token", "")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="x-workspace-id header is required")
    approval = flow.approve_object(
        opportunity_id=opportunity_id,
        object_type=body.object_type,
        decision=body.decision,
        notes=body.notes,
        workspace_id=workspace_id,
        user_id=user_id,
        api_token=api_token,
    )
    return approval.model_dump(mode="json")


class BatchCompileRequest(BaseModel):
    opportunity_ids: list[str] = Field(min_length=1)


@router.post("/batch-compile")
@_handle_flow_error
async def batch_compile(body: BatchCompileRequest) -> dict[str, Any]:
    """批量编译 promoted 卡。"""
    return _get_flow().batch_compile(body.opportunity_ids)


class CreateCampaignRequest(BaseModel):
    campaign_name: str = ""
    opportunity_ids: list[str] = Field(default_factory=list)
    target_bundle_count: int = 1
    target_variants_per_bundle: int = 1


@router.post("/campaigns")
@_handle_flow_error
async def create_campaign(body: CreateCampaignRequest) -> dict[str, Any]:
    """创建 Campaign 级批量生产计划。"""
    from apps.content_planning.schemas.campaign import CampaignPlan

    plan = CampaignPlan(
        campaign_name=body.campaign_name,
        opportunity_ids=body.opportunity_ids,
        target_bundle_count=body.target_bundle_count,
        target_variants_per_bundle=body.target_variants_per_bundle,
    )
    return plan.model_dump(mode="json")


@router.post("/campaigns/{campaign_id}/execute")
@_handle_flow_error
async def execute_campaign(campaign_id: str) -> dict[str, Any]:
    """执行 Campaign 批量生产（现阶段为概念验证，逐个调用 batch_compile）。"""
    from apps.content_planning.schemas.campaign import CampaignResult

    result = CampaignResult(campaign_id=campaign_id)
    return result.model_dump(mode="json")


@router.get("/dashboard")
async def dashboard_metrics() -> dict[str, Any]:
    """运营看板基础指标。"""
    from apps.content_planning.services.dashboard_metrics import DashboardMetrics

    flow = _get_flow()
    adapter = flow._adapter
    review_store = getattr(adapter, "_review_store", None) or getattr(adapter, "_store", None)
    metrics = DashboardMetrics(
        review_store=review_store,
        plan_store=flow._store,
    )
    return metrics.compute()


class AssetFeedbackRequest(BaseModel):
    published_note_id: str = ""
    like_count: int = 0
    collect_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0
    performance_label: str = "unknown"
    feedback_notes: str = ""


@router.post("/asset-bundle/{asset_bundle_id}/feedback")
async def submit_asset_feedback(
    asset_bundle_id: str,
    body: AssetFeedbackRequest,
) -> dict[str, Any]:
    """提交资产发布效果反馈。"""
    from apps.content_planning.schemas.feedback import PublishedAssetResult

    _Perf = Literal["excellent", "good", "average", "poor", "unknown"]
    allowed: tuple[str, ...] = ("excellent", "good", "average", "poor", "unknown")
    label_raw = body.performance_label if body.performance_label in allowed else "unknown"
    label = cast(_Perf, label_raw)

    result = PublishedAssetResult(
        asset_bundle_id=asset_bundle_id,
        published_note_id=body.published_note_id,
        like_count=body.like_count,
        collect_count=body.collect_count,
        comment_count=body.comment_count,
        share_count=body.share_count,
        view_count=body.view_count,
        performance_label=label,
        feedback_notes=body.feedback_notes,
    )

    return {
        "status": "received",
        "result_id": result.result_id,
        "asset_bundle_id": asset_bundle_id,
        "performance_label": result.performance_label,
    }


@router.post("/run-agent/{opportunity_id}")
@_handle_flow_error
async def run_agent(opportunity_id: str, body: RunAgentRequest) -> dict[str, Any]:
    """运行指定 Agent，返回结果（含解释、置信度、建议 chips）。"""
    from apps.content_planning.agents.asset_producer import AssetProducerAgent
    from apps.content_planning.agents.brief_synthesizer import BriefSynthesizerAgent
    from apps.content_planning.agents.strategy_director import StrategyDirectorAgent
    from apps.content_planning.agents.template_planner import TemplatePlannerAgent
    from apps.content_planning.agents.trend_analyst import TrendAnalystAgent
    from apps.content_planning.agents.visual_director import VisualDirectorAgent

    agent_map = {
        "trend_analyst": TrendAnalystAgent,
        "brief_synthesizer": BriefSynthesizerAgent,
        "template_planner": TemplatePlannerAgent,
        "strategy_director": StrategyDirectorAgent,
        "visual_director": VisualDirectorAgent,
        "asset_producer": AssetProducerAgent,
    }
    agent_cls = agent_map.get(body.agent_role)
    if agent_cls is None:
        raise HTTPException(status_code=400, detail=f"未知 Agent: {body.agent_role}")

    total_t0 = time.perf_counter()

    context_t0 = time.perf_counter()
    flow = _get_flow()
    session = flow._get_session(opportunity_id)
    bundle = _build_request_context_bundle(
        flow,
        opportunity_id,
        session,
        include_deep_context=body.mode == "deep",
    )
    ctx = _build_agent_context_from_bundle(
        opportunity_id,
        session,
        bundle,
        extra={**body.extra, "mode": body.mode},
    )
    context_ms = int((time.perf_counter() - context_t0) * 1000)

    agent_t0 = time.perf_counter()
    agent = agent_cls()
    result = agent.run(ctx)
    agent_ms = int((time.perf_counter() - agent_t0) * 1000)

    result_dict = result.model_dump(mode="json")

    persist_t0 = time.perf_counter()
    _log_agent_action(flow, opportunity_id, result)

    event_bus.publish_sync(ObjectEvent(
        event_type="agent_result",
        opportunity_id=opportunity_id,
        object_type="agent_result",
        object_id=result.result_id,
        agent_role=result.agent_role,
        agent_name=result.agent_name,
        payload={"explanation": result.explanation, "confidence": result.confidence},
    ))
    session_manager.add_message(
        opportunity_id,
        role=f"agent_{result.agent_role}",
        content=result.explanation,
        sender_name=result.agent_name,
        confidence=result.confidence,
    )
    persist_ms = int((time.perf_counter() - persist_t0) * 1000)

    result_dict.update(_timing_payload(total_t0, context_ms=context_ms, agent_ms=agent_ms, persist_ms=persist_ms))
    return result_dict


@router.post("/chat/{opportunity_id}")
@_handle_flow_error
async def chat_with_agent(opportunity_id: str, body: ChatMessageRequest) -> dict[str, Any]:
    """对象上下文对话：人类发消息 → Lead Agent 多轮路由 → Sub-Agent 执行。"""
    from apps.content_planning.agents.lead_agent import LeadAgent

    total_t0 = time.perf_counter()
    flow = _get_flow()
    session = flow._get_session(opportunity_id)

    # Get or create thread
    if opportunity_id not in _agent_threads:
        _agent_threads[opportunity_id] = AgentThread(opportunity_id=opportunity_id)
    thread = _agent_threads[opportunity_id]

    # Record user message in thread + session
    thread.add_user_message(body.message, stage=body.current_stage, sender=body.sender_name)
    session_manager.add_message(
        opportunity_id,
        role=body.role,
        content=body.message,
        sender_name=body.sender_name,
    )

    # Build context
    context_t0 = time.perf_counter()
    bundle = _build_request_context_bundle(
        flow,
        opportunity_id,
        session,
        include_deep_context=body.mode == "deep",
    )
    ctx = _build_agent_context_from_bundle(
        opportunity_id,
        session,
        bundle,
        extra={
            "user_message": body.message,
            "current_stage": body.current_stage,
            "mode": body.mode,
        },
    )
    context_ms = int((time.perf_counter() - context_t0) * 1000)

    agent_t0 = time.perf_counter()
    lead = LeadAgent()
    result = lead.run_turn(ctx, thread)
    agent_ms = int((time.perf_counter() - agent_t0) * 1000)

    # Record agent response in thread + session
    persist_t0 = time.perf_counter()
    thread.add_agent_message(result.explanation, agent_role=result.agent_role, confidence=result.confidence)
    session_manager.add_message(
        opportunity_id,
        role=f"agent_{result.agent_role}",
        content=result.explanation,
        sender_name=result.agent_name,
        confidence=result.confidence,
    )

    # Emit SSE event
    event_bus.publish_sync(ObjectEvent(
        event_type="chat_response",
        opportunity_id=opportunity_id,
        object_type="agent_result",
        object_id=result.result_id,
        agent_role=result.agent_role,
        agent_name=result.agent_name,
        payload={
            "explanation": result.explanation,
            "confidence": result.confidence,
            "suggestions": [s.model_dump(mode="json") for s in result.suggestions],
            "turn_count": len([m for m in thread.messages if m.role == "user"]),
        },
    ))

    _log_agent_action(flow, opportunity_id, result)
    persist_ms = int((time.perf_counter() - persist_t0) * 1000)

    result_dict = result.model_dump(mode="json")
    result_dict["thread_id"] = thread.thread_id
    result_dict["turn_count"] = len([m for m in thread.messages if m.role == "user"])
    result_dict.update(_timing_payload(total_t0, context_ms=context_ms, agent_ms=agent_ms, persist_ms=persist_ms))
    return result_dict


def _log_agent_action(flow: OpportunityToPlanFlow, opportunity_id: str, result: AgentResult) -> None:
    """记录 Agent 动作到 session 的 agent_actions。"""
    if flow._store is None:
        return
    try:
        from datetime import datetime, timezone

        session_data = flow._store.load_session(opportunity_id)
        if session_data is None:
            return
        actions_raw = session_data.get("agent_actions") or []
        if not isinstance(actions_raw, list):
            actions_raw = []
        actions_raw.append(
            {
                "agent_role": result.agent_role,
                "agent_name": result.agent_name,
                "action": "run",
                "explanation": result.explanation,
                "confidence": result.confidence,
                "suggestions_count": len(result.suggestions),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        if len(actions_raw) > 50:
            actions_raw = actions_raw[-50:]
        flow._store.update_field(opportunity_id, "agent_actions", actions_raw)
    except Exception:
        pass


@router.get("/threads/{opportunity_id}")
@_handle_flow_error
async def get_thread(opportunity_id: str) -> dict[str, Any]:
    """获取对话线程历史。"""
    thread = _agent_threads.get(opportunity_id)
    if thread is None:
        return {"thread_id": None, "messages": [], "turn_count": 0}
    return {
        "thread_id": thread.thread_id,
        "messages": [m.model_dump(mode="json") for m in thread.recent(30)],
        "turn_count": len([m for m in thread.messages if m.role == "user"]),
        "active_agent": thread.active_agent,
    }


@router.get("/agent-log/{opportunity_id}")
@_handle_flow_error
async def agent_log(opportunity_id: str) -> dict[str, Any]:
    """查看某机会的 Agent 动作日志。"""
    flow = _get_flow()
    if flow._store is None:
        return {"actions": [], "count": 0}
    session = flow._store.load_session(opportunity_id)
    if session is None:
        return {"actions": [], "count": 0}
    actions = session.get("agent_actions") or []
    return {"actions": actions, "count": len(actions)}


@router.get("/agents")
async def list_agents() -> dict[str, Any]:
    """列出所有已注册的 Agent。"""
    from apps.content_planning.agents import registry as agent_registry
    from apps.content_planning.agents.asset_producer import AssetProducerAgent
    from apps.content_planning.agents.brief_synthesizer import BriefSynthesizerAgent
    from apps.content_planning.agents.strategy_director import StrategyDirectorAgent
    from apps.content_planning.agents.template_planner import TemplatePlannerAgent
    from apps.content_planning.agents.trend_analyst import TrendAnalystAgent
    from apps.content_planning.agents.visual_director import VisualDirectorAgent

    catalog = (
        TrendAnalystAgent,
        BriefSynthesizerAgent,
        TemplatePlannerAgent,
        StrategyDirectorAgent,
        VisualDirectorAgent,
        AssetProducerAgent,
    )
    static_agents = [
        {"agent_id": cls.agent_id, "agent_name": cls.agent_name, "agent_role": cls.agent_role}
        for cls in catalog
    ]
    return {"agents": agent_registry.list_agents() or static_agents}


class LockFieldRequest(BaseModel):
    object_type: str  # brief / strategy / plan / asset_bundle
    field: str
    locked_by: str = ""


@router.post("/lock/{opportunity_id}")
@_handle_flow_error
async def lock_field(opportunity_id: str, body: LockFieldRequest) -> dict[str, Any]:
    """锁定对象的某个字段。"""
    flow = _get_flow()
    session = flow._get_session(opportunity_id)
    obj_map = {
        "brief": session.brief,
        "strategy": session.strategy,
        "plan": session.note_plan,
        "asset_bundle": session.asset_bundle,
    }
    target = obj_map.get(body.object_type)
    if target is None:
        raise HTTPException(status_code=404, detail=f"对象 {body.object_type} 未找到")
    from apps.content_planning.schemas.lock import ObjectLock

    if target.locks is None:
        target.locks = ObjectLock()
    target.locks.lock(body.field, body.locked_by)
    flow._persist(session, status="generated")
    return {"status": "locked", "field": body.field, "object_type": body.object_type}


@router.post("/unlock/{opportunity_id}")
@_handle_flow_error
async def unlock_field(opportunity_id: str, body: LockFieldRequest) -> dict[str, Any]:
    """解锁对象的某个字段。"""
    flow = _get_flow()
    session = flow._get_session(opportunity_id)
    obj_map = {
        "brief": session.brief,
        "strategy": session.strategy,
        "plan": session.note_plan,
        "asset_bundle": session.asset_bundle,
    }
    target = obj_map.get(body.object_type)
    if target is None:
        raise HTTPException(status_code=404, detail=f"对象 {body.object_type} 未找到")
    if target.locks:
        target.locks.unlock(body.field)
    flow._persist(session, status="generated")
    return {"status": "unlocked", "field": body.field, "object_type": body.object_type}


@router.get("/versions/{opportunity_id}/{object_type}")
@_handle_flow_error
async def list_versions(opportunity_id: str, object_type: str) -> dict[str, Any]:
    """列出某对象类型的所有历史版本。"""
    flow = _get_flow()
    if flow._store is None:
        return {"versions": [], "count": 0}
    versions = flow._store.load_versions(opportunity_id, object_type)
    return {"versions": versions, "count": len(versions)}


class RestoreVersionRequest(BaseModel):
    object_type: str
    version: int


@router.post("/restore-version/{opportunity_id}")
@_handle_flow_error
async def restore_version(opportunity_id: str, body: RestoreVersionRequest) -> dict[str, Any]:
    """恢复某个历史版本为当前版本。"""
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    versions = flow._store.load_versions(opportunity_id, body.object_type)
    target = None
    for v in versions:
        if isinstance(v, dict) and v.get("version") == body.version:
            target = v
            break
    if target is None:
        raise HTTPException(status_code=404, detail=f"版本 {body.version} 未找到")
    flow._store.update_field(opportunity_id, body.object_type, target)
    flow._cache.pop(opportunity_id, None)
    return {"status": "restored", "object_type": body.object_type, "version": body.version}


class GenerateVariantRequest(BaseModel):
    axis: Literal["template", "tone", "scene", "brand", "platform"] = "tone"
    label: str = ""


@router.post("/asset-bundle/{opportunity_id}/generate-variant")
@_handle_flow_error
async def generate_variant(opportunity_id: str, body: GenerateVariantRequest) -> dict[str, Any]:
    """从资产包派生变体。"""
    from apps.content_planning.services.variant_generator import VariantGenerator

    bundle = _get_flow().assemble_asset_bundle(opportunity_id)
    variant = VariantGenerator.generate_variant(bundle, body.axis, body.label)
    return variant.model_dump(mode="json")


# ── Graph / Memory / Skills ───────────────────────────────────

@router.get("/graph/{opportunity_id}")
@_handle_flow_error
async def get_plan_graph(opportunity_id: str) -> dict[str, Any]:
    """获取或创建内容策划状态图。"""
    graph = build_default_graph(opportunity_id)
    return graph.model_dump(mode="json")


@router.get("/memory/{opportunity_id}")
@_handle_flow_error
async def get_memories(opportunity_id: str, category: str | None = None) -> dict[str, Any]:
    """获取机会卡相关的 Agent 记忆。"""
    mem = AgentMemory()
    entries = mem.recall(opportunity_id=opportunity_id, category=category)
    return {"memories": [e.model_dump(mode="json") for e in entries]}


@router.get("/skills")
async def list_skills_catalog() -> dict[str, Any]:
    """列出所有可用 Skills。"""
    skills = skill_registry.list_skills()
    return {"skills": [s.model_dump(mode="json") for s in skills]}


# ═══════════════════════════════════════════════════════════════
#  兼容路由（无前缀，router_alias）
# ═══════════════════════════════════════════════════════════════

@router_alias.post("/xhs-opportunities/{opportunity_id}/generate-brief")
@_handle_flow_error
async def generate_brief_alias(opportunity_id: str, request: Request) -> dict[str, Any]:
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    return flow.build_brief(opportunity_id).model_dump(mode="json")


@router_alias.post("/xhs-opportunities/{opportunity_id}/generate-note-plan")
@_handle_flow_error
async def generate_note_plan_alias(
    opportunity_id: str,
    body: GeneratePlanRequest | None = None,
) -> dict[str, Any]:
    if body is None:
        body = GeneratePlanRequest()
    return _get_flow().build_note_plan(
        opportunity_id,
        with_generation=_resolve_with_generation(body),
        preferred_template_id=body.preferred_template_id,
    )


# ═══════════════════════════════════════════════════════════════
#  Discussion + Evaluation API
# ═══════════════════════════════════════════════════════════════

class DiscussionRequest(BaseModel):
    question: str
    stage: str = ""


class EvaluateRequest(BaseModel):
    stages: list[str] = Field(default_factory=lambda: ["card", "brief", "match", "strategy", "plan", "asset"])


def _build_eval_context(flow: OpportunityToPlanFlow, opportunity_id: str) -> dict[str, Any]:
    session_data = flow.get_session_data(opportunity_id)
    card = flow._adapter.get_card(opportunity_id)
    return {
        "card": card,
        "brief": session_data.get("brief"),
        "match_result": session_data.get("match_result"),
        "strategy": session_data.get("strategy"),
        "plan": session_data.get("plan") or session_data.get("note_plan"),
        "titles": session_data.get("titles"),
        "body": session_data.get("body"),
        "image_briefs": session_data.get("image_briefs"),
        "asset_bundle": session_data.get("asset_bundle"),
    }


def _stage_rubric_version(evaluation: dict[str, Any] | StageEvaluation | None) -> str:
    if evaluation is None:
        return ""
    if isinstance(evaluation, StageEvaluation):
        return evaluation.rubric_version or ""
    return str(evaluation.get("rubric_version") or "")


def _is_pipeline_baseline_compatible(
    baseline_eval: PipelineEvaluation | None,
    upgrade_eval: PipelineEvaluation | None,
) -> bool:
    if baseline_eval is None or upgrade_eval is None:
        return False
    for stage in ("strategy", "plan", "asset"):
        before = baseline_eval.stage_scores.get(stage)
        after = upgrade_eval.stage_scores.get(stage)
        if before is None and after is None:
            continue
        if before is None or after is None:
            return False
        if _stage_rubric_version(before) != _stage_rubric_version(after) or _stage_rubric_version(before) == "":
            return False
    return True


def _build_agent_context(
    flow: OpportunityToPlanFlow,
    opportunity_id: str,
    stage: str,
    *,
    include_deep_context: bool = False,
) -> AgentContext:
    flow.ensure_stage_object(opportunity_id, stage)
    session = flow._get_session(opportunity_id)
    bundle = _build_request_context_bundle(
        flow,
        opportunity_id,
        session,
        include_deep_context=include_deep_context,
    )
    return _build_agent_context_from_bundle(
        opportunity_id,
        session,
        bundle,
        extra={"current_stage": stage},
    )


async def _run_stage_discussion(opportunity_id: str, stage: str, question: str, run_mode: str = "agent_assisted_council") -> dict[str, Any]:
    total_t0 = time.perf_counter()
    context_t0 = time.perf_counter()
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")

    normalized_stage = _normalize_stage(stage)
    snapshot = flow.get_stage_snapshot(opportunity_id, normalized_stage)
    session = flow._get_session(opportunity_id)
    task = AgentTask(
        opportunity_id=opportunity_id,
        stage=normalized_stage,
        run_mode=cast(Literal["baseline_compiler", "agent_assisted_single", "agent_assisted_council"], run_mode),
        status="queued",
        session_ref=AgentSessionRef(
            opportunity_id=opportunity_id,
            workspace_id=session.workspace_id,
            brand_id=session.brand_id,
            campaign_id=session.campaign_id,
        ),
        payload={"question": question, "base_version": snapshot["version"]},
    )
    flow._store.save_agent_task(task.task_id, opportunity_id, normalized_stage, run_mode, "queued", task.model_dump(mode="json"))

    run = AgentRun(
        task_id=task.task_id,
        opportunity_id=opportunity_id,
        stage=normalized_stage,
        run_mode=cast(Literal["baseline_compiler", "agent_assisted_single", "agent_assisted_council"], run_mode),
        status="running",
    )
    flow._store.save_agent_run(run.run_id, task.task_id, opportunity_id, normalized_stage, run_mode, "running", run.model_dump(mode="json"))
    context_ms = int((time.perf_counter() - context_t0) * 1000)

    orchestrator = DiscussionOrchestrator()

    def _on_message(msg: AgentMessage) -> None:
        event_bus.publish_sync(ObjectEvent(
            event_type="discussion_message",
            opportunity_id=opportunity_id,
            object_type="discussion",
            object_id=getattr(msg, "message_id", ""),
            agent_role=msg.agent_role,
            agent_name=msg.metadata.get("agent_name", msg.agent_role) if msg.metadata else msg.agent_role,
            payload={"role": msg.role, "content": msg.content, "stage": normalized_stage},
        ))

    try:
        discussion_t0 = time.perf_counter()
        discussion_mode = "fast" if run_mode == "agent_assisted_single" else "deep"
        round_data = orchestrator.discuss(
            opportunity_id=opportunity_id,
            stage=normalized_stage,
            user_question=question,
            context=_build_agent_context(
                flow,
                opportunity_id,
                normalized_stage,
                include_deep_context=discussion_mode == "deep",
            ),
            on_message=_on_message,
            mode=cast(Literal["fast", "deep"], discussion_mode),
        )
        discussion_ms = int((time.perf_counter() - discussion_t0) * 1000)
        diff_rows, blocked_fields = flow.build_stage_diff(opportunity_id, normalized_stage, round_data.proposed_updates)
        proposal = StageProposal(
            opportunity_id=opportunity_id,
            stage=normalized_stage,
            target_object_type=_STAGE_OBJECT_TYPES[normalized_stage],
            target_object_id=snapshot["object_id"],
            base_version=snapshot["version"],
            run_mode=cast(Literal["baseline_compiler", "agent_assisted_single", "agent_assisted_council"], run_mode),
            summary=round_data.consensus or "",
            proposed_updates=round_data.proposed_updates,
            diff=ProposalDiff(changes=[ProposalFieldChange(**row) for row in diff_rows]),
            blocked_fields=blocked_fields,
            requires_human_confirmation=True,
            confidence=round_data.overall_score,
            source_run_id=run.run_id,
            source_discussion_id=round_data.round_id,
        )
        record = AgentDiscussionRecord(
            discussion_id=round_data.round_id,
            opportunity_id=opportunity_id,
            stage=normalized_stage,
            question=question,
            participants=round_data.participants,
            messages=[m.model_dump(mode="json") for m in round_data.messages],
            summary=round_data.consensus or "",
            proposal_id=proposal.proposal_id,
            run_id=run.run_id,
            base_version=snapshot["version"],
            status="completed",
        )
        run.status = "completed"
        run.participant_roles = round_data.participants
        run.summary = round_data.consensus or ""
        run.payload = {
            "participants": round_data.participants,
            "question": question,
            "proposal_id": proposal.proposal_id,
        }
        persist_t0 = time.perf_counter()
        flow._store.save_agent_run(run.run_id, task.task_id, opportunity_id, normalized_stage, run_mode, run.status, run.model_dump(mode="json"))
        flow._store.save_proposal(proposal.proposal_id, opportunity_id, normalized_stage, proposal.status, proposal.model_dump(mode="json"))
        flow._store.save_discussion(record.discussion_id, opportunity_id, normalized_stage, proposal.proposal_id, run.run_id, record.model_dump(mode="json"))
        persist_ms = int((time.perf_counter() - persist_t0) * 1000)
        return {
            "stage": normalized_stage,
            "task_id": task.task_id,
            "discussion_id": record.discussion_id,
            "proposal_id": proposal.proposal_id,
            "run_id": run.run_id,
            "discussion": record.model_dump(mode="json"),
            "proposal": proposal.model_dump(mode="json"),
            **_timing_payload(total_t0, context_ms=context_ms, discussion_ms=discussion_ms, persist_ms=persist_ms),
        }
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        flow._store.save_agent_run(run.run_id, task.task_id, opportunity_id, normalized_stage, run_mode, run.status, run.model_dump(mode="json"))
        raise


@router.post("/discuss/{opportunity_id}")
@_handle_flow_error
async def start_discussion(opportunity_id: str, body: DiscussionRequest) -> dict[str, Any]:
    """兼容旧讨论入口。"""
    return await _run_stage_discussion(opportunity_id, body.stage or "brief", body.question)


@router.post("/stages/{stage}/{opportunity_id}/discussions")
@_handle_flow_error
async def start_stage_discussion(stage: str, opportunity_id: str, body: StageDiscussionRequest) -> dict[str, Any]:
    return await _run_stage_discussion(opportunity_id, stage, body.question, body.run_mode)


@router.get("/discussions/{discussion_id}")
@_handle_flow_error
async def get_discussion_detail(discussion_id: str) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    discussion = flow._store.load_discussion(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")
    return discussion


@router.get("/proposals/{proposal_id}")
@_handle_flow_error
async def get_proposal_detail(proposal_id: str) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    proposal = flow._store.load_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.get("/agent-runs/{run_id}")
@_handle_flow_error
async def get_agent_run(run_id: str) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    run = flow._store.load_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


@router.get("/agent-tasks/{task_id}")
@_handle_flow_error
async def get_agent_task(task_id: str) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    task = flow._store.load_agent_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Agent task not found")
    return task


@router.post("/proposals/{proposal_id}/apply")
@_handle_flow_error
async def apply_proposal(proposal_id: str, body: ApplyProposalRequest) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    proposal = flow._store.load_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    stage = proposal.get("stage")
    if stage not in {"brief", "strategy", "plan", "asset"}:
        raise HTTPException(status_code=409, detail=f"Stage apply is not enabled yet for {stage}")
    result = flow.apply_stage_updates(
        proposal["opportunity_id"],
        stage,
        proposal.get("proposed_updates", {}),
        selected_fields=body.selected_fields,
        actor_user_id=body.actor_user_id,
        base_version=proposal.get("base_version"),
    )
    decision = ProposalDecision(
        proposal_id=proposal_id,
        decision="partial_apply" if result["skipped_fields"] else "applied",
        actor_user_id=body.actor_user_id,
        selected_fields=body.selected_fields or list(proposal.get("proposed_updates", {}).keys()),
        skipped_fields=result["skipped_fields"],
        notes=body.notes,
    )
    flow._store.save_proposal_decision(decision.decision_id, proposal_id, decision.decision, decision.model_dump(mode="json"))
    proposal["status"] = "applied" if result["applied_fields"] else "blocked"
    proposal["updated_at"] = decision.created_at.isoformat()
    flow._store.save_proposal(proposal_id, proposal["opportunity_id"], proposal["stage"], proposal["status"], proposal)
    payload_key = {
        "brief": "brief",
        "strategy": "strategy",
        "plan": "plan",
        "asset": "asset_bundle",
    }[stage]
    return {
        "proposal_id": proposal_id,
        "status": proposal["status"],
        "applied_fields": result["applied_fields"],
        "skipped_fields": result["skipped_fields"],
        "stale_flags": result["stale_flags"],
        payload_key: result.get(payload_key) or result.get("payload"),
    }


@router.post("/proposals/{proposal_id}/reject")
@_handle_flow_error
async def reject_proposal(proposal_id: str, body: RejectProposalRequest) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    proposal = flow._store.load_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    decision = ProposalDecision(
        proposal_id=proposal_id,
        decision="rejected",
        actor_user_id=body.actor_user_id,
        notes=body.notes,
    )
    flow._store.save_proposal_decision(decision.decision_id, proposal_id, decision.decision, decision.model_dump(mode="json"))
    proposal["status"] = "rejected"
    flow._store.save_proposal(proposal_id, proposal["opportunity_id"], proposal["stage"], proposal["status"], proposal)
    return {"proposal_id": proposal_id, "status": "rejected"}


@router.post("/evaluate/{opportunity_id}")
@_handle_flow_error
async def evaluate_pipeline(opportunity_id: str, body: EvaluateRequest | None = None) -> dict[str, Any]:
    """运行端到端评价。"""
    flow = _get_flow()
    context = _build_eval_context(flow, opportunity_id)
    stages_to_eval = body.stages if body else ["card", "brief", "match", "strategy", "plan", "asset"]

    stage_evals = {}
    for stage in stages_to_eval:
        try:
            stage_eval = evaluate_stage(stage, opportunity_id, context)
            stage_evals[stage] = stage_eval
        except Exception:
            pass

    metrics = compute_pipeline_metrics(opportunity_id, flow.get_session_data(opportunity_id))

    pipeline_eval = PipelineEvaluation(
        opportunity_id=opportunity_id,
        stage_scores=stage_evals,
        metrics=metrics,
    )
    pipeline_eval.compute_pipeline_score()
    if flow._store is not None:
        flow._store.save_evaluation(pipeline_eval.evaluation_id, opportunity_id, "pipeline", pipeline_eval.model_dump(mode="json"))
    return pipeline_eval.model_dump(mode="json")


@router.post("/evaluations/{stage}/{opportunity_id}/run")
@_handle_flow_error
async def run_stage_evaluation(stage: str, opportunity_id: str) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    normalized_stage = _normalize_stage(stage)
    snapshot = flow.get_stage_snapshot(opportunity_id, normalized_stage)
    stage_eval = evaluate_stage(_public_to_eval_stage(normalized_stage), opportunity_id, _build_eval_context(flow, opportunity_id))
    stage_eval.run_mode = "agent_assisted_council"
    if normalized_stage == "strategy" and not stage_eval.rubric_version:
        stage_eval.rubric_version = "strategy_v2"
    if normalized_stage == "plan" and not stage_eval.rubric_version:
        stage_eval.rubric_version = "plan_v1"
    if normalized_stage == "asset" and not stage_eval.rubric_version:
        stage_eval.rubric_version = "asset_v1"
    scorecard = StageScorecard(
        opportunity_id=opportunity_id,
        stage=normalized_stage,
        run_mode="agent_assisted_council",
        base_version=snapshot["version"],
        overall_score=stage_eval.overall_score,
        dimensions=stage_eval.dimensions,
        evaluator=stage_eval.evaluator,
        model_used=stage_eval.model_used,
        explanation=stage_eval.explanation,
        rubric_version=stage_eval.rubric_version,
        pipeline_run_id=flow.get_session_data(opportunity_id).get("pipeline_run_id", ""),
    )
    flow._store.save_evaluation(scorecard.scorecard_id, opportunity_id, "stage_run", scorecard.model_dump(mode="json"))
    payload = scorecard.model_dump(mode="json")
    payload["eval_type"] = "stage_run"
    return payload


@router.get("/evaluation/{opportunity_id}")
@_handle_flow_error
async def get_evaluation(opportunity_id: str) -> dict[str, Any]:
    """获取最近的评价结果。"""
    items = await list_evaluations(opportunity_id)
    return {"evaluations": items["items"], "items": items["items"], "total": items["total"]}


@router.get("/evaluations/{opportunity_id}")
@_handle_flow_error
async def list_evaluations(opportunity_id: str, eval_type: str | None = None) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        return {"items": [], "total": 0}
    items = flow._store.load_evaluations(opportunity_id, eval_type=eval_type, limit=50)
    return {"items": items, "total": len(items)}


# ── Phase 4: 评价对比 + 学习闭环 ──────────────────────────────


class BaselineRequest(BaseModel):
    """采集 baseline 评价。"""
    stages: list[str] = Field(default_factory=lambda: ["card", "brief", "match", "strategy", "plan", "asset"])


class CompareRequest(BaseModel):
    """触发 Before/After 对比。"""
    apply_learning: bool = True
    discussion_round_ids: list[str] = Field(default_factory=list)


@router.post("/baseline/{opportunity_id}")
@_handle_flow_error
async def collect_baseline(opportunity_id: str, body: BaselineRequest | None = None) -> dict[str, Any]:
    """采集 baseline 评价分数。"""
    from apps.content_planning.evaluation.comparison import collect_baseline as _collect

    flow = _get_flow()
    context = _build_eval_context(flow, opportunity_id)
    baseline = _collect(opportunity_id, context)
    if flow._store is not None:
        flow._store.save_evaluation(baseline.evaluation_id, opportunity_id, "baseline", baseline.model_dump(mode="json"))
    return baseline.model_dump(mode="json")


@router.post("/compare/{opportunity_id}")
@_handle_flow_error
async def compare_evaluations(opportunity_id: str, body: CompareRequest | None = None) -> dict[str, Any]:
    """运行 Before/After 对比 + 可选学习闭环。"""
    from apps.content_planning.evaluation.comparison import (
        apply_learning_loop,
        compare,
        collect_upgrade_evaluation,
    )

    flow = _get_flow()
    context = _build_eval_context(flow, opportunity_id)
    upgrade = collect_upgrade_evaluation(opportunity_id, context)
    baseline = None
    if flow._store is not None:
        baseline_rows = flow._store.load_evaluations(opportunity_id, eval_type="baseline", limit=20)
        for row in baseline_rows:
            try:
                candidate = PipelineEvaluation.model_validate(row["payload"])
                if _is_pipeline_baseline_compatible(candidate, upgrade):
                    baseline = candidate
                    break
            except Exception:
                continue

    report = compare(opportunity_id, baseline=baseline, upgrade=upgrade, context=context)

    if body and body.apply_learning:
        report = apply_learning_loop(report)
    if flow._store is not None:
        flow._store.save_evaluation(report.report_id, opportunity_id, "comparison", report.model_dump(mode="json"))
    return report.model_dump(mode="json")
