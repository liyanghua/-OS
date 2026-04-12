"""content_planning API 路由 v2。

原子 API + 编排 API + Brief 编辑 + 局部重生成。
主路径前缀：/content-planning/...
兼容路径（与验收文档 A3 一致）：/xhs-opportunities/...（无前缀，见 router_alias）
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Literal, cast

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.content_planning.agents.base import AgentContext, AgentMessage, AgentResult, AgentThread, RequestContextBundle
from apps.content_planning.agents.context_assembler import PlanningContextAssembler
from apps.content_planning.adapters.llm_router import llm_router
from apps.content_planning.agents.discussion import (
    AGENT_DISPLAY_NAMES,
    DiscussionOrchestrator,
    DiscussionRound,
    compute_applyability,
    reconcile_council_decision_type,
)
from apps.content_planning.agents.memory import AgentMemory, MemoryEntry
from apps.content_planning.agents.plan_graph import PlanGraph, build_default_graph
from apps.content_planning.agents.skill_registry import SkillDefinition, skill_registry
from apps.content_planning.agents.soul_loader import SoulLoader
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
from apps.content_planning.schemas.council_v2 import (
    CouncilAgentObs,
    CouncilModelSummary,
    CouncilObservability,
    CouncilParticipantSpec,
    CouncilSession,
    CouncilSynthesisObs,
    new_alternative_id,
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


BRIEF_COUNCIL_FIELD_WHITELIST: tuple[str, ...] = (
    "target_user",
    "target_scene",
    "content_goal",
    "primary_value",
    "visual_style_direction",
    "avoid_directions",
    "template_hints",
    "core_motive",
    "price_positioning",
    "target_audience",
    "why_worth_doing",
    "competitive_angle",
)


def _format_brief_snapshot_for_council(session: Any) -> tuple[str, str]:
    """返回 (可写字段 JSON 快照, 锁定字段说明)。"""
    brief = getattr(session, "brief", None)
    if brief is None:
        return "", ""
    data = brief.model_dump(mode="json") if hasattr(brief, "model_dump") else {}
    snap = {k: data.get(k) for k in BRIEF_COUNCIL_FIELD_WHITELIST if k in data}
    try:
        snap_json = json.dumps(snap, ensure_ascii=False, default=str)
    except Exception:
        snap_json = str(snap)
    locks = getattr(brief, "locks", None)
    locked_names: list[str] = []
    if locks is not None and hasattr(locks, "locked_field_names"):
        locked_names = list(locks.locked_field_names())
    locked_hint = "；".join(locked_names) if locked_names else "（无锁定字段）"
    return snap_json, f"以下字段已锁定，勿在 proposed_updates 中覆盖：{locked_hint}"


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
    brief_snap, locked_hint = _format_brief_snapshot_for_council(session)
    return RequestContextBundle(
        card=card,
        source_notes=source_notes,
        review_summary=review_summary,
        template=template,
        memory_context=memory_context,
        object_summary=_build_object_summary(session, card),
        council_brief_snapshot=brief_snap,
        council_locked_fields_hint=locked_hint,
    )


_planning_assembler = PlanningContextAssembler()


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
    ctx = AgentContext(
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
    stage = payload_extra.get("current_stage", "")
    mode = payload_extra.get("mode", "deep")
    planning_ctx = _planning_assembler.assemble(
        opportunity_id, stage, mode, session=session, bundle=bundle,
    )
    _planning_assembler.enrich_agent_context(ctx, planning_ctx)
    return ctx


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
    parent_discussion_id: str = ""
    target_sub_object_type: str = ""
    include_chat_context: bool = True


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
        except HTTPException:
            raise
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
        except Exception as exc:
            logger.error("Unhandled error in %s: %s", fn.__name__, exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"内部错误: {type(exc).__name__}: {exc}") from exc

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
    notes: str | None = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            raw = body.get("council_escalation_notes") or body.get("council_notes")
            if raw:
                notes = str(raw).strip() or None
    except Exception:
        notes = None
    return flow.build_brief(opportunity_id, council_escalation_notes=notes).model_dump(mode="json")


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


# ── V5: Production Pipeline APIs ──────────────────────────────


class ProductionCompileRequest(BaseModel):
    preferred_template_id: str | None = None
    with_evaluation: bool = True
    with_publish_format: bool = True


@router.post("/v5/compile/{opportunity_id}")
@_handle_flow_error
async def v5_compile(
    opportunity_id: str,
    request: Request,
    body: ProductionCompileRequest | None = None,
) -> dict[str, Any]:
    """V5 一键编译: Brief -> Strategy -> Plan -> 生成 -> AssetBundle + 质量评分 + 发布格式化。"""
    flow = _get_flow()
    _maybe_bind_workspace_context(flow, request, opportunity_id)
    if body is None:
        body = ProductionCompileRequest()
    return flow.compile_note_plan(
        opportunity_id,
        with_generation=True,
        with_evaluation=body.with_evaluation,
        with_publish_format=body.with_publish_format,
        preferred_template_id=body.preferred_template_id,
    )


@router.get("/v5/compilation-report/{opportunity_id}")
@_handle_flow_error
async def v5_compilation_report(opportunity_id: str) -> dict[str, Any]:
    """获取已有编译结果的质量评估报告。"""
    flow = _get_flow()
    report = flow._evaluate_compilation(opportunity_id)
    return report.model_dump(mode="json")


@router.get("/v5/quality-explanation/{opportunity_id}")
@_handle_flow_error
async def v5_quality_explanation(opportunity_id: str) -> dict[str, Any]:
    """获取生成结果 vs 源笔记的差异化质量解释。"""
    from apps.content_planning.services.quality_explainer import QualityExplainer

    flow = _get_flow()
    session = flow.get_session_data(opportunity_id)
    if not session.get("asset_bundle"):
        raise HTTPException(status_code=404, detail="尚无 AssetBundle")

    from apps.content_planning.schemas.asset_bundle import AssetBundle
    bundle = AssetBundle(**session["asset_bundle"])
    strategy = None
    if session.get("strategy"):
        from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
        strategy = RewriteStrategy(**session["strategy"])
    brief = None
    if session.get("brief"):
        from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
        brief = OpportunityBrief(**session["brief"])

    source_notes = flow._adapter.get_source_notes(brief.source_note_ids if brief else [])
    source_ctx = (source_notes[0] if source_notes else {}).get("note_context", {})

    explainer = QualityExplainer()
    explanation = explainer.explain(source_ctx, bundle, strategy, brief)
    return explanation.model_dump(mode="json")


@router.get("/v5/publish-package/{opportunity_id}")
@_handle_flow_error
async def v5_publish_package(opportunity_id: str) -> dict[str, Any]:
    """获取 PublishReadyPackage（基于已有 AssetBundle 格式化）。"""
    flow = _get_flow()
    pkg = flow.format_for_publish(opportunity_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="尚无 AssetBundle，请先完成编译")
    return pkg.model_dump(mode="json")


@router.get("/v5/tools")
async def v5_list_tools() -> dict[str, Any]:
    """列出所有已注册的工具和 MCP 服务器。"""
    from apps.content_planning.agents.tool_registry import tool_registry
    from apps.content_planning.agents.mcp_adapter import mcp_adapter
    from apps.content_planning.agents.skill_registry import skill_registry

    tools = tool_registry.list_tools()
    skills = skill_registry.list_skills()
    return {
        "tools": [{"name": t.name, "description": t.description, "toolset": t.toolset} for t in tools],
        "tool_count": len(tools),
        "skills": [{"id": s.skill_id, "name": s.skill_name, "category": s.category, "steps": len(s.executable_steps)} for s in skills],
        "skill_count": len(skills),
        "mcp_servers": mcp_adapter.list_servers(),
        "mcp_server_count": mcp_adapter.server_count,
    }


@router.post("/v5/auto-promote/{opportunity_id}")
@_handle_flow_error
async def v5_auto_promote(opportunity_id: str) -> dict[str, Any]:
    """Dev 环境快速晋级机会卡（跳过人工 review）。"""
    from apps.intel_hub.services.opportunity_promoter import auto_promote_for_dev

    flow = _get_flow()
    store = flow._adapter._store
    new_status = auto_promote_for_dev(store, opportunity_id)
    if new_status == "not_found":
        raise HTTPException(status_code=404, detail="机会卡未找到")
    return {"opportunity_id": opportunity_id, "status": new_status}


@router.post("/v5/batch-auto-promote")
@_handle_flow_error
async def v5_batch_auto_promote() -> dict[str, Any]:
    """Dev 环境批量快速晋级所有机会卡。"""
    from apps.intel_hub.services.opportunity_promoter import batch_auto_promote

    flow = _get_flow()
    store = flow._adapter._store
    results = batch_auto_promote(store)
    return {"promoted": results, "count": len(results)}


# ── V5: Data Flywheel APIs ────────────────────────────────────


class V5FeedbackRequest(BaseModel):
    opportunity_id: str
    asset_bundle_id: str = ""
    template_id: str = ""
    strategy_id: str = ""
    platform: str = "xhs"
    published_note_id: str = ""
    like_count: int = 0
    collect_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0
    human_notes: str = ""
    human_edits_summary: str = ""


@router.post("/v5/feedback")
@_handle_flow_error
async def v5_submit_feedback(body: V5FeedbackRequest) -> dict[str, Any]:
    """V5 统一反馈入口：接受发布效果数据，触发 Pattern 提取 + 模板权重 + 记忆写入。"""
    from apps.content_planning.schemas.unified_feedback import UnifiedFeedback
    from apps.content_planning.services.feedback_processor import FeedbackProcessor

    flow = _get_flow()
    plan_store = flow._store

    session_data = flow.get_session_data(body.opportunity_id)
    feedback = UnifiedFeedback(
        opportunity_id=body.opportunity_id,
        asset_bundle_id=body.asset_bundle_id or session_data.get("asset_bundle", {}).get("asset_bundle_id", ""),
        template_id=body.template_id or session_data.get("strategy", {}).get("template_id", ""),
        strategy_id=body.strategy_id or session_data.get("strategy", {}).get("strategy_id", ""),
        plan_id=session_data.get("note_plan", {}).get("plan_id", ""),
        brief_id=session_data.get("brief", {}).get("brief_id", ""),
        workspace_id=session_data.get("workspace_id", ""),
        brand_id=session_data.get("brand_id", ""),
        campaign_id=session_data.get("campaign_id", ""),
        platform=body.platform,
        published_note_id=body.published_note_id,
        like_count=body.like_count,
        collect_count=body.collect_count,
        comment_count=body.comment_count,
        share_count=body.share_count,
        view_count=body.view_count,
        human_notes=body.human_notes,
        human_edits_summary=body.human_edits_summary,
    )

    memory = None
    try:
        from apps.content_planning.agents.memory import AgentMemory
        from apps.intel_hub.config_loader import resolve_repo_path
        memory = AgentMemory(str(resolve_repo_path("data/agent_memory.sqlite")))
    except Exception:
        pass

    processor = FeedbackProcessor(plan_store=plan_store, memory=memory)
    result = processor.process(feedback)

    plan_store.save_unified_feedback(feedback)

    return result


@router.get("/v5/feedback/{opportunity_id}")
@_handle_flow_error
async def v5_get_feedback(opportunity_id: str) -> dict[str, Any]:
    """获取某机会卡的所有反馈记录。"""
    flow = _get_flow()
    records = flow._store.load_unified_feedback(opportunity_id=opportunity_id)
    return {"feedback": records, "count": len(records)}


@router.get("/v5/patterns")
@_handle_flow_error
async def v5_list_patterns(workspace_id: str = "", brand_id: str = "") -> dict[str, Any]:
    """获取已提取的 WinningPattern 和 FailedPattern。"""
    flow = _get_flow()
    store = flow._store
    kwargs: dict[str, Any] = {}
    if workspace_id:
        kwargs["workspace_id"] = workspace_id
    if brand_id:
        kwargs["brand_id"] = brand_id
    winning = store.load_winning_patterns(**kwargs)
    failed = store.load_failed_patterns(**kwargs)
    return {
        "winning_patterns": winning,
        "failed_patterns": failed,
        "winning_count": len(winning),
        "failed_count": len(failed),
    }


@router.get("/v5/template-effectiveness/{template_id}")
@_handle_flow_error
async def v5_template_effectiveness(template_id: str) -> dict[str, Any]:
    """获取模板效果历史记录。"""
    flow = _get_flow()
    records = flow._store.load_template_effectiveness(template_id)
    return {"records": records, "count": len(records)}


# ── V6: 内容生产链 APIs ──────────────────────────────────────


@router.post("/v6/ingest-eval/{opportunity_id}")
@_handle_flow_error
async def v6_ingest_eval(opportunity_id: str) -> dict[str, Any]:
    """对原始笔记运行数据完整度评估。"""
    flow = _get_flow()
    card = flow._adapter.get_card(opportunity_id)
    if card is None:
        raise HTTPException(status_code=404, detail="机会卡未找到")
    source_notes = flow._adapter.get_source_notes(card.source_note_ids)
    note_ctx = source_notes[0] if source_notes else {}
    eval_result = evaluate_stage("ingest", opportunity_id, {
        "parsed_note": note_ctx,
        "pipeline_details": note_ctx.get("pipeline_details", {}),
        "benchmarks": [],
    })
    return {
        "opportunity_id": opportunity_id,
        "stage": "ingest",
        "evaluation": eval_result.model_dump(mode="json"),
        "passed": eval_result.overall_score >= 0.25,
        "suggestions": [
            d.explanation for d in eval_result.dimensions if d.score < 0.4
        ],
    }


@router.post("/v6/enrich-card/{opportunity_id}")
@_handle_flow_error
async def v6_enrich_card(opportunity_id: str) -> dict[str, Any]:
    """用 V6 语义字段增强现有 card。"""
    from apps.content_planning.services.note_to_card_flow import NoteToCardFlow

    flow = _get_flow()
    card = flow._adapter.get_card(opportunity_id)
    if card is None:
        raise HTTPException(status_code=404, detail="机会卡未找到")
    source_notes = flow._adapter.get_source_notes(card.source_note_ids)
    note_ctx = source_notes[0] if source_notes else {}
    n2c = NoteToCardFlow()
    enriched = n2c._enrich_card(card, note_ctx, note_ctx.get("pipeline_details", {}))
    try:
        flow._adapter._store.update_card(enriched)
    except Exception:
        pass
    return {
        "opportunity_id": opportunity_id,
        "enriched_card": enriched.model_dump(mode="json"),
        "v6_fields": {
            "audience": enriched.audience,
            "scene": enriched.scene,
            "pain_point": enriched.pain_point,
            "hook": enriched.hook,
            "selling_points": enriched.selling_points,
            "card_status": enriched.card_status,
        },
    }


@router.post("/v6/score/{opportunity_id}")
@_handle_flow_error
async def v6_score(opportunity_id: str) -> dict[str, Any]:
    """生成 ExpertScorecard。"""
    from apps.content_planning.services.expert_scorer import ExpertScorer

    flow = _get_flow()
    card = flow._adapter.get_card(opportunity_id)
    if card is None:
        raise HTTPException(status_code=404, detail="机会卡未找到")
    source_notes = flow._adapter.get_source_notes(card.source_note_ids)
    note_ctx = source_notes[0] if source_notes else {}
    eng = note_ctx.get("note_context", {})

    scorer = ExpertScorer()
    scorecard = scorer.score(card, eng)
    flow._store.save_scorecard(scorecard)
    return {
        "opportunity_id": opportunity_id,
        "scorecard": scorecard.model_dump(mode="json"),
    }


@router.get("/v6/scorecard/{opportunity_id}")
@_handle_flow_error
async def v6_get_scorecard(opportunity_id: str) -> dict[str, Any]:
    """获取 scorecard。"""
    flow = _get_flow()
    scorecards = flow._store.load_scorecards_by_opportunity(opportunity_id, limit=1)
    if not scorecards:
        return {"opportunity_id": opportunity_id, "scorecard": None}
    return {
        "opportunity_id": opportunity_id,
        "scorecard": scorecards[0],
    }


@router.post("/v6/compile-brief/{opportunity_id}")
@_handle_flow_error
async def v6_compile_brief(opportunity_id: str) -> dict[str, Any]:
    """基于 scorecard 编译 production-ready brief。"""
    from apps.content_planning.schemas.expert_scorecard import ExpertScorecard

    flow = _get_flow()
    card = flow._adapter.get_card(opportunity_id)
    if card is None:
        raise HTTPException(status_code=404, detail="机会卡未找到")

    scorecards = flow._store.load_scorecards_by_opportunity(opportunity_id, limit=1)
    scorecard_obj = None
    if scorecards:
        try:
            scorecard_obj = ExpertScorecard(**scorecards[0])
        except Exception:
            pass

    source_notes = flow._adapter.get_source_notes(card.source_note_ids)
    parsed = source_notes[0] if source_notes else None
    review_summary = flow._adapter.get_review_summary(opportunity_id)
    brief = flow._brief_compiler.compile(card, parsed, review_summary, scorecard=scorecard_obj)

    flow._store.save_session(opportunity_id, brief=brief, session_status="generated")

    return {
        "opportunity_id": opportunity_id,
        "brief": brief.model_dump(mode="json"),
        "scorecard_applied": scorecard_obj is not None,
        "production_readiness_status": brief.production_readiness_status,
    }


@router.post("/v6/run-pipeline/{opportunity_id}")
@_handle_flow_error
async def v6_run_pipeline(opportunity_id: str) -> dict[str, Any]:
    """一键全链路：ingest eval -> enrich -> score -> brief。"""
    from apps.content_planning.services.note_to_card_flow import NoteToCardFlow
    from apps.content_planning.schemas.expert_scorecard import ExpertScorecard

    flow = _get_flow()
    card = flow._adapter.get_card(opportunity_id)
    if card is None:
        raise HTTPException(status_code=404, detail="机会卡未找到")

    source_notes = flow._adapter.get_source_notes(card.source_note_ids)
    note_ctx = source_notes[0] if source_notes else {}

    n2c = NoteToCardFlow()
    pipeline_result = n2c.run(card, parsed_note=note_ctx, auto_promote=True)

    if flow._store is not None:
        for gate in pipeline_result.gates:
            if gate.evaluation:
                ev = gate.evaluation
                flow._store.save_evaluation(
                    ev.evaluation_id, opportunity_id, gate.stage,
                    ev.model_dump(mode="json"),
                )

    brief = None
    brief_eval = None
    scorecard_applied = False
    if not pipeline_result.blocked and pipeline_result.scorecard:
        sc = pipeline_result.scorecard
        flow._store.save_scorecard(sc)

        if sc.recommendation in ("evaluate", "initiate"):
            review_summary = flow._adapter.get_review_summary(opportunity_id)
            brief = flow._brief_compiler.compile(card, note_ctx, review_summary, scorecard=sc)
            flow._store.save_session(opportunity_id, brief=brief, session_status="generated")
            scorecard_applied = True

            brief_eval = evaluate_stage("brief", opportunity_id, {
                "brief": brief.model_dump(),
                "scorecard": sc.model_dump(),
            })
            if flow._store is not None:
                flow._store.save_evaluation(
                    brief_eval.evaluation_id, opportunity_id, "brief",
                    brief_eval.model_dump(mode="json"),
                )

    return {
        "opportunity_id": opportunity_id,
        "blocked": pipeline_result.blocked,
        "block_reason": pipeline_result.block_reason,
        "promoted": pipeline_result.promoted,
        "gates": [g.model_dump(mode="json") for g in pipeline_result.gates],
        "scorecard": pipeline_result.scorecard.model_dump(mode="json") if pipeline_result.scorecard else None,
        "brief": brief.model_dump(mode="json") if brief else None,
        "brief_evaluation": brief_eval.model_dump(mode="json") if brief_eval else None,
        "scorecard_applied": scorecard_applied,
    }


@router.get("/v6/pipeline-status/{opportunity_id}")
@_handle_flow_error
async def v6_pipeline_status(opportunity_id: str) -> dict[str, Any]:
    """链路状态与各阶段 eval 结果。"""
    flow = _get_flow()
    scorecards = flow._store.load_scorecards_by_opportunity(opportunity_id, limit=1)
    session = flow._store.load_session(opportunity_id)
    evaluations = flow._store.load_evaluations(opportunity_id, limit=10)

    stage_evals: dict[str, Any] = {}
    for ev in evaluations:
        payload = ev.get("payload", {})
        if isinstance(payload, dict):
            stage = payload.get("stage", ev.get("eval_type", ""))
            if stage:
                stage_evals[stage] = payload

    has_brief = session is not None and session.get("brief") is not None
    has_scorecard = len(scorecards) > 0
    recommendation = scorecards[0].get("recommendation", "") if scorecards else ""

    return {
        "opportunity_id": opportunity_id,
        "has_scorecard": has_scorecard,
        "has_brief": has_brief,
        "recommendation": recommendation,
        "scorecard_summary": {
            "total_score": scorecards[0].get("total_score", 0) if scorecards else 0,
            "confidence": scorecards[0].get("confidence", 0) if scorecards else 0,
            "recommendation": recommendation,
        } if scorecards else None,
        "stage_evaluations": stage_evals,
    }


@router.post("/v6/quick-draft/{opportunity_id}")
@_handle_flow_error
async def v6_quick_draft(opportunity_id: str) -> dict[str, Any]:
    """从 V6 Brief + Scorecard 快速生成笔记草稿。"""
    from apps.content_planning.services.quick_draft_generator import QuickDraftGenerator
    from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
    from apps.content_planning.schemas.expert_scorecard import ExpertScorecard

    flow = _get_flow()
    card = flow._adapter.get_card(opportunity_id)

    session = flow._store.load_session(opportunity_id) if flow._store else None
    brief_raw = session.get("brief") if session else None
    if not isinstance(brief_raw, dict):
        raise HTTPException(status_code=400, detail="Brief 尚未生成，请先完成策划")
    try:
        brief = OpportunityBrief(**brief_raw)
    except Exception as exc:
        logger.warning("Brief validation failed for %s: %s", opportunity_id, exc)
        raise HTTPException(status_code=400, detail=f"Brief 数据格式异常: {exc}") from exc

    scorecard_obj = None
    if flow._store:
        sc_rows = flow._store.load_scorecards_by_opportunity(opportunity_id, limit=1)
        if sc_rows:
            try:
                scorecard_obj = ExpertScorecard(**sc_rows[0])
            except Exception:
                pass

    gen = QuickDraftGenerator()
    draft = gen.generate(brief, scorecard=scorecard_obj, card=card)

    if flow._store:
        flow._store.update_field(opportunity_id, "quick_draft", draft)

    return {
        "opportunity_id": opportunity_id,
        "draft": draft,
    }


@router.get("/v6/quick-draft/{opportunity_id}")
@_handle_flow_error
async def v6_get_quick_draft(opportunity_id: str) -> dict[str, Any]:
    """获取已生成的笔记草稿。"""
    flow = _get_flow()
    session = flow._store.load_session(opportunity_id) if flow._store else None
    draft = session.get("quick_draft") if session else None
    return {
        "opportunity_id": opportunity_id,
        "draft": draft,
    }


# ── 图片生成端点 ──────────────────────────────────────────────────────

_image_gen_tasks: dict[str, dict[str, Any]] = {}


class ImageGenRequest(BaseModel):
    provider: str = "auto"


def _build_rich_prompts(
    opportunity_id: str,
    session: dict[str, Any] | None,
    gen_mode: str = "prompt_only",
) -> tuple[list["RichImagePrompt"], list[str]]:
    """从 session 加载全链路数据，融合为 RichImagePrompt 列表。返回 (prompts, ref_urls)。"""
    from apps.content_planning.services.prompt_composer import compose_image_prompts
    from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
    from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
    from apps.content_planning.schemas.note_plan import NewNotePlan
    from apps.content_planning.schemas.content_generation import ImageSlotBrief

    draft = session.get("quick_draft") if session else None
    if not draft:
        raise HTTPException(status_code=400, detail="请先生成笔记草稿")

    brief = None
    brief_raw = session.get("brief") if session else None
    if isinstance(brief_raw, dict):
        try:
            brief = OpportunityBrief(**brief_raw)
        except Exception:
            pass

    strategy = None
    strat_raw = session.get("strategy") if session else None
    if isinstance(strat_raw, dict):
        try:
            strategy = RewriteStrategy(**strat_raw)
        except Exception:
            pass
    elif isinstance(strat_raw, list) and strat_raw:
        try:
            strategy = RewriteStrategy(**strat_raw[-1])
        except Exception:
            pass

    note_plan = None
    plan_raw = session.get("plan") if session else None
    if isinstance(plan_raw, dict):
        try:
            note_plan = NewNotePlan(**plan_raw)
        except Exception:
            pass

    image_briefs_list: list[ImageSlotBrief] = []
    ib_raw = session.get("image_briefs") if session else None
    if isinstance(ib_raw, dict):
        slots_raw = ib_raw.get("slot_briefs", [])
        for sb in (slots_raw or []):
            if isinstance(sb, dict):
                try:
                    image_briefs_list.append(ImageSlotBrief(**sb))
                except Exception:
                    pass
    elif isinstance(ib_raw, list):
        for sb in ib_raw:
            if isinstance(sb, dict):
                try:
                    image_briefs_list.append(ImageSlotBrief(**sb))
                except Exception:
                    pass

    match_result = session.get("match_result") if session else None

    ref_image_urls: list[str] = []
    if gen_mode == "ref_image":
        try:
            from apps.content_planning.adapters.intel_hub_adapter import IntelHubAdapter
            adapter = IntelHubAdapter()
            card = session.get("card") if session else None
            note_ids = card.get("source_note_ids", []) if isinstance(card, dict) else []
            if not note_ids:
                note_ids = [opportunity_id]
            notes = adapter.get_source_notes(note_ids)
            for n in notes:
                ctx = n.get("note_context", n)
                cover = ctx.get("cover_image", "")
                if cover:
                    ref_image_urls.append(cover)
                for img in ctx.get("image_urls", []):
                    if img and img != cover:
                        ref_image_urls.append(img)
        except Exception as e:
            logger.warning("获取参考图失败, 降级为纯提示词模式: %s", e)

    gen_history_raw = session.get("generated_images") if session else None
    gen_history: list[dict[str, Any]] = []
    if isinstance(gen_history_raw, list):
        for item in gen_history_raw:
            if isinstance(item, dict) and "timestamp" in item:
                gen_history.append(item)

    rich = compose_image_prompts(
        draft=draft,
        brief=brief,
        strategy=strategy,
        note_plan=note_plan,
        image_briefs=image_briefs_list or None,
        match_result=match_result,
        ref_image_urls=ref_image_urls if gen_mode == "ref_image" else None,
        generated_images_history=gen_history or None,
    )
    return rich, ref_image_urls


@router.post("/v6/image-gen/{opportunity_id}/preview-prompts")
@_handle_flow_error
async def v6_preview_prompts(opportunity_id: str, request: Request) -> dict[str, Any]:
    """预览即将发送的图片 prompt（不触发生图），供 Prompt Builder 展示 + 编辑。"""
    gen_mode = "prompt_only"
    try:
        body = await request.json()
        if isinstance(body, dict):
            gen_mode = body.get("gen_mode", "prompt_only")
    except Exception:
        pass

    flow = _get_flow()
    session = flow._store.load_session(opportunity_id) if flow._store else None

    saved = session.get("saved_prompts") if session else None
    if saved and isinstance(saved, list) and len(saved) > 0:
        return {
            "opportunity_id": opportunity_id,
            "gen_mode": gen_mode,
            "ref_images_count": 0,
            "source": "saved",
            "prompts": saved,
        }

    rich_prompts, ref_urls = _build_rich_prompts(opportunity_id, session, gen_mode)

    if not rich_prompts:
        raise HTTPException(status_code=400, detail="未找到可生成的图片描述")

    gen_history_raw = session.get("generated_images") if session else None
    pref_count = 0
    if isinstance(gen_history_raw, list):
        pref_count = sum(
            1 for r in gen_history_raw
            if isinstance(r, dict) and r.get("user_edited") and any(
                res.get("rating") == "good" for res in r.get("results", []) if isinstance(res, dict)
            )
        )

    return {
        "opportunity_id": opportunity_id,
        "gen_mode": gen_mode,
        "ref_images_count": len(ref_urls),
        "source": "composed",
        "preferences_applied": pref_count,
        "prompts": [p.model_dump() for p in rich_prompts],
    }


@router.post("/v6/image-gen/{opportunity_id}/save-prompts")
@_handle_flow_error
async def v6_save_prompts(opportunity_id: str, request: Request) -> dict[str, Any]:
    """保存用户编辑后的结构化 prompt 以便下次复用。"""
    body = await request.json()
    prompts = body.get("prompts")
    if not prompts or not isinstance(prompts, list):
        raise HTTPException(status_code=400, detail="缺少 prompts 数据")

    flow = _get_flow()
    if flow._store:
        flow._store.update_field(opportunity_id, "saved_prompts", prompts)

    return {"status": "saved", "count": len(prompts)}


@router.post("/v6/image-gen/{opportunity_id}")
@_handle_flow_error
async def v6_start_image_gen(opportunity_id: str, request: Request) -> dict[str, Any]:
    """启动后台图片生成任务。支持 edited_prompts 覆盖融合结果。"""
    import threading
    import uuid as _uuid
    from apps.content_planning.services.image_generator import (
        ImageGeneratorService,
        ImagePrompt,
        RichImagePrompt,
    )

    provider = "auto"
    gen_mode = "prompt_only"
    edited_prompts: list[dict[str, Any]] | None = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            provider = body.get("provider", "auto")
            gen_mode = body.get("gen_mode", "prompt_only")
            edited_prompts = body.get("edited_prompts")
    except Exception:
        pass

    flow = _get_flow()
    session = flow._store.load_session(opportunity_id) if flow._store else None
    draft = session.get("quick_draft") if session else None
    if not draft:
        raise HTTPException(status_code=400, detail="请先生成笔记草稿")

    rich_prompts, ref_image_urls = _build_rich_prompts(opportunity_id, session, gen_mode)

    if edited_prompts and isinstance(edited_prompts, list):
        edit_map = {ep["slot_id"]: ep for ep in edited_prompts if isinstance(ep, dict) and "slot_id" in ep}
        for rp in rich_prompts:
            if rp.slot_id in edit_map:
                ep = edit_map[rp.slot_id]
                if "subject" in ep:
                    rp.subject = ep["subject"]
                if "prompt_text" in ep:
                    rp.prompt_text = ep["prompt_text"]
                if "negative_prompt" in ep:
                    rp.negative_prompt = ep["negative_prompt"]
                if "style_tags" in ep and isinstance(ep["style_tags"], list):
                    rp.style_tags = ep["style_tags"]
                if "must_include" in ep and isinstance(ep["must_include"], list):
                    rp.must_include = ep["must_include"]
                if "avoid_items" in ep and isinstance(ep["avoid_items"], list):
                    rp.avoid_items = ep["avoid_items"]

    prompts = [rp.to_image_prompt() for rp in rich_prompts]
    if not prompts:
        raise HTTPException(status_code=400, detail="未找到可生成的图片描述")

    user_edited = bool(edited_prompts)
    prompt_log = [
        {
            "slot_id": rp.slot_id,
            "final_prompt": rp.compose_prompt_text() or rp.prompt_text,
            "final_negative": rp.negative_prompt,
            "subject": rp.subject,
            "style_tags": rp.style_tags,
            "must_include": rp.must_include,
            "avoid_items": rp.avoid_items,
            "sources": [s.model_dump() for s in rp.sources],
            "has_ref": bool(rp.ref_image_url),
            "user_edited": user_edited,
        }
        for rp in rich_prompts
    ]

    svc = ImageGeneratorService()
    if not svc.is_available():
        raise HTTPException(status_code=503, detail="图片生成服务不可用（缺少 API Key 或 SDK）")

    task_id = _uuid.uuid4().hex[:12]
    task_state: dict[str, Any] = {
        "task_id": task_id,
        "opportunity_id": opportunity_id,
        "total": len(prompts),
        "completed": 0,
        "results": [],
        "status": "running",
    }
    _image_gen_tasks[task_id] = task_state

    def _on_progress(slot_id: str, status: str, data: dict[str, Any]) -> None:
        from apps.content_planning.gateway.event_bus import event_bus, ObjectEvent
        event_bus.publish_sync(ObjectEvent(
            event_type="image_gen_progress",
            opportunity_id=opportunity_id,
            payload={"task_id": task_id, "slot_id": slot_id, "status": status, **data},
        ))

    def _run() -> None:
        try:
            results = svc.generate_batch(prompts, opportunity_id, on_progress=_on_progress, provider=provider)
            for r, rp in zip(results, rich_prompts):
                r.final_prompt = rp.prompt_text
                r.final_negative_prompt = rp.negative_prompt
                r.gen_mode = gen_mode
                r.user_edited = user_edited
            task_state["results"] = [r.model_dump() for r in results]
            task_state["completed"] = sum(1 for r in results if r.status == "completed")
            task_state["status"] = "done"

            gen_record = {
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "task_id": task_id,
                "provider": provider,
                "gen_mode": gen_mode,
                "user_edited": user_edited,
                "prompt_log": prompt_log,
                "results": task_state["results"],
            }

            images_data = [r.model_dump() for r in results if r.status == "completed"]
            if flow._store:
                existing_history = []
                try:
                    prev = flow._store.load_session(opportunity_id)
                    if prev and isinstance(prev.get("generated_images"), list):
                        for item in prev["generated_images"]:
                            if isinstance(item, dict) and "timestamp" in item:
                                existing_history.append(item)
                except Exception:
                    pass
                existing_history.append(gen_record)
                flow._store.update_field(opportunity_id, "generated_images", existing_history)
                existing_draft = draft.copy() if draft else {}
                existing_draft["images"] = images_data
                flow._store.update_field(opportunity_id, "quick_draft", existing_draft)

            from apps.content_planning.gateway.event_bus import event_bus, ObjectEvent
            event_bus.publish_sync(ObjectEvent(
                event_type="image_gen_complete",
                opportunity_id=opportunity_id,
                payload={
                    "task_id": task_id,
                    "total": len(prompts),
                    "completed": task_state["completed"],
                    "results": task_state["results"],
                },
            ))
        except Exception as exc:
            logger.error("Image gen task %s failed: %s", task_id, exc, exc_info=True)
            task_state["status"] = "failed"
            task_state["error"] = str(exc)

    thread = threading.Thread(target=_run, daemon=True, name=f"image-gen-{task_id}")
    thread.start()

    return {
        "task_id": task_id,
        "opportunity_id": opportunity_id,
        "total_images": len(prompts),
        "prompts": [{"slot_id": p.slot_id, "prompt": p.prompt[:80], "has_ref": bool(p.ref_image_url)} for p in prompts],
        "provider": provider,
        "gen_mode": gen_mode,
        "ref_images_count": len(ref_image_urls),
        "status": "started",
    }


@router.get("/v6/image-gen/{opportunity_id}/status")
@_handle_flow_error
async def v6_image_gen_status(opportunity_id: str) -> dict[str, Any]:
    """查询图片生成状态（含最近一轮结果）。"""
    matching = [t for t in _image_gen_tasks.values() if t["opportunity_id"] == opportunity_id]
    if not matching:
        flow = _get_flow()
        session = flow._store.load_session(opportunity_id) if flow._store else None
        raw = session.get("generated_images") if session else None
        if isinstance(raw, list) and raw:
            if isinstance(raw[-1], dict) and "timestamp" in raw[-1]:
                latest = raw[-1]
                return {
                    "opportunity_id": opportunity_id,
                    "status": "done",
                    "results": latest.get("results", []),
                    "history_count": len(raw),
                }
            if isinstance(raw[0], dict) and "slot_id" in raw[0]:
                return {
                    "opportunity_id": opportunity_id,
                    "status": "done",
                    "results": raw,
                    "history_count": 0,
                }
        return {
            "opportunity_id": opportunity_id,
            "status": "idle",
            "results": [],
        }
    task = matching[-1]
    return {
        "opportunity_id": opportunity_id,
        "task_id": task["task_id"],
        "status": task["status"],
        "total": task.get("total", 0),
        "completed": task.get("completed", 0),
        "results": task.get("results", []),
        "error": task.get("error", ""),
    }


@router.get("/v6/image-gen/{opportunity_id}/history")
@_handle_flow_error
async def v6_image_gen_history(opportunity_id: str) -> dict[str, Any]:
    """返回完整的图片生成历史（含每轮 prompt_log + results）。"""
    flow = _get_flow()
    session = flow._store.load_session(opportunity_id) if flow._store else None
    raw = session.get("generated_images") if session else None
    history: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "timestamp" in item:
                history.append(item)
    return {
        "opportunity_id": opportunity_id,
        "total_rounds": len(history),
        "history": history,
    }


@router.post("/v6/image-gen/{opportunity_id}/optimize-prompt")
@_handle_flow_error
async def v6_optimize_prompt(opportunity_id: str, request: Request) -> dict[str, Any]:
    """用 LLM 优化一个 slot 的结构化 prompt。"""
    body = await request.json()
    slot_data = body.get("prompt")
    if not slot_data or not isinstance(slot_data, dict):
        raise HTTPException(status_code=400, detail="缺少 prompt 数据")

    from apps.content_planning.skills.prompt_optimizer import optimize_prompt
    result = await optimize_prompt(slot_data)
    return {"slot_id": slot_data.get("slot_id", ""), "result": result}


@router.post("/v6/image-gen/{opportunity_id}/feedback")
@_handle_flow_error
async def v6_image_gen_feedback(opportunity_id: str, request: Request) -> dict[str, Any]:
    """对某轮某张生成图进行评价（good/ok/bad）。"""
    body = await request.json()
    round_idx = body.get("round_idx")
    slot_id = body.get("slot_id")
    rating = body.get("rating")
    if round_idx is None or not slot_id or rating not in ("good", "ok", "bad"):
        raise HTTPException(status_code=400, detail="需要 round_idx, slot_id, rating(good/ok/bad)")

    flow = _get_flow()
    session = flow._store.load_session(opportunity_id) if flow._store else None
    raw = session.get("generated_images") if session else None
    if not isinstance(raw, list):
        raise HTTPException(status_code=404, detail="未找到生成历史")

    history = [item for item in raw if isinstance(item, dict) and "timestamp" in item]
    if round_idx < 0 or round_idx >= len(history):
        raise HTTPException(status_code=400, detail="round_idx 越界")

    record = history[round_idx]
    for r in record.get("results", []):
        if r.get("slot_id") == slot_id:
            r["rating"] = rating
            break

    if flow._store:
        flow._store.update_field(opportunity_id, "generated_images", raw)
    return {"status": "ok", "round_idx": round_idx, "slot_id": slot_id, "rating": rating}


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

    flow = _get_flow()
    _Perf = Literal["excellent", "good", "average", "poor", "unknown"]
    allowed: tuple[str, ...] = ("excellent", "good", "average", "poor", "unknown")
    label_raw = body.performance_label if body.performance_label in allowed else "unknown"
    label = cast(_Perf, label_raw)

    session = flow._store.load_session(asset_bundle_id) or {}
    opp_id = session.get("opportunity_id", "")
    result = PublishedAssetResult(
        asset_bundle_id=asset_bundle_id,
        opportunity_id=opp_id,
        published_note_id=body.published_note_id,
        like_count=body.like_count,
        collect_count=body.collect_count,
        comment_count=body.comment_count,
        share_count=body.share_count,
        view_count=body.view_count,
        performance_label=label,
        feedback_notes=body.feedback_notes,
    )

    from apps.content_planning.schemas.feedback import FeedbackRecord
    total_eng = body.like_count + body.collect_count + body.comment_count + body.share_count
    fb = FeedbackRecord(
        opportunity_id=opp_id,
        asset_bundle_id=asset_bundle_id,
        workspace_id=session.get("workspace_id", ""),
        brand_id=session.get("brand_id", ""),
        campaign_id=session.get("campaign_id", ""),
        engagement_proxy=min(total_eng / 1000.0, 1.0) if total_eng else 0.0,
        feedback_quality=label,
        notes=body.feedback_notes,
    )
    flow._store.save_feedback_record(fb)

    return {
        "status": "received",
        "result_id": result.result_id,
        "asset_bundle_id": asset_bundle_id,
        "performance_label": result.performance_label,
        "feedback_id": fb.feedback_id,
    }


# ---------------------------------------------------------------------------
# Phase 1: 发布结果闭环 API
# ---------------------------------------------------------------------------


class PublishResultRequest(BaseModel):
    platform: str = "xhs"
    external_ref: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    performance_label: str = "unknown"
    feedback_notes: str = ""


def _metric_int(metrics: dict[str, Any], key: str) -> int:
    raw = metrics.get(key, 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


@router.post("/asset-bundle/{opportunity_id}/publish-result")
@_handle_flow_error
async def record_publish_result(opportunity_id: str, body: PublishResultRequest) -> dict[str, Any]:
    """录入发布结果，关联到对象版本。"""
    flow = _get_flow()
    session = flow._store.load_session(opportunity_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    bundle_json = session.get("asset_bundle_json")
    bundle = json.loads(bundle_json) if bundle_json else {}

    platform_store = getattr(flow, "_platform_store", None)
    if platform_store is None:
        raise HTTPException(status_code=501, detail="platform_store not available")

    asset_bundle_id = bundle.get("asset_bundle_id", opportunity_id)
    pub = platform_store.record_publish_result(
        workspace_id=session.get("workspace_id", ""),
        brand_id=session.get("brand_id", ""),
        campaign_id=session.get("campaign_id", ""),
        asset_bundle_id=asset_bundle_id,
        opportunity_id=opportunity_id,
        brief_version=session.get("version", 1),
        strategy_version=bundle.get("version", 1),
        plan_version=session.get("version", 1),
        asset_bundle_version=bundle.get("version", 1),
        platform=body.platform,
        external_ref=body.external_ref,
        metrics=body.metrics,
    )

    # 同步写入反馈记录，供 outcome-summary 聚合 avg_engagement_proxy 等
    from apps.content_planning.schemas.feedback import FeedbackRecord

    _Perf = Literal["excellent", "good", "average", "poor", "unknown"]
    allowed: tuple[str, ...] = ("excellent", "good", "average", "poor", "unknown")
    label_raw = body.performance_label if body.performance_label in allowed else "unknown"
    label = cast(_Perf, label_raw)
    m = body.metrics or {}
    like_c = _metric_int(m, "like_count")
    collect_c = _metric_int(m, "collect_count")
    comment_c = _metric_int(m, "comment_count")
    share_c = _metric_int(m, "share_count")
    view_c = _metric_int(m, "view_count")
    total_eng = like_c + collect_c + comment_c + share_c
    fb = FeedbackRecord(
        opportunity_id=opportunity_id,
        asset_bundle_id=asset_bundle_id,
        workspace_id=session.get("workspace_id", ""),
        brand_id=session.get("brand_id", ""),
        campaign_id=session.get("campaign_id", ""),
        engagement_proxy=min(total_eng / 1000.0, 1.0) if total_eng else 0.0,
        feedback_quality=label,
        notes=body.feedback_notes or body.external_ref or "",
    )
    flow._store.save_feedback_record(fb)

    out = pub.model_dump(mode="json")
    out["feedback_id"] = fb.feedback_id
    return out


@router.get("/opportunities/{opportunity_id}/outcome-summary")
@_handle_flow_error
async def outcome_summary(opportunity_id: str) -> dict[str, Any]:
    """聚合该机会下所有 publish results + feedback 的结果摘要。"""
    flow = _get_flow()
    platform_store = getattr(flow, "_platform_store", None)

    publish_results: list[dict[str, Any]] = []
    if platform_store:
        prs = platform_store.list_publish_results(opportunity_id=opportunity_id)
        publish_results = [p.model_dump(mode="json") for p in prs]

    feedback_records = flow._store.load_feedback_records(opportunity_id=opportunity_id)
    evaluations = flow._store.load_evaluations(opportunity_id)

    total_pubs = len(publish_results)
    avg_engagement = 0.0
    if feedback_records:
        engs = [float(fr.get("engagement_proxy") or 0.0) for fr in feedback_records]
        avg_engagement = sum(engs) / len(engs) if engs else 0.0

    return {
        "opportunity_id": opportunity_id,
        "total_publish_results": total_pubs,
        "publish_results": publish_results,
        "feedback_records": feedback_records,
        "avg_engagement_proxy": round(avg_engagement, 4),
        "evaluations_count": len(evaluations),
    }


@router.get("/comparison/{opportunity_id}/outcome-delta")
@_handle_flow_error
async def outcome_delta(opportunity_id: str) -> dict[str, Any]:
    """含 outcome 的双层对比。"""
    flow = _get_flow()
    from apps.content_planning.evaluation.comparison import compare, OutcomeDelta

    evals = flow._store.load_evaluations(opportunity_id)
    baseline_eval = None
    upgrade_eval = None
    for ev in evals:
        if ev.get("eval_type") == "baseline":
            baseline_eval = ev
        elif ev.get("eval_type") in ("pipeline", "stage_run", "comparison"):
            upgrade_eval = ev

    baseline_pe = None
    upgrade_pe = None
    if baseline_eval and baseline_eval.get("payload"):
        try:
            baseline_pe = PipelineEvaluation.model_validate(baseline_eval["payload"])
        except Exception:
            pass
    if upgrade_eval and upgrade_eval.get("payload"):
        try:
            upgrade_pe = PipelineEvaluation.model_validate(upgrade_eval["payload"])
        except Exception:
            pass

    report = compare(opportunity_id, baseline=baseline_pe, upgrade=upgrade_pe)

    feedback = flow._store.load_feedback_records(opportunity_id=opportunity_id)
    if feedback:
        engs = [fr.get("engagement_proxy", 0.0) for fr in feedback]
        avg_eng = sum(engs) / len(engs) if engs else 0.0
        report.outcome = OutcomeDelta(
            engagement_after=round(avg_eng, 4),
            outcome_improved=avg_eng > 0.3,
        )

    return report.model_dump(mode="json")


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
    notes: str | None = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            raw = body.get("council_escalation_notes") or body.get("council_notes")
            if raw:
                notes = str(raw).strip() or None
    except Exception:
        notes = None
    return flow.build_brief(opportunity_id, council_escalation_notes=notes).model_dump(mode="json")


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


def _proposal_diff_from_rows(diff_rows: list[dict[str, Any]]) -> ProposalDiff:
    return ProposalDiff(
        changes=[
            ProposalFieldChange(
                field=r["field"],
                before=r["before"],
                after=r["after"],
                blocked=r["blocked"],
                change_type="modify",
                confidence=0.0,
                reason="",
            )
            for r in diff_rows
        ]
    )


def _enrich_alternatives(alts: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in alts:
        out.append(
            {
                "alternative_id": new_alternative_id(),
                "label": str(a.get("label") or ""),
                "summary": str(a.get("summary") or ""),
                "description": str(a.get("summary") or ""),
            }
        )
    return out


def _build_fallback_action_payload(
    council_dt: str,
    applyability: str,
    consensus: str,
) -> dict[str, Any]:
    if council_dt == "applyable" and applyability == "direct":
        return {}
    return {
        "type": "apply_as_draft",
        "target_field": "competitive_angle",
        "content": (consensus or "")[:2000],
    }


def _build_council_observability(run_id: str, round_data: DiscussionRound) -> CouncilObservability:
    agents: list[CouncilAgentObs] = []
    for msg in round_data.messages:
        if msg.role != "agent":
            continue
        m = msg.metadata or {}
        if m.get("status") == "failed":
            agents.append(
                CouncilAgentObs(
                    agent_id=msg.agent_role,
                    used_llm=bool(m.get("used_llm", False)),
                    degraded=True,
                    model="",
                    timing_ms=int(m.get("timing_ms") or 0),
                )
            )
            continue
        agents.append(
            CouncilAgentObs(
                agent_id=msg.agent_role,
                used_llm=bool(m.get("used_llm", False)),
                degraded=bool(m.get("degraded", False)),
                model=str(m.get("model") or ""),
                timing_ms=int(m.get("timing_ms") or 0),
            )
        )
    return CouncilObservability(
        trace_id=run_id,
        session_id=run_id,
        model_summary=CouncilModelSummary(
            llm_available=llm_router.is_any_available(),
        ),
        agents=agents,
        synthesis=CouncilSynthesisObs(
            used_llm=round_data.synthesis_used_llm,
            degraded=round_data.synthesis_degraded,
            timing_ms=round_data.synthesis_timing_ms,
        ),
    )


def _format_chat_context_for_council(opportunity_id: str, *, max_chars: int = 2400) -> str:
    """将同 opportunity 的 Conversation 线程摘要拼入 Council 问题前（链式上下文）。"""
    thread: AgentThread | None = _agent_threads.get(opportunity_id)
    if not thread or not thread.messages:
        return ""
    summary = thread.context_summary()
    if not summary.strip():
        return ""
    if len(summary) > max_chars:
        summary = summary[-max_chars:]
    return f"[Conversation 前序]\n{summary}\n\n"


async def _run_stage_discussion(
    opportunity_id: str,
    stage: str,
    question: str,
    run_mode: str = "agent_assisted_council",
    *,
    parent_discussion_id: str = "",
    target_sub_object_type: str = "",
    include_chat_context: bool = True,
) -> dict[str, Any]:
    total_t0 = time.perf_counter()
    context_t0 = time.perf_counter()
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")

    normalized_stage = _normalize_stage(stage)
    snapshot = flow.get_stage_snapshot(opportunity_id, normalized_stage)
    session = flow._get_session(opportunity_id)

    discussion_question = question
    if parent_discussion_id:
        parent = flow._store.load_discussion(parent_discussion_id)
        if parent:
            summ = (parent.get("summary") or "")[:500]
            discussion_question = (
                f"[Follow-up · 前置讨论 {parent_discussion_id}]\n前置摘要：{summ}\n\n用户追问：{question}"
            )
    elif include_chat_context:
        prefix = _format_chat_context_for_council(opportunity_id)
        if prefix:
            discussion_question = prefix + f"[Council 当前问题]\n{question}"

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
        payload={
            "question": question,
            "base_version": snapshot["version"],
            "parent_discussion_id": parent_discussion_id,
            "target_sub_object_type": target_sub_object_type,
        },
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

    def _on_phase(phase: str, payload: dict[str, Any]) -> None:
        event_bus.publish_sync(ObjectEvent(
            event_type="council_phase",
            opportunity_id=opportunity_id,
            object_type="discussion",
            object_id=run.run_id,
            agent_role="council",
            agent_name=str(payload.get("label_zh") or ""),
            payload={"phase": phase, **payload},
        ))

    def _on_council_event(event_name: str, data: dict[str, Any]) -> None:
        event_bus.publish_sync(
            ObjectEvent(
                event_type=event_name,
                opportunity_id=opportunity_id,
                object_type="discussion",
                object_id=run.run_id,
                agent_role="council",
                agent_name="",
                payload={"event_version": 2, **data},
            )
        )

    try:
        council_started_at = datetime.now(UTC)
        discussion_t0 = time.perf_counter()
        discussion_mode = "fast" if run_mode == "agent_assisted_single" else "deep"
        _disc_ctx = _build_agent_context(
            flow,
            opportunity_id,
            normalized_stage,
            include_deep_context=discussion_mode == "deep",
        )

        import asyncio as _aio
        import functools as _ft
        _loop = _aio.get_running_loop()
        round_data = await _loop.run_in_executor(
            None,
            _ft.partial(
                orchestrator.discuss,
                opportunity_id=opportunity_id,
                stage=normalized_stage,
                user_question=discussion_question,
                context=_disc_ctx,
                on_message=_on_message,
                on_phase=_on_phase,
                on_council_event=_on_council_event,
                council_session_id=run.run_id,
                mode=cast(Literal["fast", "deep"], discussion_mode),
            ),
        )
        discussion_ms = int((time.perf_counter() - discussion_t0) * 1000)
        specialists_ms = sum(round_data.specialist_timings_ms.values())
        synthesis_ms = round_data.synthesis_timing_ms
        diff_rows, blocked_fields = flow.build_stage_diff(opportunity_id, normalized_stage, round_data.proposed_updates)
        council_dt = reconcile_council_decision_type(
            diff_rows=diff_rows,
            disagreements=round_data.disagreements,
            open_questions=round_data.open_questions,
            model_decision_hint=round_data.model_decision_hint,
            disagreements_structured=round_data.disagreements_structured,
        )
        applyability = compute_applyability(diff_rows)
        consensus_body = round_data.consensus or ""
        exec_summary = round_data.executive_summary or consensus_body[:160]
        alts_enriched = _enrich_alternatives(round_data.alternatives)
        fb_action = _build_fallback_action_payload(str(council_dt), str(applyability), consensus_body)
        proposal = StageProposal(
            opportunity_id=opportunity_id,
            stage=normalized_stage,
            target_object_type=_STAGE_OBJECT_TYPES[normalized_stage],
            target_object_id=snapshot["object_id"],
            base_version=snapshot["version"],
            run_mode=cast(Literal["baseline_compiler", "agent_assisted_single", "agent_assisted_council"], run_mode),
            summary=exec_summary,
            proposed_updates=round_data.proposed_updates,
            diff=_proposal_diff_from_rows(diff_rows),
            blocked_fields=blocked_fields,
            requires_human_confirmation=True,
            confidence=round_data.overall_score,
            source_run_id=run.run_id,
            source_discussion_id=round_data.round_id,
            council_decision_type=council_dt,
            applyability=applyability,
            agreements=round_data.agreements,
            disagreements=round_data.disagreements,
            open_questions=round_data.open_questions,
            recommended_next_steps=round_data.recommended_next_steps,
            alternatives=alts_enriched,
            model_decision_hint=round_data.model_decision_hint,
            follow_up_of_discussion_id=parent_discussion_id,
            target_sub_object_type=target_sub_object_type,
            session_id=run.run_id,
            consensus_text=consensus_body,
            fallback_action=fb_action,
            strategy_block_diffs=round_data.strategy_block_diffs,
            plan_field_diffs=round_data.plan_field_diffs,
            asset_diffs=round_data.asset_diffs,
        )
        record = AgentDiscussionRecord(
            discussion_id=round_data.round_id,
            opportunity_id=opportunity_id,
            stage=normalized_stage,
            question=question,
            participants=round_data.participants,
            messages=[m.model_dump(mode="json") for m in round_data.messages],
            summary=exec_summary,
            proposal_id=proposal.proposal_id,
            run_id=run.run_id,
            base_version=snapshot["version"],
            status="completed",
            council_decision_type=council_dt,
            agreements=round_data.agreements,
            disagreements=round_data.disagreements,
            open_questions=round_data.open_questions,
            recommended_next_steps=round_data.recommended_next_steps,
            alternatives=alts_enriched,
            follow_up_of_discussion_id=parent_discussion_id,
            target_sub_object_type=target_sub_object_type,
            consensus=consensus_body,
            executive_summary=exec_summary,
            disagreements_structured=round_data.disagreements_structured,
            recommended_next_steps_items=round_data.recommended_steps_structured,
            confidence=round_data.overall_score,
        )
        run.status = "completed"
        run.participant_roles = round_data.participants
        run.summary = round_data.consensus or ""
        run.payload = {
            "participants": round_data.participants,
            "question": question,
            "proposal_id": proposal.proposal_id,
            "council_decision_type": council_dt,
        }
        persist_t0 = time.perf_counter()
        flow._store.save_agent_run(run.run_id, task.task_id, opportunity_id, normalized_stage, run_mode, run.status, run.model_dump(mode="json"))
        flow._store.save_proposal(proposal.proposal_id, opportunity_id, normalized_stage, proposal.status, proposal.model_dump(mode="json"))
        flow._store.save_discussion(record.discussion_id, opportunity_id, normalized_stage, proposal.proposal_id, run.run_id, record.model_dump(mode="json"))
        event_bus.publish_sync(
            ObjectEvent(
                event_type="council_proposal_ready",
                opportunity_id=opportunity_id,
                object_type="discussion",
                object_id=run.run_id,
                agent_role="council",
                agent_name="",
                payload={
                    "event_version": 2,
                    "session_id": run.run_id,
                    "proposal_id": proposal.proposal_id,
                    "discussion_id": record.discussion_id,
                    "council_decision_type": council_dt,
                    "applyability": applyability,
                },
            )
        )
        persist_ms = int((time.perf_counter() - persist_t0) * 1000)
        finished_at = datetime.now(UTC)
        observability = _build_council_observability(run.run_id, round_data)
        timing_total = int((time.perf_counter() - total_t0) * 1000)
        _council_soul = SoulLoader()
        council_session = CouncilSession(
            session_id=run.run_id,
            stage_type=normalized_stage,
            target_object_type=_STAGE_OBJECT_TYPES[normalized_stage],
            target_object_id=snapshot["object_id"],
            target_object_version=snapshot["version"],
            opportunity_id=opportunity_id,
            question=question,
            run_mode=run_mode,
            participants=[
                CouncilParticipantSpec(
                    agent_id=role,
                    display_name=AGENT_DISPLAY_NAMES.get(role, role),
                    role_type="specialist",
                    soul_tagline=_council_soul.tagline(role),
                )
                for role in round_data.participants
            ],
            status="completed",
            decision_type=str(council_dt),
            applyability=str(applyability),
            started_at=council_started_at,
            finished_at=finished_at,
            timing_ms=timing_total,
            timing_breakdown={
                "context_ms": context_ms,
                "specialists_ms": specialists_ms,
                "synthesis_ms": synthesis_ms,
                "discussion_ms": discussion_ms,
                "persist_ms": persist_ms,
            },
        )
        event_bus.publish_sync(
            ObjectEvent(
                event_type="council_session_completed",
                opportunity_id=opportunity_id,
                object_type="discussion",
                object_id=run.run_id,
                agent_role="council",
                agent_name="",
                payload={
                    "event_version": 2,
                    "session_id": run.run_id,
                    "proposal_id": proposal.proposal_id,
                    "discussion_id": record.discussion_id,
                    "timing_ms": timing_total,
                },
            )
        )
        return {
            "stage": normalized_stage,
            "task_id": task.task_id,
            "discussion_id": record.discussion_id,
            "proposal_id": proposal.proposal_id,
            "run_id": run.run_id,
            "session": council_session.model_dump(mode="json"),
            "discussion": record.model_dump(mode="json"),
            "proposal": proposal.model_dump(mode="json"),
            "observability": observability.model_dump(mode="json"),
            "council": {
                "decision_type": council_dt,
                "applyability": applyability,
            },
            **_timing_payload(
                total_t0,
                context_ms=context_ms,
                specialists_ms=specialists_ms,
                synthesis_ms=synthesis_ms,
                discussion_ms=discussion_ms,
                persist_ms=persist_ms,
            ),
        }
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        flow._store.save_agent_run(run.run_id, task.task_id, opportunity_id, normalized_stage, run_mode, run.status, run.model_dump(mode="json"))
        event_bus.publish_sync(
            ObjectEvent(
                event_type="council_session_failed",
                opportunity_id=opportunity_id,
                object_type="discussion",
                object_id=run.run_id,
                agent_role="council",
                agent_name="",
                payload={
                    "event_version": 2,
                    "session_id": run.run_id,
                    "failed_phase": "discussion_orchestration",
                    "error_message": str(exc)[:2000],
                },
            )
        )
        raise


@router.post("/discuss/{opportunity_id}")
@_handle_flow_error
async def start_discussion(opportunity_id: str, body: DiscussionRequest) -> dict[str, Any]:
    """兼容旧讨论入口。"""
    return await _run_stage_discussion(opportunity_id, body.stage or "brief", body.question)


@router.post("/stages/{stage}/{opportunity_id}/discussions")
@_handle_flow_error
async def start_stage_discussion(stage: str, opportunity_id: str, body: StageDiscussionRequest) -> dict[str, Any]:
    return await _run_stage_discussion(
        opportunity_id,
        stage,
        body.question,
        body.run_mode,
        parent_discussion_id=body.parent_discussion_id,
        target_sub_object_type=body.target_sub_object_type,
        include_chat_context=body.include_chat_context,
    )


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


def _proposal_to_escalation_notes(proposal: dict[str, Any]) -> str:
    lines: list[str] = []
    if proposal.get("summary"):
        lines.append("共识：" + str(proposal["summary"]))
    for d in proposal.get("disagreements") or []:
        lines.append("分歧：" + str(d))
    for a in proposal.get("alternatives") or []:
        if isinstance(a, dict) and a.get("label"):
            lines.append(f"备选 {a.get('label')}：{a.get('summary', '')}")
    for q in proposal.get("open_questions") or []:
        lines.append("待补全：" + str(q))
    return "\n".join(lines)


@router.post("/proposals/{proposal_id}/apply-as-draft")
@_handle_flow_error
async def apply_proposal_as_draft(proposal_id: str) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    proposal = flow._store.load_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.get("stage") != "brief":
        raise HTTPException(status_code=409, detail="仅 brief 阶段支持 Council 草稿采纳")
    return flow.apply_council_advisory_draft(proposal["opportunity_id"], proposal)


@router.post("/proposals/{proposal_id}/escalate-rewrite-brief")
@_handle_flow_error
async def escalate_rewrite_brief(proposal_id: str) -> dict[str, Any]:
    """按 Council 共识触发 Brief 规则重编译，并注入共识摘要到 why_worth_doing。"""
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    proposal = flow._store.load_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.get("stage") != "brief":
        raise HTTPException(status_code=409, detail="仅 brief 阶段支持按共识重编 Brief")
    oid = str(proposal["opportunity_id"])
    notes = _proposal_to_escalation_notes(proposal)
    return flow.build_brief(oid, council_escalation_notes=notes).model_dump(mode="json")


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
    extra_kwargs: dict[str, Any] = {}
    if stage == "strategy" and proposal.get("strategy_block_diffs"):
        extra_kwargs["strategy_block_diffs"] = proposal["strategy_block_diffs"]
    if stage == "asset" and proposal.get("asset_diffs"):
        extra_kwargs["asset_diffs"] = proposal["asset_diffs"]
    result = flow.apply_stage_updates(
        proposal["opportunity_id"],
        stage,
        proposal.get("proposed_updates", {}),
        selected_fields=body.selected_fields,
        actor_user_id=body.actor_user_id,
        base_version=proposal.get("base_version"),
        **extra_kwargs,
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
    resp: dict[str, Any] = {
        "proposal_id": proposal_id,
        "status": proposal["status"],
        "applied_fields": result["applied_fields"],
        "skipped_fields": result["skipped_fields"],
        "stale_flags": result["stale_flags"],
        payload_key: result.get(payload_key) or result.get("payload"),
    }
    if result.get("skipped_reasons"):
        resp["skipped_reasons"] = result["skipped_reasons"]
    return resp


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


@router.get("/discussions/by-opportunity/{opportunity_id}")
@_handle_flow_error
async def list_discussions_by_opportunity(
    opportunity_id: str,
    stage: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    flow = _get_flow()
    if flow._store is None:
        raise HTTPException(status_code=500, detail="Store not available")
    discussions = flow._store.list_discussions_by_opportunity(
        opportunity_id, limit=min(limit, 100), stage=stage,
    )
    return {"opportunity_id": opportunity_id, "discussions": discussions, "total": len(discussions)}


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


# ── Agent Pipeline 端点 ────────────────────────────────────────

_pipeline_runner = None


def _get_pipeline_runner():
    global _pipeline_runner
    if _pipeline_runner is None:
        from apps.content_planning.services.agent_pipeline_runner import AgentPipelineRunner
        flow = _get_flow()
        _pipeline_runner = AgentPipelineRunner(
            adapter=flow._adapter,
            plan_store=flow._store,
            platform_store=flow._platform_store,
        )
    return _pipeline_runner


def set_pipeline_runner(runner) -> None:
    global _pipeline_runner
    _pipeline_runner = runner


class AgentPipelineTriggerRequest(BaseModel):
    skip_stages: list[str] = Field(default_factory=list)
    execution_mode: str = "deep"


@router.post("/{opportunity_id}/agent-pipeline")
async def trigger_agent_pipeline(opportunity_id: str, body: AgentPipelineTriggerRequest | None = None):
    runner = _get_pipeline_runner()
    req = body or AgentPipelineTriggerRequest()
    run = await runner.trigger(
        opportunity_id,
        skip_stages=req.skip_stages,
        execution_mode=req.execution_mode,
    )
    return {"run_id": run.run_id, "graph_id": run.graph_id, "status": run.status.value}


@router.get("/{opportunity_id}/agent-pipeline/status")
async def get_agent_pipeline_status(opportunity_id: str):
    runner = _get_pipeline_runner()
    status = await runner.get_status(opportunity_id)
    if status is None:
        raise HTTPException(status_code=404, detail="No pipeline run found")
    return status


@router.post("/{opportunity_id}/agent-pipeline/cancel")
async def cancel_agent_pipeline(opportunity_id: str):
    runner = _get_pipeline_runner()
    ok = await runner.cancel(opportunity_id)
    if not ok:
        raise HTTPException(status_code=400, detail="No running pipeline to cancel")
    return {"cancelled": True}


class BatchAgentPipelineRequest(BaseModel):
    opportunity_ids: list[str]
    execution_mode: str = "deep"


@router.post("/batch-agent-pipeline")
async def trigger_batch_agent_pipeline(body: BatchAgentPipelineRequest):
    runner = _get_pipeline_runner()
    runs = await runner.trigger_batch(body.opportunity_ids, execution_mode=body.execution_mode)
    return {
        oid: {"run_id": run.run_id, "graph_id": run.graph_id, "status": run.status.value}
        for oid, run in runs.items()
    }


@router.post("/batch-agent-pipeline/status")
async def get_batch_agent_pipeline_status(body: BatchAgentPipelineRequest):
    runner = _get_pipeline_runner()
    statuses = await runner.get_batch_status(body.opportunity_ids)
    return statuses


# ── V2 API Endpoints: HealthCheck / Inspect / Readiness / Judge / ReviewLoop ──


class HealthCheckRequest(BaseModel):
    stage: str = "brief"


@router.post("/{opportunity_id}/health-check")
@_handle_flow_error
async def run_health_check(opportunity_id: str, body: HealthCheckRequest) -> dict[str, Any]:
    """Run stage-specific health check, return issues + action chips."""
    from apps.content_planning.agents.health_checker import HealthChecker
    from apps.content_planning.schemas.action_spec import actions_from_health_issues

    flow = _get_flow()
    session = flow._get_session(opportunity_id)
    checker = HealthChecker()

    result = checker.check(
        body.stage,
        brief=session.brief,
        strategy=session.strategy,
        plan=session.note_plan,
        asset_bundle=session.asset_bundle,
    )
    actions = actions_from_health_issues(result.issues, opportunity_id, body.stage)
    return {
        "stage": result.stage,
        "score": result.score,
        "is_healthy": result.is_healthy,
        "issues": [i.model_dump(mode="json") for i in result.issues],
        "next_best_action": result.next_best_action,
        "next_best_action_type": result.next_best_action_type,
        "action_chips": [a.model_dump(mode="json") for a in actions],
    }


class InspectRequest(BaseModel):
    object_type: str = "title"
    object_content: Any = None


@router.post("/{opportunity_id}/inspect")
@_handle_flow_error
async def run_inspect(opportunity_id: str, body: InspectRequest) -> dict[str, Any]:
    """AI Inspector: analyze a selected object, return quality + actions."""
    from apps.content_planning.agents.ai_inspector import AIInspector

    flow = _get_flow()
    session = flow._get_session(opportunity_id)
    inspector = AIInspector()
    result = inspector.inspect(
        body.object_type,
        body.object_content,
        context={"strategy": session.strategy, "brief": session.brief},
        opportunity_id=opportunity_id,
    )
    return result.model_dump(mode="json")


@router.post("/{opportunity_id}/plan-consistency")
@_handle_flow_error
async def run_plan_consistency(opportunity_id: str) -> dict[str, Any]:
    """Check plan-level consistency across titles, body, images, strategy."""
    from apps.content_planning.agents.ai_inspector import AIInspector

    flow = _get_flow()
    session = flow._get_session(opportunity_id)
    inspector = AIInspector()
    result = inspector.check_plan_consistency(
        titles=session.titles,
        body=session.body,
        strategy=session.strategy,
        image_briefs=session.image_briefs,
        plan=session.note_plan,
        opportunity_id=opportunity_id,
    )
    return result.model_dump(mode="json")


@router.get("/{opportunity_id}/readiness")
@_handle_flow_error
async def check_readiness(opportunity_id: str) -> dict[str, Any]:
    """Opportunity readiness check: evidence + review + history."""
    from apps.content_planning.agents.opportunity_readiness import OpportunityReadinessChecker

    flow = _get_flow()
    card = flow._adapter.get_card(opportunity_id)
    source_notes = flow._adapter.get_source_notes(card.source_note_ids) if card else []
    review_summary = flow._adapter.get_review_summary(opportunity_id) if card else {}
    checker = OpportunityReadinessChecker()
    result = checker.check(
        opportunity_id,
        card=card,
        review_summary=review_summary,
        source_notes=source_notes,
    )
    return result.model_dump(mode="json")


class JudgeRequest(BaseModel):
    variants: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/{opportunity_id}/judge")
@_handle_flow_error
async def run_judge(opportunity_id: str, body: JudgeRequest | None = None) -> dict[str, Any]:
    """Judge Agent: evaluate asset quality and optionally compare variants."""
    from apps.content_planning.agents.judge_agent import JudgeAgent

    flow = _get_flow()
    session = flow._get_session(opportunity_id)
    judge = JudgeAgent()

    req = body or JudgeRequest()
    if req.variants:
        comparison = judge.compare_variants(req.variants, plan=session.note_plan)
        return {"mode": "comparison", **comparison.model_dump(mode="json")}
    else:
        result = judge.evaluate(
            session.asset_bundle,
            plan=session.note_plan,
            strategy=session.strategy,
            opportunity_id=opportunity_id,
        )
        return {"mode": "evaluate", **result.model_dump(mode="json")}


class ReviewFeedbackRequest(BaseModel):
    asset_id: str = ""
    brand_id: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)
    performance_tier: str = "average"
    human_notes: str = ""


@router.post("/{opportunity_id}/review-feedback")
@_handle_flow_error
async def submit_review_feedback(opportunity_id: str, body: ReviewFeedbackRequest) -> dict[str, Any]:
    """Submit post-publish performance feedback to close the review loop."""
    from apps.content_planning.agents.review_loop import PerformanceFeedback, ReviewLoop

    feedback = PerformanceFeedback(
        opportunity_id=opportunity_id,
        asset_id=body.asset_id,
        brand_id=body.brand_id,
        metrics=body.metrics,
        performance_tier=body.performance_tier,
        human_notes=body.human_notes,
    )
    loop = ReviewLoop()
    result = loop.process_feedback(feedback)
    return result.model_dump(mode="json")


class StrategyBlockRequest(BaseModel):
    block_name: str = ""
    block_type: str = ""
    content: str = ""
    instruction: str = ""
    action: str = "analyze"  # analyze | rewrite


@router.post("/{opportunity_id}/strategy-block")
@_handle_flow_error
async def operate_strategy_block(opportunity_id: str, body: StrategyBlockRequest) -> dict[str, Any]:
    """Block-level strategy operations: analyze or rewrite a single block."""
    from apps.content_planning.agents.strategy_block_analyzer import StrategyBlock, StrategyBlockAnalyzer

    flow = _get_flow()
    session = flow._get_session(opportunity_id)
    analyzer = StrategyBlockAnalyzer()
    block = StrategyBlock(
        block_name=body.block_name,
        block_type=body.block_type,
        content=body.content,
    )

    brief_context = ""
    if session.brief:
        brief_context = str(session.brief)[:500]

    if body.action == "rewrite":
        rewritten = analyzer.rewrite_block(block, instruction=body.instruction, brief_context=brief_context)
        return {"action": "rewrite", "block_name": body.block_name, "rewritten_content": rewritten}
    else:
        result = analyzer.analyze_block(block, brief_context=brief_context, opportunity_id=opportunity_id)
        return result.model_dump(mode="json")


class RerunFromNodeRequest(BaseModel):
    node_id: str = ""


@router.post("/{opportunity_id}/agent-pipeline/rerun")
@_handle_flow_error
async def rerun_from_node(opportunity_id: str, body: RerunFromNodeRequest) -> dict[str, Any]:
    """Partial rerun: restart pipeline from a specific node."""
    runner = _get_pipeline_runner()
    run = await runner.rerun_from_node(opportunity_id, body.node_id)
    if run is None:
        raise HTTPException(status_code=404, detail="No pipeline run or node found")
    return {"run_id": run.run_id, "status": run.status.value, "rerun_from": body.node_id}
