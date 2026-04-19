"""growth_lab API 路由。

路由前缀：/growth-lab/...
- /growth-lab/radar       — 热点雷达
- /growth-lab/compiler    — 卖点编译器
- /growth-lab/lab         — 主图裂变工作台
- /growth-lab/first3s     — 前3秒裂变工作台
- /growth-lab/board       — 测试放大板
- /growth-lab/assets      — 资产图谱
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from apps.growth_lab.storage.growth_lab_store import GrowthLabStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/growth-lab", tags=["growth-lab"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)

_store: GrowthLabStore | None = None


def _get_store() -> GrowthLabStore:
    global _store
    if _store is None:
        _store = GrowthLabStore()
    return _store


# ── 请求模型 ────────────────────────────────────────────────────

class TrendOpportunityCreate(BaseModel):
    title: str = ""
    summary: str = ""
    source_platform: str = ""
    source_type: str = "trend"
    workspace_id: str = ""
    brand_id: str = ""


class SellingPointSpecCreate(BaseModel):
    source_opportunity_ids: list[str] = Field(default_factory=list)
    core_claim: str = ""
    supporting_claims: list[str] = Field(default_factory=list)
    target_people: list[str] = Field(default_factory=list)
    target_scenarios: list[str] = Field(default_factory=list)
    workspace_id: str = ""
    brand_id: str = ""


class MainImageVariantCreate(BaseModel):
    source_selling_point_id: str = ""
    platform: str = ""
    sku_id: str = ""
    variables: list[dict] = Field(default_factory=list)
    base_prompt: str = ""
    negative_prompt: str = ""
    reference_image_urls: list[str] = Field(default_factory=list)
    workspace_id: str = ""
    brand_id: str = ""


class VariantBatchRequest(BaseModel):
    source_selling_point_id: str = ""
    platform: str = ""
    sku_id: str = ""
    variable_matrix: list[list[dict]] = Field(default_factory=list)
    base_prompt: str = ""
    negative_prompt: str = ""
    reference_image_urls: list[str] = Field(default_factory=list)
    provider_hint: str = "auto"
    workspace_id: str = ""
    brand_id: str = ""


class TestTaskCreate(BaseModel):
    source_variant_id: str = ""
    variant_type: str = "main_image"
    platform: str = ""
    store_id: str = ""
    sku_id: str = ""
    test_window_days: int = 7
    owner: str = ""
    workspace_id: str = ""
    brand_id: str = ""


class ResultSnapshotCreate(BaseModel):
    task_id: str = ""
    date: str = ""
    ctr: float | None = None
    traffic: int | None = None
    conversion_rate: float | None = None
    refund_rate: float | None = None
    save_rate: float | None = None
    overall_result: str = "pending"
    notes: str = ""


class CompileSellingPointRequest(BaseModel):
    opportunity_ids: list[str] = Field(default_factory=list)
    workspace_id: str = ""
    brand_id: str = ""


class ExpertAnnotationCreate(BaseModel):
    spec_id: str = ""
    field_name: str = ""
    annotation_type: str = "insight"
    content: str = ""
    annotator: str = "专家用户"


# ── 页面路由 ────────────────────────────────────────────────────

@router.get("/radar", response_class=HTMLResponse)
async def radar_page(request: Request) -> HTMLResponse:
    tpl = TEMPLATE_ENV.get_template("radar.html")
    return HTMLResponse(tpl.render())


@router.get("/compiler", response_class=HTMLResponse)
async def compiler_page(request: Request) -> HTMLResponse:
    tpl = TEMPLATE_ENV.get_template("compiler.html")
    return HTMLResponse(tpl.render())


@router.get("/lab", response_class=HTMLResponse)
async def main_image_lab_page(request: Request) -> HTMLResponse:
    tpl = TEMPLATE_ENV.get_template("main_image_lab.html")
    return HTMLResponse(tpl.render())


@router.get("/first3s", response_class=HTMLResponse)
async def first3s_lab_page(request: Request) -> HTMLResponse:
    tpl = TEMPLATE_ENV.get_template("first3s_lab.html")
    return HTMLResponse(tpl.render())


@router.get("/board", response_class=HTMLResponse)
async def test_board_page(request: Request) -> HTMLResponse:
    tpl = TEMPLATE_ENV.get_template("board.html")
    return HTMLResponse(tpl.render())


@router.get("/assets", response_class=HTMLResponse)
async def asset_graph_page(request: Request) -> HTMLResponse:
    tpl = TEMPLATE_ENV.get_template("asset_graph.html")
    return HTMLResponse(tpl.render())


@router.get("/workspace", response_class=HTMLResponse)
async def visual_workspace_page(request: Request) -> HTMLResponse:
    tpl = TEMPLATE_ENV.get_template("workspace.html")
    return HTMLResponse(tpl.render())


# ── API: Radar / TrendOpportunity ─────────────────────────────

@router.get("/api/radar/opportunities")
async def list_opportunities(
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    store = _get_store()
    where = {}
    if status:
        where["status"] = status
    items = store.list_trend_opportunities(where=where, limit=limit, offset=offset)
    total = store._count("trend_opportunities", where=where if where else None)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/api/radar/opportunities/{opp_id}")
async def get_opportunity(opp_id: str) -> dict:
    store = _get_store()
    item = store.get_trend_opportunity(opp_id)
    if not item:
        raise HTTPException(404, f"TrendOpportunity {opp_id} not found")
    return item


@router.post("/api/radar/opportunities")
async def create_opportunity(req: TrendOpportunityCreate) -> dict:
    from apps.growth_lab.schemas.trend_opportunity import TrendOpportunity
    opp = TrendOpportunity(**req.model_dump())
    store = _get_store()
    store.save_trend_opportunity(opp.model_dump())
    return opp.model_dump()


@router.post("/api/radar/opportunities/{opp_id}/bookmark")
async def bookmark_opportunity(opp_id: str) -> dict:
    store = _get_store()
    item = store.get_trend_opportunity(opp_id)
    if not item:
        raise HTTPException(404, f"TrendOpportunity {opp_id} not found")
    item["status"] = "bookmarked"
    store.save_trend_opportunity(item)
    return {"status": "ok", "new_status": "bookmarked"}


@router.post("/api/radar/opportunities/{opp_id}/promote")
async def promote_opportunity(opp_id: str) -> dict:
    store = _get_store()
    item = store.get_trend_opportunity(opp_id)
    if not item:
        raise HTTPException(404, f"TrendOpportunity {opp_id} not found")
    item["status"] = "promoted"
    store.save_trend_opportunity(item)
    return {"status": "ok", "new_status": "promoted"}


@router.post("/api/radar/sync-from-intel-hub")
async def sync_from_intel_hub() -> dict:
    """从 intel_hub 同步 XHS 机会卡到 Radar。"""
    from apps.growth_lab.adapters.opportunity_adapter import xhs_card_to_trend_opportunity
    from apps.intel_hub.storage.xhs_review_store import XHSReviewStore

    try:
        xhs_store = XHSReviewStore(
            Path(__file__).resolve().parents[3] / "data" / "xhs_review.sqlite"
        )
        result = xhs_store.list_cards(page_size=500)
        cards = result["items"]
    except Exception as e:
        logger.warning("无法连接 intel_hub 数据源: %s", e)
        cards = []

    store = _get_store()
    synced = 0
    for card in cards:
        try:
            opp = xhs_card_to_trend_opportunity(card)
            store.save_trend_opportunity(opp.model_dump())
            synced += 1
        except Exception as e:
            logger.warning("同步机会卡失败 %s: %s", getattr(card, "opportunity_id", "?"), e)
    return {"synced": synced, "total_source": len(cards)}


# ── API: Compiler / SellingPointSpec ──────────────────────────

@router.get("/api/compiler/specs")
async def list_specs(status: str = "", limit: int = 50, offset: int = 0) -> dict:
    store = _get_store()
    where = {}
    if status:
        where["status"] = status
    items = store.list_selling_point_specs(where=where, limit=limit, offset=offset)
    total = store._count("selling_point_specs", where=where if where else None)
    return {"items": items, "total": total}


@router.get("/api/compiler/specs/{spec_id}")
async def get_spec(spec_id: str) -> dict:
    store = _get_store()
    item = store.get_selling_point_spec(spec_id)
    if not item:
        raise HTTPException(404, f"SellingPointSpec {spec_id} not found")
    return item


@router.post("/api/compiler/specs")
async def create_spec(req: SellingPointSpecCreate) -> dict:
    from apps.growth_lab.schemas.selling_point_spec import SellingPointSpec
    spec = SellingPointSpec(**req.model_dump())
    store = _get_store()
    store.save_selling_point_spec(spec.model_dump())
    return spec.model_dump()


@router.post("/api/compiler/compile")
async def compile_selling_points(req: CompileSellingPointRequest) -> dict:
    """LLM 驱动的卖点编译。"""
    from apps.growth_lab.services.selling_point_compiler import SellingPointCompilerService
    compiler = SellingPointCompilerService()
    store = _get_store()

    opportunities = []
    for oid in req.opportunity_ids:
        opp = store.get_trend_opportunity(oid)
        if opp:
            opportunities.append(opp)

    if not opportunities:
        raise HTTPException(400, "未找到有效的机会卡")

    result = await compiler.compile(
        opportunities,
        workspace_id=req.workspace_id,
        brand_id=req.brand_id,
    )
    store.save_selling_point_spec(result.model_dump())
    return result.model_dump()


@router.post("/api/compiler/compile-stream")
async def compile_selling_points_stream(req: CompileSellingPointRequest) -> StreamingResponse:
    """SSE 三阶段编译流。"""
    from apps.growth_lab.services.selling_point_compiler import SellingPointCompilerService
    compiler = SellingPointCompilerService()
    store = _get_store()

    opportunities = []
    for oid in req.opportunity_ids:
        opp = store.get_trend_opportunity(oid)
        if opp:
            opportunities.append(opp)

    if not opportunities:
        raise HTTPException(400, "未找到有效的机会卡")

    expert_annotations = store.list_expert_annotations(
        where={"brand_id": req.brand_id} if req.brand_id else None,
        limit=10,
    ) if hasattr(store, 'list_expert_annotations') else []

    async def event_generator():
        async for evt in compiler.compile_stream(
            opportunities,
            workspace_id=req.workspace_id,
            brand_id=req.brand_id,
            expert_annotations=expert_annotations,
        ):
            if evt.get("event") == "compile_complete":
                spec_data = evt["data"]
                store.save_selling_point_spec(spec_data)
            yield f"data: {json.dumps(evt, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── API: Expert Annotations ──────────────────────────────────

@router.post("/api/compiler/annotations")
async def create_annotation(req: ExpertAnnotationCreate) -> dict:
    from apps.growth_lab.schemas.selling_point_spec import ExpertAnnotation
    ann = ExpertAnnotation(
        spec_id=req.spec_id,
        field_name=req.field_name,
        annotation_type=req.annotation_type,
        content=req.content,
        annotator=req.annotator,
    )
    store = _get_store()
    store.save_expert_annotation(ann.model_dump())
    return ann.model_dump()


@router.get("/api/compiler/annotations")
async def list_annotations(spec_id: str = "", limit: int = 50) -> dict:
    store = _get_store()
    where: dict[str, Any] = {}
    if spec_id:
        where["spec_id"] = spec_id
    items = store.list_expert_annotations(where=where, limit=limit)
    return {"items": items, "total": len(items)}


# ── API: References ──────────────────────────────────────────

_TAG_LABEL_ZH = {
    "main_image": "主图",
    "first3s": "前3秒",
    "detail_module": "详情模块",
    "video_shot": "分镜",
    "buyer_show": "买家秀",
    "competitor_ref": "竞品",
    "high_performer": "高表现",
    "main_image_template": "主图模板",
    "viral_clip": "爆款片段",
    "selling_point_template": "卖点模板",
    "workspace": "视觉工作台",
    "人群场景直击图": "人群直击",
    "痛点放大对比图": "痛点对比",
    "核心需求满足图": "需求满足",
    "场景化功能对比图": "场景对比",
    "用户信任背书图": "信任背书",
}


def _humanize_tag(t: str) -> str:
    if not t:
        return ""
    return _TAG_LABEL_ZH.get(t, t)


def _normalize_reference(raw: dict) -> dict:
    """把 PatternTemplate / AssetPerformanceCard 统一成运营友好的展示结构。"""
    # PatternTemplate：有 name/template_text
    if "template_text" in raw or ("name" in raw and "asset_id" not in raw):
        tags = raw.get("tags") or []
        return {
            "kind": "pattern",
            "title": raw.get("name") or raw.get("headline") or "经验模板",
            "subtitle": raw.get("template_text") or raw.get("hook_text") or raw.get("description") or "",
            "image_url": raw.get("image_url") or raw.get("thumbnail_url") or "",
            "tags": [_humanize_tag(t) for t in tags if t],
            "source_label": "经验模板",
            "metric_label": f"复用 {raw.get('usage_count') or 0} 次" if raw.get("usage_count") else "",
            "link": "",
        }

    # AssetPerformanceCard
    tags = raw.get("tags") or []
    asset_type = raw.get("asset_type") or ""
    source_platform = raw.get("source_platform") or ""
    best_metrics = raw.get("best_metrics") or {}
    metric_bits: list[str] = []
    for k in ("ctr", "cvr", "roi", "sales"):
        if k in best_metrics:
            metric_bits.append(f"{k.upper()} {best_metrics[k]}")
    usage = raw.get("usage_count") or 0
    if usage:
        metric_bits.append(f"被复用 {usage} 次")

    title = raw.get("description") or raw.get("headline") or "未命名资产"
    # 状态 subtitle
    status = raw.get("status") or ""
    source_label_parts = [_humanize_tag(asset_type)]
    if source_platform:
        source_label_parts.append(_humanize_tag(source_platform))
    if status and status != "active":
        source_label_parts.append(status)
    return {
        "kind": "asset",
        "title": title,
        "subtitle": "、".join([_humanize_tag(t) for t in tags if t]) or "",
        "image_url": raw.get("image_url") or "",
        "tags": [_humanize_tag(t) for t in tags if t],
        "source_label": " · ".join(p for p in source_label_parts if p),
        "metric_label": " · ".join(metric_bits),
        "link": raw.get("image_url") or "",
    }


_DEFAULT_SHELF_REFS = [
    {
        "kind": "pattern",
        "title": "爆款标题公式：痛点 + 解决方案 + 差异化",
        "subtitle": "例：告别 XX 烦恼，XX 产品让你 XX",
        "image_url": "", "tags": ["经验模板"], "source_label": "经验模板",
        "metric_label": "", "link": "",
    },
    {
        "kind": "pattern",
        "title": "数字型标题：具体数据增强说服力",
        "subtitle": "例：3 天见效 / 月销 10 万+ / 98% 好评",
        "image_url": "", "tags": ["经验模板"], "source_label": "经验模板",
        "metric_label": "", "link": "",
    },
    {
        "kind": "pattern",
        "title": "场景型标题：切入具体使用场景",
        "subtitle": "例：露营必备 / 宿舍神器 / 通勤好物",
        "image_url": "", "tags": ["经验模板"], "source_label": "经验模板",
        "metric_label": "", "link": "",
    },
]
_DEFAULT_FIRST3S_REFS = [
    {
        "kind": "pattern",
        "title": "悬念型钩子：先抛问题再给答案",
        "subtitle": "例：你还在为 XX 苦恼吗？",
        "image_url": "", "tags": ["经验模板"], "source_label": "经验模板",
        "metric_label": "", "link": "",
    },
    {
        "kind": "pattern",
        "title": "共鸣型钩子：直击目标人群痛点",
        "subtitle": "例：每次 XX 的时候是不是特别 XX？",
        "image_url": "", "tags": ["经验模板"], "source_label": "经验模板",
        "metric_label": "", "link": "",
    },
    {
        "kind": "pattern",
        "title": "反转型钩子：先否定再肯定",
        "subtitle": "例：我以为 XX 没用，直到我试了这个…",
        "image_url": "", "tags": ["经验模板"], "source_label": "经验模板",
        "metric_label": "", "link": "",
    },
]


@router.get("/api/compiler/references")
async def get_references() -> dict:
    """返回货架/前3秒参考案例（从 PatternTemplate 和 AssetPerformanceCard 拉取，统一成运营友好结构）。"""
    store = _get_store()

    shelf_templates = store.list_pattern_templates(
        where={"template_type": "main_image"}, limit=5,
    )
    first3s_templates = store.list_pattern_templates(
        where={"template_type": "first3s"}, limit=5,
    )
    shelf_assets = store.list_asset_performance_cards(
        where={"asset_type": "high_performer"}, limit=3,
    )
    # main_image_template 也应当作为货架参考
    shelf_assets_tpl = store.list_asset_performance_cards(
        where={"asset_type": "main_image_template"}, limit=3,
    )

    shelf_raw = list(shelf_templates) + list(shelf_assets) + list(shelf_assets_tpl)
    first3s_raw = list(first3s_templates)

    shelf_refs = [_normalize_reference(r) for r in shelf_raw] or _DEFAULT_SHELF_REFS
    first3s_refs = [_normalize_reference(r) for r in first3s_raw] or _DEFAULT_FIRST3S_REFS

    return {"shelf_references": shelf_refs, "first3s_references": first3s_refs}


# ── API: Lab / MainImageVariant ───────────────────────────────

@router.get("/api/lab/variants")
async def list_variants(
    selling_point_id: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    store = _get_store()
    where: dict[str, Any] = {}
    if selling_point_id:
        where["source_selling_point_id"] = selling_point_id
    if status:
        where["status"] = status
    items = store.list_main_image_variants(where=where, limit=limit, offset=offset)
    total = store._count("main_image_variants", where=where if where else None)
    return {"items": items, "total": total}


@router.get("/api/lab/variants/{variant_id}")
async def get_variant(variant_id: str) -> dict:
    store = _get_store()
    item = store.get_main_image_variant(variant_id)
    if not item:
        raise HTTPException(404, f"MainImageVariant {variant_id} not found")
    return item


@router.post("/api/lab/variants")
async def create_variant(req: MainImageVariantCreate) -> dict:
    from apps.growth_lab.schemas.main_image_variant import (
        ImageVariantSpec, MainImageVariant, VariantVariable,
    )
    variables = [VariantVariable(**v) for v in req.variables]
    spec = ImageVariantSpec(
        variables=variables,
        base_prompt=req.base_prompt,
        negative_prompt=req.negative_prompt,
        reference_image_urls=req.reference_image_urls,
    )
    variant = MainImageVariant(
        source_selling_point_id=req.source_selling_point_id,
        platform=req.platform,
        sku_id=req.sku_id,
        key_variables=variables,
        image_variant_spec=spec,
        workspace_id=req.workspace_id,
        brand_id=req.brand_id,
    )
    store = _get_store()
    store.save_main_image_variant(variant.model_dump())
    return variant.model_dump()


@router.post("/api/lab/generate-batch")
async def generate_variant_batch(req: VariantBatchRequest) -> dict:
    """批量生成主图变体：先编译变量矩阵为 variant 列表，再入队。"""
    from apps.growth_lab.services.main_image_variant_compiler import MainImageVariantCompiler
    from apps.growth_lab.services.variant_batch_queue import VariantBatchQueue

    store = _get_store()
    spec = store.get_selling_point_spec(req.source_selling_point_id)

    compiler = MainImageVariantCompiler()
    variants = compiler.compile_matrix(
        spec or {"spec_id": req.source_selling_point_id},
        req.variable_matrix,
        platform=req.platform,
        sku_id=req.sku_id,
        workspace_id=req.workspace_id,
        brand_id=req.brand_id,
    )

    variant_dicts = [v.model_dump() for v in variants]
    for vd in variant_dicts:
        img_spec = vd.get("image_variant_spec", {})
        if req.base_prompt and not img_spec.get("base_prompt"):
            img_spec["base_prompt"] = req.base_prompt
        if req.negative_prompt:
            img_spec["negative_prompt"] = req.negative_prompt
        if req.reference_image_urls:
            img_spec["reference_image_urls"] = req.reference_image_urls
        if req.provider_hint and req.provider_hint != "auto":
            img_spec["provider_hint"] = req.provider_hint
        vd["image_variant_spec"] = img_spec
        vd["status"] = "generating"
        store.save_main_image_variant(vd)

    def _on_slot_done(variant_dict: dict, result_url: str) -> None:
        variant_dict["generated_image_url"] = result_url
        variant_dict["status"] = "generated" if result_url else "failed"
        try:
            store.save_main_image_variant(variant_dict)
        except Exception:
            pass

    queue = _get_batch_queue(on_slot_done=_on_slot_done)
    batch_id = queue.enqueue_batch(
        variant_dicts,
        workspace_id=req.workspace_id,
        brand_id=req.brand_id,
    )
    return {"batch_id": batch_id, "status": "queued", "total_slots": len(variant_dicts)}


_batch_queue_instance: "VariantBatchQueue | None" = None


def _get_batch_queue(on_slot_done=None):
    from apps.growth_lab.services.variant_batch_queue import VariantBatchQueue
    global _batch_queue_instance
    if _batch_queue_instance is None:
        _batch_queue_instance = VariantBatchQueue(on_slot_done=on_slot_done)
    elif on_slot_done is not None:
        _batch_queue_instance._on_slot_done = on_slot_done
    return _batch_queue_instance


@router.get("/api/lab/batch/{batch_id}/status")
async def get_batch_status(batch_id: str) -> dict:
    queue = _get_batch_queue()
    return queue.get_batch_status(batch_id)


# ── API: First3s ─────────────────────────────────────────────

@router.get("/api/first3s/variants")
async def list_first3s_variants(
    selling_point_id: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    store = _get_store()
    where: dict[str, Any] = {}
    if selling_point_id:
        where["source_selling_point_id"] = selling_point_id
    if status:
        where["status"] = status
    items = store.list_first3s_variants(where=where, limit=limit, offset=offset)
    total = store._count("first3s_variants", where=where if where else None)
    return {"items": items, "total": total}


@router.get("/api/first3s/variants/{variant_id}")
async def get_first3s_variant(variant_id: str) -> dict:
    store = _get_store()
    item = store.get_first3s_variant(variant_id)
    if not item:
        raise HTTPException(404, f"First3sVariant {variant_id} not found")
    return item


@router.post("/api/first3s/generate-hooks")
async def generate_hook_scripts(req: CompileSellingPointRequest) -> dict:
    """基于卖点生成前3秒钩子脚本。"""
    from apps.growth_lab.services.first3s_variant_compiler import First3sVariantCompiler
    compiler = First3sVariantCompiler()
    store = _get_store()

    specs = []
    for oid in req.opportunity_ids:
        spec = store.get_selling_point_spec(oid)
        if spec:
            specs.append(spec)

    if not specs:
        raise HTTPException(400, "未找到有效的卖点规格")

    results = await compiler.generate_hook_variants(
        specs, workspace_id=req.workspace_id, brand_id=req.brand_id,
    )
    for r in results:
        store.save_first3s_variant(r.model_dump())
    return {"variants": [r.model_dump() for r in results], "total": len(results)}


class VideoGenerateRequest(BaseModel):
    variant_id: str = ""
    prompt: str = ""
    first_frame_url: str = ""
    aspect_ratio: str = "9:16"


_video_jobs: dict[str, dict[str, Any]] = {}


@router.post("/api/first3s/generate-video")
async def generate_video(req: VideoGenerateRequest) -> dict:
    """提交 Seedance 视频生成任务（异步）。"""
    import asyncio
    from apps.growth_lab.services.video_generator import VideoGeneratorService

    svc = VideoGeneratorService()
    if not svc.is_available():
        raise HTTPException(500, "OPENROUTER_API_KEY 未配置，无法生成视频")

    if not req.prompt:
        raise HTTPException(400, "prompt 不能为空")

    store = _get_store()
    variant = store.get_first3s_variant(req.variant_id) if req.variant_id else None
    variant_id = req.variant_id or "tmp_" + __import__("uuid").uuid4().hex[:12]

    if variant:
        variant["video_prompt"] = req.prompt
        variant["first_frame_url"] = req.first_frame_url
        variant["video_generation_status"] = "pending"
        store.save_first3s_variant(variant)

    async def _run_job(job_id: str) -> None:
        _video_jobs[job_id]["status"] = "generating"
        try:
            result = await svc.generate_and_wait(
                req.prompt,
                variant_id,
                first_frame_url=req.first_frame_url,
                aspect_ratio=req.aspect_ratio,
            )
            _video_jobs[job_id].update(result)
            if variant and result.get("status") == "completed":
                variant["generated_video_url"] = result.get("video_url", "")
                variant["video_generation_status"] = "completed"
                variant["video_job_id"] = result.get("job_id", "")
                store.save_first3s_variant(variant)
            elif variant:
                variant["video_generation_status"] = result.get("status", "failed")
                store.save_first3s_variant(variant)
        except Exception as e:
            logger.exception("[VideoGen] job %s failed: %s", job_id, e)
            _video_jobs[job_id].update({"status": "failed", "error": str(e)})
            if variant:
                variant["video_generation_status"] = "failed"
                store.save_first3s_variant(variant)

    job_id = __import__("uuid").uuid4().hex[:16]
    _video_jobs[job_id] = {"status": "pending", "variant_id": variant_id}
    asyncio.create_task(_run_job(job_id))

    return {"job_id": job_id, "status": "pending"}


@router.get("/api/first3s/video-status/{job_id}")
async def video_status(job_id: str) -> dict:
    """轮询视频生成状态。"""
    job = _video_jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "video_url": job.get("video_url", ""),
        "error": job.get("error", ""),
        "elapsed_ms": job.get("elapsed_ms", 0),
        "frame_dropped": job.get("frame_dropped", False),
    }


def _extract_note_id(url: str) -> str:
    """从小红书 URL 中提取笔记 ID。"""
    import re
    if not url:
        return ""
    m = re.search(r"/explore/([a-f0-9]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/discovery/item/([a-f0-9]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"note[_/]?id[=:]([a-f0-9]+)", url, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


# ── API: First3s / 一键发布 ──────────────────────────────────

class PublishRequest(BaseModel):
    variant_id: str = ""
    title: str = ""
    body: str = ""
    topics: list[str] = Field(default_factory=list)


_publish_jobs: dict[str, dict[str, Any]] = {}


@router.post("/api/first3s/publish")
async def publish_to_xhs(req: PublishRequest) -> dict:
    """提交小红书发布任务（异步 Playwright）。"""
    import asyncio
    from apps.growth_lab.services.xhs_publisher import XHSPublishService, build_publish_content

    store = _get_store()
    variant = store.get_first3s_variant(req.variant_id) if req.variant_id else None

    if not variant:
        raise HTTPException(404, "First3sVariant not found")

    video_url = variant.get("generated_video_url", "")
    if not video_url:
        raise HTTPException(400, "该钩子尚未生成视频，请先生成视频")

    title = req.title
    body = req.body
    topics = req.topics

    if not title or not body:
        hook_script = variant.get("hook_script", {})
        spec = None
        sp_id = variant.get("source_selling_point_id", "")
        if sp_id:
            spec = store.get_selling_point_spec(sp_id)
        auto = build_publish_content(hook_script, spec)
        if not title:
            title = auto["title"]
        if not body:
            body = auto["body"]
        if not topics:
            topics = auto["topics"]

    _repo_root = Path(__file__).resolve().parents[3]
    _videos_dir = _repo_root / "data" / "generated_videos"
    video_path = str(_videos_dir / video_url.replace("/generated-videos/", ""))

    job_id = __import__("uuid").uuid4().hex[:16]
    _publish_jobs[job_id] = {
        "status": "pending",
        "variant_id": req.variant_id,
        "progress_step": "",
        "progress_detail": "",
    }

    def _on_progress(step: str, detail: str) -> None:
        if job_id in _publish_jobs:
            _publish_jobs[job_id]["progress_step"] = step
            _publish_jobs[job_id]["progress_detail"] = detail

    async def _run_publish() -> None:
        _publish_jobs[job_id]["status"] = "publishing"
        try:
            svc = XHSPublishService(headless=False)
            result = await svc.publish_video(
                video_path=video_path,
                title=title,
                body=body,
                topics=topics,
                on_progress=_on_progress,
            )
            _publish_jobs[job_id].update(result)

            if result.get("status") == "published" and variant:
                from datetime import datetime, UTC as _UTC
                note_url = result.get("note_url", "")
                note_id = _extract_note_id(note_url)

                variant.setdefault("publish_count", 0)
                variant["publish_count"] += 1
                variant.setdefault("publish_history", [])
                variant["publish_history"].append({
                    "job_id": job_id,
                    "title": title,
                    "note_url": note_url,
                    "note_id": note_id,
                    "published_at": datetime.now(_UTC).isoformat(),
                })
                store.save_first3s_variant(variant)

                from apps.growth_lab.schemas.test_task import TestTask as _TT
                task = _TT(
                    source_variant_id=req.variant_id,
                    variant_type="first3s",
                    platform="xiaohongshu",
                    xhs_note_url=note_url,
                    xhs_note_id=note_id,
                    xhs_publish_job_id=job_id,
                    xhs_review_status="pending",
                    status="active",
                    test_window_days=7,
                    metrics_to_watch=["liked_count", "collected_count", "comment_count"],
                )
                task_dict = task.model_dump()
                store.save_test_task(task_dict)
                _publish_jobs[job_id]["test_task_id"] = task_dict["task_id"]
                logger.info("[Publish] auto-created TestTask %s for variant %s", task_dict["task_id"], req.variant_id)
        except Exception as e:
            logger.exception("[Publish] job %s failed: %s", job_id, e)
            _publish_jobs[job_id].update({"status": "failed", "error": str(e)})

    asyncio.create_task(_run_publish())
    return {"job_id": job_id, "status": "pending"}


@router.get("/api/first3s/publish-status/{job_id}")
async def publish_status(job_id: str) -> dict:
    """轮询发布状态。"""
    job = _publish_jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Publish job {job_id} not found")
    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "note_url": job.get("note_url", ""),
        "error": job.get("error", ""),
        "elapsed_ms": job.get("elapsed_ms", 0),
        "progress_step": job.get("progress_step", ""),
        "progress_detail": job.get("progress_detail", ""),
        "test_task_id": job.get("test_task_id", ""),
    }


@router.get("/api/first3s/publish-preview")
async def publish_preview(variant_id: str = "", regenerate: str = "") -> dict:
    """预览发布内容（不实际发布）。regenerate=1 时强制重新 LLM 生成。"""
    from apps.growth_lab.services.xhs_publisher import build_publish_content

    store = _get_store()
    variant = store.get_first3s_variant(variant_id) if variant_id else None
    if not variant:
        raise HTTPException(404, "First3sVariant not found")

    hook_script = variant.get("hook_script", {})
    spec = None
    sp_id = variant.get("source_selling_point_id", "")
    if sp_id:
        spec = store.get_selling_point_spec(sp_id)

    spec_dict = spec if isinstance(spec, dict) else (spec.model_dump() if hasattr(spec, "model_dump") else None)

    content: dict | None = None
    ai_generated = False
    try:
        from apps.growth_lab.services.publish_content_compiler import PublishContentCompiler
        compiler = PublishContentCompiler()
        annotations = []
        if sp_id and hasattr(store, "list_expert_annotations"):
            annotations = store.list_expert_annotations(
                where={"spec_id": sp_id}, limit=10,
            )
        content = await compiler.compile(hook_script, spec_dict, annotations or None)
        ai_generated = True
    except Exception:
        logger.warning("[PublishPreview] LLM compile failed, fallback to rules", exc_info=True)

    if content is None:
        content = build_publish_content(hook_script, spec)

    content["video_url"] = variant.get("generated_video_url", "")
    content["variant_id"] = variant_id
    content["ai_generated"] = ai_generated
    return content


# ── API: First3s / 小红书登录 ─────────────────────────────────

_login_jobs: dict[str, dict[str, Any]] = {}


@router.get("/api/first3s/xhs-login-status")
async def xhs_login_status() -> dict:
    """检查小红书登录态是否有效。"""
    from apps.growth_lab.services.xhs_publisher import _is_storage_state_valid
    ss = _is_storage_state_valid()
    if ss:
        import json as _json
        meta_path = Path(ss).with_suffix(".meta.json")
        exported_at = ""
        if meta_path.exists():
            try:
                meta = _json.loads(meta_path.read_text())
                exported_at = meta.get("exported_at", "")
            except Exception:
                pass
        return {"logged_in": True, "exported_at": exported_at}
    return {"logged_in": False, "exported_at": ""}


@router.post("/api/first3s/xhs-login")
async def xhs_login() -> dict:
    """启动浏览器扫码登录小红书，异步完成后保存 storage_state。"""
    import asyncio

    job_id = __import__("uuid").uuid4().hex[:16]
    _login_jobs[job_id] = {"status": "pending", "step": "starting"}

    async def _run_login() -> None:
        _login_jobs[job_id]["status"] = "running"
        try:
            from playwright.async_api import async_playwright
            _login_jobs[job_id]["step"] = "launching_browser"

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(viewport={"width": 1400, "height": 900})
                page = await context.new_page()

                _login_jobs[job_id]["step"] = "navigating"
                await page.goto("https://creator.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                _login_jobs[job_id]["step"] = "waiting_for_login"

                for i in range(120):
                    await page.wait_for_timeout(2000)
                    url = page.url.lower()
                    if "login" not in url and ("creator" in url or "home" in url):
                        break
                    try:
                        avatar = page.locator('[class*="avatar"], [class*="user-info"], [class*="nickname"]')
                        if await avatar.count() > 0:
                            break
                    except Exception:
                        pass
                else:
                    _login_jobs[job_id].update({"status": "failed", "error": "登录超时(4分钟)"})
                    await context.close()
                    await browser.close()
                    return

                _login_jobs[job_id]["step"] = "exporting"
                from apps.growth_lab.services.xhs_publisher import _SESSIONS_DIR
                _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
                ss_path = _SESSIONS_DIR / "xhs_state.json"
                await context.storage_state(path=str(ss_path))

                import json as _json
                from datetime import datetime, timezone
                meta_path = ss_path.with_suffix(".meta.json")
                meta_path.write_text(
                    _json.dumps({"exported_at": datetime.now(tz=timezone.utc).isoformat()}, ensure_ascii=False),
                    encoding="utf-8",
                )

                await context.close()
                await browser.close()
                _login_jobs[job_id].update({"status": "success", "step": "done"})

        except Exception as e:
            logger.exception("[XHSLogin] failed: %s", e)
            _login_jobs[job_id].update({"status": "failed", "error": str(e)})

    asyncio.create_task(_run_login())
    return {"job_id": job_id, "status": "pending"}


@router.get("/api/first3s/xhs-login-status/{job_id}")
async def xhs_login_job_status(job_id: str) -> dict:
    """轮询扫码登录任务状态。"""
    job = _login_jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Login job {job_id} not found")
    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "step": job.get("step", ""),
        "error": job.get("error", ""),
    }


# ── API: Board / TestTask ────────────────────────────────────

@router.get("/api/board/tasks")
async def list_test_tasks(
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    store = _get_store()
    where = {}
    if status:
        where["status"] = status
    items = store.list_test_tasks(where=where, limit=limit, offset=offset)
    total = store._count("test_tasks", where=where if where else None)
    return {"items": items, "total": total}


@router.post("/api/board/tasks")
async def create_test_task(req: TestTaskCreate) -> dict:
    from apps.growth_lab.schemas.test_task import TestTask
    task = TestTask(**req.model_dump())
    store = _get_store()
    store.save_test_task(task.model_dump())
    return task.model_dump()


@router.post("/api/board/tasks/{task_id}/result")
async def add_result_snapshot(task_id: str, req: ResultSnapshotCreate) -> dict:
    from apps.growth_lab.schemas.test_task import ResultSnapshot
    store = _get_store()
    task = store.get_test_task(task_id)
    if not task:
        raise HTTPException(404, f"TestTask {task_id} not found")
    snapshot = ResultSnapshot(task_id=task_id, **req.model_dump(exclude={"task_id"}))
    store.save_result_snapshot(snapshot.model_dump())
    return snapshot.model_dump()


@router.get("/api/board/tasks/{task_id}/results")
async def list_task_results(task_id: str) -> dict:
    store = _get_store()
    items = store.list_result_snapshots(task_id)
    return {"items": items, "total": len(items)}


@router.post("/api/board/tasks/{task_id}/amplify")
async def create_amplification_plan(task_id: str) -> dict:
    """基于测试结果生成放大建议。"""
    from apps.growth_lab.services.amplification_planner import AmplificationPlanner
    planner = AmplificationPlanner()
    store = _get_store()
    task = store.get_test_task(task_id)
    if not task:
        raise HTTPException(404, f"TestTask {task_id} not found")
    results = store.list_result_snapshots(task_id)
    plan = await planner.suggest(task, results)
    store.save_amplification_plan(plan.model_dump())
    return plan.model_dump()


class BindNoteRequest(BaseModel):
    note_id: str = ""
    note_url: str = ""


@router.patch("/api/board/tasks/{task_id}/bind-note")
async def bind_note(task_id: str, req: BindNoteRequest) -> dict:
    """手动绑定小红书笔记 ID 到测试任务。"""
    store = _get_store()
    task = store.get_test_task(task_id)
    if not task:
        raise HTTPException(404, f"TestTask {task_id} not found")

    note_id = req.note_id.strip()
    if not note_id and req.note_url:
        note_id = _extract_note_id(req.note_url)
    if not note_id:
        raise HTTPException(400, "无法提取笔记 ID，请检查链接或手动输入")

    task["xhs_note_id"] = note_id
    if req.note_url:
        task["xhs_note_url"] = req.note_url.strip()
    store.save_test_task(task)
    return {"task_id": task_id, "xhs_note_id": note_id}


@router.post("/api/board/tasks/{task_id}/sync-metrics")
async def sync_note_metrics(task_id: str) -> dict:
    """从小红书回采笔记互动数据并写入 ResultSnapshot。"""
    from apps.growth_lab.services.note_metrics_syncer import NoteMetricsSyncer
    from apps.growth_lab.schemas.test_task import ResultSnapshot

    store = _get_store()
    task = store.get_test_task(task_id)
    if not task:
        raise HTTPException(404, f"TestTask {task_id} not found")
    note_id = task.get("xhs_note_id", "")
    if not note_id:
        raise HTTPException(400, "该任务尚未关联笔记 ID，请先绑定")

    syncer = NoteMetricsSyncer(headless=True)
    try:
        metrics = await syncer.fetch(note_id)
    except Exception as exc:
        logger.exception("[sync-metrics] syncer.fetch raised: %s", exc)
        raise HTTPException(502, f"回采异常: {exc}")
    if not metrics:
        raise HTTPException(502, f"回采数据失败 (note_id={note_id})，请检查登录态或笔记是否可访问")

    note_status = metrics.get("note_status", "")
    note_status_msg = metrics.get("note_status_msg", "")
    audit_status = metrics.get("audit_status", -1)

    today = __import__("datetime").date.today().isoformat()
    snapshot = ResultSnapshot(
        task_id=task_id,
        date=today,
        liked_count=metrics.get("liked_count"),
        collected_count=metrics.get("collected_count"),
        comment_count=metrics.get("comment_count"),
        share_count=metrics.get("share_count"),
        view_count=metrics.get("view_count"),
        rise_fans_count=metrics.get("rise_fans_count"),
        notes=note_status_msg or f"自动回采 (来源: {metrics.get('source', '')})",
        raw_data=metrics,
    )
    store.save_result_snapshot(snapshot.model_dump())

    if audit_status == 1:
        task["xhs_review_status"] = "approved"
    elif audit_status == 0:
        task["xhs_review_status"] = "under_review"
    elif audit_status == 2:
        task["xhs_review_status"] = "rejected"
    elif note_status in ("under_review", "rejected", "hidden"):
        task["xhs_review_status"] = note_status
    elif task.get("xhs_review_status") in ("pending",):
        task["xhs_review_status"] = "approved"
    store.save_test_task(task)

    resp: dict[str, Any] = {"snapshot_id": snapshot.snapshot_id, "metrics": metrics}
    if note_status:
        resp["note_status"] = note_status
        resp["note_status_msg"] = note_status_msg
    return resp


# ── API: Assets ──────────────────────────────────────────────

@router.get("/api/assets/cards")
async def list_asset_cards(
    status: str = "",
    asset_type: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    store = _get_store()
    where: dict[str, Any] = {}
    if status:
        where["status"] = status
    if asset_type:
        where["asset_type"] = asset_type
    items = store.list_asset_performance_cards(where=where, limit=limit, offset=offset)
    total = store._count("asset_performance_cards", where=where if where else None)
    return {"items": items, "total": total}


@router.get("/api/assets/templates")
async def list_templates(status: str = "", limit: int = 50, offset: int = 0) -> dict:
    store = _get_store()
    where = {}
    if status:
        where["status"] = status
    items = store.list_pattern_templates(where=where, limit=limit, offset=offset)
    total = store._count("pattern_templates", where=where if where else None)
    return {"items": items, "total": total}


@router.post("/api/assets/promote-high-performers")
async def promote_high_performers(workspace_id: str = "") -> dict:
    """扫描测试结果，沉淀高表现资产。"""
    from apps.growth_lab.services.asset_graph_service import AssetGraphService
    svc = AssetGraphService(_get_store())
    promoted = svc.promote_high_performers(workspace_id)
    return {"promoted": len(promoted), "items": [c.model_dump() for c in promoted]}


@router.post("/api/assets/extract-patterns")
async def extract_patterns(workspace_id: str = "") -> dict:
    """从高表现资产中提取模式模板。"""
    from apps.growth_lab.services.asset_graph_service import AssetGraphService
    svc = AssetGraphService(_get_store())
    templates = svc.extract_patterns(workspace_id)
    return {"extracted": len(templates), "items": [t.model_dump() for t in templates]}


@router.get("/api/assets/recommend/{selling_point_id}")
async def recommend_assets(selling_point_id: str, workspace_id: str = "") -> dict:
    """为卖点推荐可复用资产。"""
    from apps.growth_lab.services.asset_graph_service import AssetGraphService
    svc = AssetGraphService(_get_store())
    recs = svc.recommend_for_selling_point(selling_point_id, workspace_id)
    return {"recommendations": [r.model_dump() for r in recs]}


# ── API: 全链路闭环 ──────────────────────────────────────────

@router.post("/api/loop/feedback-to-radar")
async def feedback_to_radar(workspace_id: str = "") -> dict:
    """将高表现模式反馈到 Radar 形成闭环。"""
    from apps.growth_lab.services.asset_graph_service import AssetGraphService
    svc = AssetGraphService(_get_store())
    feedback_opps = svc.feedback_to_radar(workspace_id)
    return {"feedback_opportunities": len(feedback_opps), "items": feedback_opps}


# ── API: 视觉工作台（无限画布） ──────────────────────────────

class WorkspaceCompileRequest(BaseModel):
    source_spec_id: str = ""
    product_name: str = ""
    audience: str = ""
    output_types: list[str] = Field(default_factory=lambda: ["main_image"])
    style_refs: list[str] = Field(default_factory=list)
    scenario_refs: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    requested_counts: dict[str, int] = Field(default_factory=dict)
    workspace_id: str = ""
    brand_id: str = ""
    template_overrides: dict[str, str] = Field(default_factory=dict)
    # {frame_key: True} → 强制"仅借框架"：骨架化并按 intent 重参数化，丢弃品类细节
    borrow_frame_only: dict[str, bool] = Field(default_factory=dict)


class WorkspaceGenerateNodeRequest(BaseModel):
    count: int = 1


_SOURCE_KIND_ZH = {
    "yaml_simple": "精简模板",
    "yaml_v2": "专家资产（Schema v2）",
    "md_table": "专家 MD（表格）",
    "md_sections": "专家 MD（分节）",
}


def _template_summary(t) -> dict:
    """返回 workspace templates 列表展示用的精简结构。"""
    return {
        "template_id": t.template_id,
        "category": t.category,
        "name": t.name,
        "description": t.description,
        "version": t.version,
        "slot_count": len(t.slots),
        "source_kind": t.source_kind,
        "source_kind_label": _SOURCE_KIND_ZH.get(t.source_kind, t.source_kind),
        "source_path": t.yaml_source_path,
    }


@router.get("/api/workspace/templates")
async def list_workspace_templates(category: str = "") -> dict:
    """列出业务专家模板。"""
    from apps.growth_lab.services.template_library import get_template_library
    lib = get_template_library()
    items = lib.list_by_category(category) if category else lib.list_all()
    return {
        "items": [
            {
                **_template_summary(t),
                "slots": [s.model_dump() for s in t.slots],
            }
            for t in items
        ],
    }


@router.get("/api/workspace/template/{template_id}")
async def get_workspace_template(template_id: str) -> dict:
    """获取单个模板（含 Schema v2 完整上下文，供节点溯源面板使用）。"""
    from apps.growth_lab.services.template_library import get_template_library
    from pathlib import Path as _P
    lib = get_template_library()
    t = lib.get(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    data = t.model_dump()
    data["source_kind_label"] = _SOURCE_KIND_ZH.get(t.source_kind, t.source_kind)
    # 展示友好路径
    try:
        data["source_path_display"] = str(_P(t.yaml_source_path).name) if t.yaml_source_path else ""
    except Exception:
        data["source_path_display"] = t.yaml_source_path or ""
    return data


@router.post("/api/workspace/compile")
async def compile_workspace(req: WorkspaceCompileRequest) -> dict:
    """从 IntentContext 编译一个新的 CompilePlan + Frames + Nodes。"""
    from apps.growth_lab.schemas.visual_workspace import IntentContext
    from apps.growth_lab.services.visual_plan_compiler import VisualPlanCompiler

    intent = IntentContext(
        product_name=req.product_name,
        audience=req.audience,
        output_types=req.output_types or ["main_image"],
        style_refs=req.style_refs,
        scenario_refs=req.scenario_refs,
        must_have=req.must_have,
        avoid=req.avoid,
        requested_counts=req.requested_counts,
        source_spec_id=req.source_spec_id,
    )
    # 若传入了 source_spec_id 且字段不全，尝试用 spec 回填
    store = _get_store()
    if req.source_spec_id:
        spec = store.get_selling_point_spec(req.source_spec_id)
        if spec:
            if not intent.product_name:
                intent.product_name = spec.get("core_claim", "")
            if not intent.must_have:
                intent.must_have = list(spec.get("supporting_claims", []))[:3]
            if not intent.audience:
                people = spec.get("target_people", [])
                intent.audience = "、".join(people[:2]) if people else ""

    compiler = VisualPlanCompiler()
    plan, frames, nodes = compiler.compile(
        intent,
        template_overrides=req.template_overrides or None,
        borrow_frame_only=req.borrow_frame_only or None,
    )
    plan_dict = plan.model_dump(mode="json")
    plan_dict["workspace_id"] = req.workspace_id
    plan_dict["brand_id"] = req.brand_id
    store.save_workspace_plan(plan_dict)
    for f in frames:
        store.save_workspace_frame(f.model_dump(mode="json"))
    for n in nodes:
        store.save_workspace_node(n.model_dump(mode="json"))

    return {
        "plan_id": plan.plan_id,
        "frame_count": len(frames),
        "node_count": len(nodes),
    }


@router.get("/api/workspace/plan/{plan_id}")
async def get_workspace_plan(plan_id: str) -> dict:
    """返回一个 plan 的完整内容（含 frames/nodes/variants 的简要索引）。"""
    store = _get_store()
    plan = store.get_workspace_plan(plan_id)
    if not plan:
        raise HTTPException(404, "plan not found")
    frames = store.list_workspace_frames(plan_id)
    nodes = store.list_workspace_nodes(plan_id=plan_id)
    # 加载每个节点的 active variant URL
    variants_by_node: dict[str, list[dict]] = {}
    for n in nodes:
        vs = store.list_workspace_variants(n["node_id"])
        variants_by_node[n["node_id"]] = vs
    return {
        "plan": plan,
        "frames": frames,
        "nodes": nodes,
        "variants_by_node": variants_by_node,
    }


@router.get("/api/workspace/plans")
async def list_workspace_plans(limit: int = 50, offset: int = 0) -> dict:
    store = _get_store()
    items = store.list_workspace_plans(limit=limit, offset=offset)
    return {
        "items": [
            {
                "plan_id": p.get("plan_id", ""),
                "status": p.get("status", "draft"),
                "product_name": (p.get("intent") or {}).get("product_name", ""),
                "frame_count": len(p.get("frame_ids", []) or []),
                "created_at": p.get("created_at", ""),
                "updated_at": p.get("updated_at", ""),
            }
            for p in items
        ],
        "total": store._count("workspace_plans"),
    }


@router.get("/api/workspace/gallery")
async def workspace_gallery(plan_limit: int = 20, variant_limit_per_plan: int = 24) -> dict:
    """返回"生图历史图集"：最近若干 plan + 其下所有已出图变体的缩略图与上下文。

    前端用它做跨任务的图集入口：点缩略图即可跳回对应 plan 的对应节点并带上 variant_id。
    """
    store = _get_store()
    plans = store.list_workspace_plans(limit=plan_limit, offset=0)
    groups: list[dict[str, Any]] = []
    for plan in plans:
        plan_id = plan.get("plan_id", "")
        if not plan_id:
            continue
        nodes = store.list_workspace_nodes(plan_id=plan_id)
        node_by_id = {n.get("node_id"): n for n in nodes if n.get("node_id")}
        frames = store.list_workspace_frames(plan_id)
        frame_by_id = {f.get("frame_id"): f for f in frames if f.get("frame_id")}

        items: list[dict[str, Any]] = []
        for n in nodes:
            vs = store.list_workspace_variants(n.get("node_id", ""))
            for v in vs:
                url = v.get("asset_url") or ""
                if not url:
                    continue
                items.append({
                    "variant_id": v.get("variant_id", ""),
                    "node_id": n.get("node_id", ""),
                    "plan_id": plan_id,
                    "frame_id": n.get("frame_id", ""),
                    "frame_key": (frame_by_id.get(n.get("frame_id"), {}) or {}).get("frame_key", ""),
                    "asset_url": url,
                    "role": n.get("role") or "",
                    "result_type": n.get("result_type", ""),
                    "aspect_ratio": n.get("aspect_ratio", "1:1"),
                    "status": v.get("status", ""),
                    "is_active": v.get("variant_id") == n.get("active_variant_id"),
                    "updated_at": v.get("updated_at", "") or v.get("created_at", ""),
                    "mode": (v.get("extra") or {}).get("mode", ""),
                    "base_variant_id": (v.get("extra") or {}).get("base_variant_id", ""),
                    "edit_instruction": (v.get("extra") or {}).get("edit_instruction", ""),
                })
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        items = items[: max(1, int(variant_limit_per_plan))]
        if not items:
            continue
        groups.append({
            "plan_id": plan_id,
            "product_name": (plan.get("intent") or {}).get("product_name", "") or "未命名任务",
            "audience": (plan.get("intent") or {}).get("audience", ""),
            "status": plan.get("status", ""),
            "updated_at": plan.get("updated_at", ""),
            "variant_count": len(items),
            "variants": items,
        })
    return {"groups": groups, "plan_count": len(groups)}


@router.post("/api/workspace/node/{node_id}/generate")
async def generate_workspace_node(node_id: str, req: WorkspaceGenerateNodeRequest) -> dict:
    """为单个节点触发一次生成（可指定 count 张变体）。"""
    from apps.growth_lab.services.visual_node_generator import VisualNodeGenerator
    gen = VisualNodeGenerator(_get_store())
    try:
        batch_id = gen.generate_for_node(node_id, count=max(1, int(req.count or 1)))
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return {"batch_id": batch_id, "node_id": node_id}


class WorkspaceEditVariantRequest(BaseModel):
    user_prompt: str = ""
    count: int = 1
    base_variant_id: str = ""


@router.post("/api/workspace/node/{node_id}/edit-variant")
async def edit_workspace_variant(node_id: str, req: WorkspaceEditVariantRequest) -> dict:
    """对话式图生图微调：以 active（或指定）变体为底图入队 mode=edit 新变体。"""
    from apps.growth_lab.services.visual_node_generator import VisualNodeGenerator
    gen = VisualNodeGenerator(_get_store())
    try:
        batch_id = gen.edit_variant(
            node_id,
            user_prompt=req.user_prompt or "",
            base_variant_id=req.base_variant_id or "",
            count=max(1, int(req.count or 1)),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"batch_id": batch_id, "node_id": node_id, "mode": "edit"}


@router.post("/api/workspace/frame/{frame_id}/generate-all")
async def generate_workspace_frame(frame_id: str) -> dict:
    """批量生成一个 Frame 内所有 draft 节点，每个节点生成一张。"""
    from apps.growth_lab.services.visual_node_generator import VisualNodeGenerator
    store = _get_store()
    nodes = store.list_workspace_nodes(frame_id=frame_id)
    if not nodes:
        raise HTTPException(404, "frame has no nodes")
    gen = VisualNodeGenerator(store)
    batch_ids: list[str] = []
    for n in nodes:
        if n.get("status") in {"generated", "approved"}:
            continue
        batch_ids.append(gen.generate_for_node(n["node_id"], count=1))
    return {"batch_ids": batch_ids, "triggered_nodes": len(batch_ids)}


@router.get("/api/workspace/batch/{batch_id}/status")
async def workspace_batch_status(batch_id: str) -> dict:
    """轮询 batch 进度（同 main-image 批量 queue 的格式）。"""
    from apps.growth_lab.services.visual_node_generator import get_batch_queue
    q = get_batch_queue(batch_id)
    if q is None:
        raise HTTPException(404, "batch not found")
    return q.get_batch_status(batch_id)


@router.get("/api/workspace/node/{node_id}")
async def get_workspace_node(node_id: str) -> dict:
    store = _get_store()
    n = store.get_workspace_node(node_id)
    if not n:
        raise HTTPException(404, "node not found")
    variants = store.list_workspace_variants(node_id)
    return {"node": n, "variants": variants}


class WorkspaceCopilotProposeRequest(BaseModel):
    user_prompt: str = ""


@router.get("/api/workspace/node/{node_id}/suggest-actions")
async def workspace_suggest_actions(node_id: str, use_llm: int = 0) -> dict:
    """右栏"建议动作区"——返回 3-5 条可一键执行的建议。"""
    from apps.growth_lab.services.workspace_copilot import get_workspace_copilot
    store = _get_store()
    node = store.get_workspace_node(node_id)
    if not node:
        raise HTTPException(404, "node not found")
    intent = (store.get_workspace_plan(node.get("plan_id", "")) or {}).get("intent") or {}
    copilot = get_workspace_copilot()
    if use_llm:
        actions = await copilot.suggest_actions_llm(node, intent)
    else:
        actions = copilot.suggest_actions(node, intent)
    return {"actions": actions}


@router.post("/api/workspace/node/{node_id}/propose-edit")
async def workspace_propose_edit(
    node_id: str, req: WorkspaceCopilotProposeRequest,
) -> dict:
    """右栏"对话编辑器"——把用户指令转换为结构化执行提案（不直接改库）。"""
    from apps.growth_lab.services.workspace_copilot import get_workspace_copilot
    store = _get_store()
    node = store.get_workspace_node(node_id)
    if not node:
        raise HTTPException(404, "node not found")
    intent = (store.get_workspace_plan(node.get("plan_id", "")) or {}).get("intent") or {}
    copilot = get_workspace_copilot()
    proposal = await copilot.propose_edit(node, req.user_prompt, intent)
    return {"proposal": proposal}


class WorkspaceCopilotApplyRequest(BaseModel):
    prompt_delta: str = ""
    copy_delta: str = ""
    generate_count: int = 1


@router.post("/api/workspace/node/{node_id}/apply-proposal")
async def workspace_apply_proposal(node_id: str, req: WorkspaceCopilotApplyRequest) -> dict:
    """把提案落到节点：更新 visual_spec / copy_spec 后立即触发一次生成。"""
    from apps.growth_lab.services.visual_node_generator import VisualNodeGenerator
    store = _get_store()
    node = store.get_workspace_node(node_id)
    if not node:
        raise HTTPException(404, "node not found")
    changed = False
    if req.prompt_delta:
        # 把 delta 追加到 visual_spec（而不是覆盖），保留溯源
        orig = node.get("visual_spec", "")
        node["visual_spec"] = (orig + "\n【调整】" + req.prompt_delta).strip()
        changed = True
    if req.copy_delta:
        orig = node.get("copy_spec", "")
        node["copy_spec"] = (orig + "\n【调整】" + req.copy_delta).strip() if orig else req.copy_delta
        changed = True
    if changed:
        node["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        store.save_workspace_node(node)

    gen = VisualNodeGenerator(store)
    batch_id = gen.generate_for_node(node_id, count=max(1, int(req.generate_count or 1)))
    return {"ok": True, "batch_id": batch_id, "node": node}


class WorkspaceCompetitorRequest(BaseModel):
    image_url: str = ""


@router.post("/api/workspace/node/{node_id}/deconstruct-competitor")
async def workspace_deconstruct_competitor(
    node_id: str, req: WorkspaceCompetitorRequest,
) -> dict:
    """对竞品节点触发一次 32 维度拆解；结果写入节点 payload。"""
    from apps.growth_lab.services.competitor_deconstructor import get_competitor_deconstructor
    store = _get_store()
    node = store.get_workspace_node(node_id)
    if not node:
        raise HTTPException(404, "node not found")
    dec = get_competitor_deconstructor()
    analysis = await dec.deconstruct(req.image_url)
    # 写回节点 extra + 参考链接
    node.setdefault("extra", {})
    node["extra"]["competitor_analysis"] = analysis
    node["extra"]["competitor_image_url"] = req.image_url
    node["status"] = "reviewed"
    node["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    store.save_workspace_node(node)
    return {"ok": True, "analysis": analysis, "node": node}


class WorkspaceNodeUpdateRequest(BaseModel):
    active_variant_id: str | None = None
    status: str | None = None
    copy_spec: str | None = None
    visual_spec: str | None = None
    canvas_x: float | None = None
    canvas_y: float | None = None


@router.patch("/api/workspace/node/{node_id}")
async def update_workspace_node(node_id: str, req: WorkspaceNodeUpdateRequest) -> dict:
    store = _get_store()
    n = store.get_workspace_node(node_id)
    if not n:
        raise HTTPException(404, "node not found")
    changed = False
    for field in ("active_variant_id", "status", "copy_spec", "visual_spec"):
        val = getattr(req, field)
        if val is not None:
            n[field] = val
            changed = True
    if req.canvas_x is not None:
        n["canvas_x"] = float(req.canvas_x)
        changed = True
    if req.canvas_y is not None:
        n["canvas_y"] = float(req.canvas_y)
        changed = True
    if changed:
        n["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        store.save_workspace_node(n)
    return {"ok": True, "node": n}


# ── Sprint 4: replan_frame + 导出 + 资产图谱回流 ────────────

class WorkspaceReplanRequest(BaseModel):
    new_template_id: str = ""
    keep_assets: bool = True


@router.post("/api/workspace/frame/{frame_id}/replan")
async def workspace_replan_frame(frame_id: str, req: WorkspaceReplanRequest) -> dict:
    """切换 Frame 模板（保留已生成资产，做 slot 级别重绑定）。"""
    from apps.growth_lab.services.frame_replanner import FrameReplanner
    if not req.new_template_id:
        raise HTTPException(400, "new_template_id is required")
    replanner = FrameReplanner(_get_store())
    try:
        result = replanner.replan(
            frame_id=frame_id,
            new_template_id=req.new_template_id,
            keep_assets=req.keep_assets,
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True, **result}


@router.get("/api/workspace/node/{node_id}/final-card")
async def workspace_final_card(node_id: str) -> dict:
    """产出最终结果卡（交付给 Command Center / 复盘使用）。"""
    from apps.growth_lab.services.workspace_exporter import WorkspaceExporter
    exporter = WorkspaceExporter(_get_store())
    try:
        card = exporter.render_final_result_card(node_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"card": card}


@router.get("/api/workspace/plan/{plan_id}/export")
async def workspace_export_zip(plan_id: str):
    """下载 plan 的交付包（ZIP）。"""
    from apps.growth_lab.services.workspace_exporter import WorkspaceExporter
    exporter = WorkspaceExporter(_get_store())
    try:
        data, filename = exporter.export_plan_zip(plan_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/api/workspace/plan/{plan_id}/push-to-asset-graph")
async def workspace_push_to_asset_graph(plan_id: str) -> dict:
    """把已 approved/reviewed 的节点推送到资产图谱。"""
    from apps.growth_lab.services.workspace_exporter import WorkspaceExporter
    exporter = WorkspaceExporter(_get_store())
    try:
        pushed = exporter.push_to_asset_graph(plan_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True, "pushed_count": len(pushed), "assets": pushed}


# ── API: 视频处理 ────────────────────────────────────────────

@router.post("/api/video/process")
async def process_video(video_path: str = "") -> dict:
    """处理上传视频：切片 + 转写 + 钩子识别。"""
    if not video_path:
        raise HTTPException(400, "video_path is required")
    from apps.growth_lab.services.video_processor import VideoProcessor
    processor = VideoProcessor()
    result = await processor.process_video(video_path)
    return {
        "video_id": result.video_id,
        "clip_path": result.clip_path,
        "transcript": result.full_transcript_text,
        "hook_analysis": {
            "type": result.hook_analysis.detected_hook_type,
            "conflict": result.hook_analysis.conflict_type,
            "confidence": result.hook_analysis.confidence,
        } if result.hook_analysis else None,
        "metadata": {
            "duration": result.metadata.duration_seconds,
            "resolution": f"{result.metadata.width}x{result.metadata.height}",
            "has_audio": result.metadata.has_audio,
        } if result.metadata else None,
        "processing_ms": result.processing_ms,
        "error": result.error,
    }
