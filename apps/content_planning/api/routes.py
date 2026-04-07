"""content_planning API 路由。

主路径前缀：/content-planning/...
兼容路径（与验收文档 A3 一致）：/xhs-opportunities/...（无前缀，见 router_alias）
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


class GeneratePlanRequest(BaseModel):
    """生成笔记策划请求。

    - mode=plan_only：仅返回 brief / 匹配 / 策略 / note_plan（默认）
    - mode=full：等价于 with_generation=true，额外返回 titles / body / image_briefs
    - with_generation：显式为 true 时也会开启生成（与 mode=full 叠加任一即可）
    """

    with_generation: bool = False
    preferred_template_id: str | None = None
    mode: Literal["plan_only", "full"] = "plan_only"


def _resolve_with_generation(body: GeneratePlanRequest) -> bool:
    return body.with_generation or body.mode == "full"


def _http_brief(opportunity_id: str) -> dict[str, Any]:
    try:
        return _get_flow().build_brief(opportunity_id).model_dump(mode="json")
    except OpportunityNotPromotedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _http_note_plan(opportunity_id: str, body: GeneratePlanRequest | None) -> dict[str, Any]:
    if body is None:
        body = GeneratePlanRequest()
    try:
        return _get_flow().build_note_plan(
            opportunity_id,
            with_generation=_resolve_with_generation(body),
            preferred_template_id=body.preferred_template_id,
        )
    except OpportunityNotPromotedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/xhs-opportunities/{opportunity_id}/generate-brief")
async def generate_brief(opportunity_id: str) -> dict[str, Any]:
    return _http_brief(opportunity_id)


@router.post("/xhs-opportunities/{opportunity_id}/generate-note-plan")
async def generate_note_plan(opportunity_id: str, body: GeneratePlanRequest | None = None) -> dict[str, Any]:
    return _http_note_plan(opportunity_id, body)


@router_alias.post("/xhs-opportunities/{opportunity_id}/generate-brief")
async def generate_brief_alias(opportunity_id: str) -> dict[str, Any]:
    """兼容验收文档中的无前缀路径 POST /xhs-opportunities/{id}/generate-brief。"""
    return _http_brief(opportunity_id)


@router_alias.post("/xhs-opportunities/{opportunity_id}/generate-note-plan")
async def generate_note_plan_alias(opportunity_id: str, body: GeneratePlanRequest | None = None) -> dict[str, Any]:
    """兼容验收文档中的无前缀路径 POST /xhs-opportunities/{id}/generate-note-plan。"""
    return _http_note_plan(opportunity_id, body)
