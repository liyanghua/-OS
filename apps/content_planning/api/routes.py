"""content_planning API 路由 v2。

原子 API + 编排 API + Brief 编辑 + 局部重生成。
主路径前缀：/content-planning/...
兼容路径（与验收文档 A3 一致）：/xhs-opportunities/...（无前缀，见 router_alias）
"""

from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.content_planning.exceptions import OpportunityNotPromotedError
from apps.content_planning.services.opportunity_to_plan_flow import OpportunityToPlanFlow

router = APIRouter(prefix="/content-planning", tags=["content_planning"])
router_alias = APIRouter(tags=["content_planning"])

_flow: OpportunityToPlanFlow | None = None


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


# ═══════════════════════════════════════════════════════════════
#  原子 API（主前缀 /content-planning/...）
# ═══════════════════════════════════════════════════════════════

@router.post("/xhs-opportunities/{opportunity_id}/generate-brief")
@_handle_flow_error
async def generate_brief(opportunity_id: str) -> dict[str, Any]:
    return _get_flow().build_brief(opportunity_id).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-note-plan")
@_handle_flow_error
async def generate_note_plan(
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


@router.post("/xhs-opportunities/{opportunity_id}/match-templates")
@_handle_flow_error
async def match_templates(opportunity_id: str) -> dict[str, Any]:
    """Brief → 模板匹配。"""
    return _get_flow().match_templates(opportunity_id).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-strategy")
@_handle_flow_error
async def generate_strategy(
    opportunity_id: str,
    body: GenerateStrategyRequest | None = None,
) -> dict[str, Any]:
    """模板 → RewriteStrategy。"""
    tid = body.template_id if body else None
    return _get_flow().build_strategy(
        opportunity_id, template_id=tid,
    ).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-titles")
@_handle_flow_error
async def generate_titles(opportunity_id: str) -> dict[str, Any]:
    """局部重生成标题。"""
    return _get_flow().regenerate_titles(opportunity_id).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-body")
@_handle_flow_error
async def generate_body(opportunity_id: str) -> dict[str, Any]:
    """局部重生成正文。"""
    return _get_flow().regenerate_body(opportunity_id).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/generate-image-briefs")
@_handle_flow_error
async def generate_image_briefs(opportunity_id: str) -> dict[str, Any]:
    """局部重生成图片执行指令。"""
    return _get_flow().regenerate_image_briefs(opportunity_id).model_dump(mode="json")


@router.put("/briefs/{opportunity_id}")
@_handle_flow_error
async def update_brief(
    opportunity_id: str,
    body: BriefUpdateRequest,
) -> dict[str, Any]:
    """人工编辑 Brief（按 opportunity_id 索引）。"""
    partial = {k: v for k, v in body.model_dump().items() if v is not None}
    return _get_flow().update_brief(opportunity_id, partial).model_dump(mode="json")


@router.post("/xhs-opportunities/{opportunity_id}/compile-note-plan")
@_handle_flow_error
async def compile_note_plan(
    opportunity_id: str,
    body: GeneratePlanRequest | None = None,
) -> dict[str, Any]:
    """编排型一键全链路。"""
    if body is None:
        body = GeneratePlanRequest(mode="full")
    return _get_flow().compile_note_plan(
        opportunity_id,
        with_generation=_resolve_with_generation(body),
        preferred_template_id=body.preferred_template_id,
    )


@router.get("/session/{opportunity_id}")
@_handle_flow_error
async def get_session(opportunity_id: str) -> dict[str, Any]:
    """获取当前会话缓存。"""
    return _get_flow().get_session_data(opportunity_id)


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
async def get_asset_bundle(opportunity_id: str) -> dict[str, Any]:
    """组装并返回 AssetBundle。"""
    bundle = _get_flow().assemble_asset_bundle(opportunity_id)
    return bundle.model_dump(mode="json")


@router.get("/asset-bundle/{opportunity_id}/export")
@_handle_flow_error
async def export_asset_bundle(opportunity_id: str, format: str = "json") -> Any:
    """导出 AssetBundle。format: json / markdown / image_package"""
    from apps.content_planning.services.asset_exporter import AssetExporter

    bundle = _get_flow().assemble_asset_bundle(opportunity_id)
    exporter = AssetExporter()
    if format == "markdown":
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(exporter.export_markdown(bundle), media_type="text/markdown")
    elif format == "image_package":
        return exporter.export_image_package(bundle)
    return exporter.export_json(bundle)


class BatchCompileRequest(BaseModel):
    opportunity_ids: list[str] = Field(min_length=1)


@router.post("/batch-compile")
@_handle_flow_error
async def batch_compile(body: BatchCompileRequest) -> dict[str, Any]:
    """批量编译 promoted 卡。"""
    return _get_flow().batch_compile(body.opportunity_ids)


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


# ═══════════════════════════════════════════════════════════════
#  兼容路由（无前缀，router_alias）
# ═══════════════════════════════════════════════════════════════

@router_alias.post("/xhs-opportunities/{opportunity_id}/generate-brief")
@_handle_flow_error
async def generate_brief_alias(opportunity_id: str) -> dict[str, Any]:
    return _get_flow().build_brief(opportunity_id).model_dump(mode="json")


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
