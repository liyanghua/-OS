"""content_planning API 路由 v2。

原子 API + 编排 API + Brief 编辑 + 局部重生成。
主路径前缀：/content-planning/...
兼容路径（与验收文档 A3 一致）：/xhs-opportunities/...（无前缀，见 router_alias）
"""

from __future__ import annotations

from typing import Any, Literal

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
