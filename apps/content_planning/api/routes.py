"""content_planning API 路由 v2。

原子 API + 编排 API + Brief 编辑 + 局部重生成。
主路径前缀：/content-planning/...
兼容路径（与验收文档 A3 一致）：/xhs-opportunities/...（无前缀，见 router_alias）
"""

from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.content_planning.agents.base import AgentContext, AgentMessage, AgentResult, AgentThread
from apps.content_planning.agents.discussion import DiscussionOrchestrator, DiscussionRound
from apps.content_planning.agents.memory import AgentMemory, MemoryEntry
from apps.content_planning.agents.plan_graph import PlanGraph, build_default_graph
from apps.content_planning.agents.skill_registry import SkillDefinition, skill_registry
from apps.content_planning.exceptions import OpportunityNotPromotedError
from apps.content_planning.gateway.event_bus import event_bus, ObjectEvent
from apps.content_planning.gateway.session_manager import session_manager
from apps.content_planning.services.opportunity_to_plan_flow import OpportunityToPlanFlow

router = APIRouter(prefix="/content-planning", tags=["content_planning"])
router_alias = APIRouter(tags=["content_planning"])

_flow: OpportunityToPlanFlow | None = None
_agent_threads: dict[str, AgentThread] = {}


def _get_flow() -> OpportunityToPlanFlow:
    global _flow
    if _flow is None:
        _flow = OpportunityToPlanFlow()
    return _flow


def set_flow(flow: OpportunityToPlanFlow) -> None:
    """允许外部注入（如 app.py 共享 adapter/store）。"""
    global _flow
    _flow = flow


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
    extra: dict[str, Any] = Field(default_factory=dict)


class ChatMessageRequest(BaseModel):
    message: str
    role: str = "human"
    sender_name: str = ""
    current_stage: str = ""


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

    flow = _get_flow()
    session = flow._get_session(opportunity_id)

    card = flow._adapter.get_card(opportunity_id)
    source_notes = flow._adapter.get_source_notes(card.source_note_ids) if card else []
    review_summary = flow._adapter.get_review_summary(opportunity_id) if card else {}

    template = None
    if session.match_result and session.match_result.primary_template:
        template = flow._retriever.get_template(session.match_result.primary_template.template_id)

    ctx = AgentContext(
        opportunity_id=opportunity_id,
        brief=session.brief,
        strategy=session.strategy,
        plan=session.note_plan,
        match_result=session.match_result,
        template=template,
        titles=session.titles,
        body=session.body,
        image_briefs=session.image_briefs,
        asset_bundle=session.asset_bundle,
        source_notes=source_notes,
        review_summary=review_summary if isinstance(review_summary, dict) else {},
        extra={**body.extra, "card": card},
    )

    agent = agent_cls()
    result = agent.run(ctx)

    result_dict = result.model_dump(mode="json")

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

    return result_dict


@router.post("/chat/{opportunity_id}")
@_handle_flow_error
async def chat_with_agent(opportunity_id: str, body: ChatMessageRequest) -> dict[str, Any]:
    """对象上下文对话：人类发消息 → Lead Agent 多轮路由 → Sub-Agent 执行。"""
    from apps.content_planning.agents.lead_agent import LeadAgent

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
    card = flow._adapter.get_card(opportunity_id)
    source_notes = flow._adapter.get_source_notes(card.source_note_ids) if card else []
    review_summary = flow._adapter.get_review_summary(opportunity_id) if card else {}

    template = None
    if session.match_result and session.match_result.primary_template:
        template = flow._retriever.get_template(session.match_result.primary_template.template_id)

    ctx = AgentContext(
        opportunity_id=opportunity_id,
        brief=session.brief,
        strategy=session.strategy,
        plan=session.note_plan,
        match_result=session.match_result,
        template=template,
        titles=session.titles,
        body=session.body,
        image_briefs=session.image_briefs,
        asset_bundle=session.asset_bundle,
        source_notes=source_notes,
        review_summary=review_summary if isinstance(review_summary, dict) else {},
        extra={
            "card": card,
            "user_message": body.message,
            "current_stage": body.current_stage,
        },
    )

    lead = LeadAgent()
    result = lead.run_turn(ctx, thread)

    # Record agent response in thread + session
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

    result_dict = result.model_dump(mode="json")
    result_dict["thread_id"] = thread.thread_id
    result_dict["turn_count"] = len([m for m in thread.messages if m.role == "user"])
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
    object_type: str  # brief / strategy / plan / bundle
    field: str
    locked_by: str = ""


@router.post("/lock/{opportunity_id}")
@_handle_flow_error
async def lock_field(opportunity_id: str, body: LockFieldRequest) -> dict[str, Any]:
    """锁定对象的某个字段。"""
    flow = _get_flow()
    session = flow._get_session(opportunity_id)
    obj_map = {"brief": session.brief, "strategy": session.strategy, "plan": session.note_plan}
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
    obj_map = {"brief": session.brief, "strategy": session.strategy, "plan": session.note_plan}
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
    stages: list[str] = Field(default_factory=lambda: ["card", "brief", "match", "strategy", "content"])


@router.post("/discuss/{opportunity_id}")
@_handle_flow_error
async def start_discussion(opportunity_id: str, body: DiscussionRequest) -> dict[str, Any]:
    """触发多 Agent 阶段讨论。"""
    flow = _get_flow()
    session = flow._get_session(opportunity_id)

    card = flow._adapter.get_card(opportunity_id)
    source_notes = flow._adapter.get_source_notes(card.source_note_ids) if card else []

    template = None
    if session.match_result and session.match_result.primary_template:
        template = flow._retriever.get_template(session.match_result.primary_template.template_id)

    ctx = AgentContext(
        opportunity_id=opportunity_id,
        brief=session.brief,
        strategy=session.strategy,
        plan=session.note_plan,
        match_result=session.match_result,
        template=template,
        source_notes=source_notes,
        extra={"card": card},
    )

    orchestrator = DiscussionOrchestrator()

    def _on_message(msg):
        event_bus.publish_sync(ObjectEvent(
            event_type="discussion_message",
            opportunity_id=opportunity_id,
            object_type="discussion",
            object_id=msg.message_id,
            agent_role=msg.agent_role,
            agent_name=msg.metadata.get("agent_name", msg.agent_role),
            payload={"role": msg.role, "content": msg.content, "stage": body.stage},
        ))

    discussion = orchestrator.discuss(
        opportunity_id=opportunity_id,
        stage=body.stage,
        user_question=body.question,
        context=ctx,
        on_message=_on_message,
    )

    return discussion.model_dump(mode="json")


@router.post("/evaluate/{opportunity_id}")
@_handle_flow_error
async def evaluate_pipeline(opportunity_id: str, body: EvaluateRequest | None = None) -> dict[str, Any]:
    """运行端到端评价。"""
    from apps.content_planning.evaluation.stage_evaluator import evaluate_stage
    from apps.content_planning.evaluation.pipeline_metrics import compute_pipeline_metrics
    from apps.content_planning.schemas.evaluation import PipelineEvaluation, PipelineMetrics

    flow = _get_flow()
    session_data = flow.get_session_data(opportunity_id)
    card = flow._adapter.get_card(opportunity_id)

    stages_to_eval = body.stages if body else ["card", "brief", "match", "strategy", "content"]

    eval_context = {
        "card": card,
        "brief": session_data.get("brief"),
        "match_result": session_data.get("match_result"),
        "strategy": session_data.get("strategy"),
        "plan": session_data.get("plan"),
        "titles": session_data.get("titles"),
        "body": session_data.get("body"),
        "image_briefs": session_data.get("image_briefs"),
    }

    stage_evals = {}
    for stage in stages_to_eval:
        try:
            stage_eval = evaluate_stage(stage, opportunity_id, eval_context)
            stage_evals[stage] = stage_eval
        except Exception:
            pass

    metrics = compute_pipeline_metrics(opportunity_id, session_data)

    pipeline_eval = PipelineEvaluation(
        opportunity_id=opportunity_id,
        stage_scores=stage_evals,
        metrics=metrics,
    )
    pipeline_eval.compute_pipeline_score()

    return pipeline_eval.model_dump(mode="json")


@router.get("/evaluation/{opportunity_id}")
@_handle_flow_error
async def get_evaluation(opportunity_id: str) -> dict[str, Any]:
    """获取最近的评价结果。"""
    flow = _get_flow()
    if flow._store is None:
        return {"evaluations": []}
    session = flow._store.load_session(opportunity_id)
    if session is None:
        return {"evaluations": []}
    evals = session.get("evaluations", [])
    return {"evaluations": evals if isinstance(evals, list) else []}


# ── Phase 4: 评价对比 + 学习闭环 ──────────────────────────────


class BaselineRequest(BaseModel):
    """采集 baseline 评价。"""
    stages: list[str] = Field(default_factory=lambda: ["card", "brief", "match", "strategy", "content"])


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
    session_data = flow.get_session_data(opportunity_id)
    card = flow._adapter.get_card(opportunity_id)
    context = {
        "card": card,
        "brief": session_data.get("brief"),
        "match_result": session_data.get("match_result"),
        "strategy": session_data.get("strategy"),
        "plan": session_data.get("plan"),
        "titles": session_data.get("titles"),
        "body": session_data.get("body"),
        "image_briefs": session_data.get("image_briefs"),
    }
    baseline = _collect(opportunity_id, context)
    return baseline.model_dump(mode="json")


@router.post("/compare/{opportunity_id}")
@_handle_flow_error
async def compare_evaluations(opportunity_id: str, body: CompareRequest | None = None) -> dict[str, Any]:
    """运行 Before/After 对比 + 可选学习闭环。"""
    from apps.content_planning.evaluation.comparison import (
        apply_learning_loop,
        compare,
    )

    flow = _get_flow()
    session_data = flow.get_session_data(opportunity_id)
    card = flow._adapter.get_card(opportunity_id)
    context = {
        "card": card,
        "brief": session_data.get("brief"),
        "match_result": session_data.get("match_result"),
        "strategy": session_data.get("strategy"),
        "plan": session_data.get("plan"),
        "titles": session_data.get("titles"),
        "body": session_data.get("body"),
        "image_briefs": session_data.get("image_briefs"),
    }

    report = compare(opportunity_id, context=context)

    if body and body.apply_learning:
        report = apply_learning_loop(report)

    return report.model_dump(mode="json")
