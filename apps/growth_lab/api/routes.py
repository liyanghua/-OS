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

@router.get("/api/compiler/references")
async def get_references() -> dict:
    """返回货架/前3秒参考案例（从 PatternTemplate 和 AssetPerformanceCard 拉取）。"""
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

    shelf_refs = shelf_templates + shelf_assets
    first3s_refs = first3s_templates

    if not shelf_refs:
        shelf_refs = [
            {"name": "爆款标题公式：痛点 + 解决方案 + 差异化", "template_text": "例：告别 XX 烦恼，XX 产品让你 XX"},
            {"name": "数字型标题：具体数据增强说服力", "template_text": "例：3天见效 / 月销10万+ / 98%好评"},
            {"name": "场景型标题：切入具体使用场景", "template_text": "例：露营必备 / 宿舍神器 / 通勤好物"},
        ]
    if not first3s_refs:
        first3s_refs = [
            {"name": "悬念型钩子：先抛问题再给答案", "hook_text": "例：你还在为 XX 苦恼吗？"},
            {"name": "共鸣型钩子：直击目标人群痛点", "hook_text": "例：每次 XX 的时候是不是特别 XX？"},
            {"name": "反转型钩子：先否定再肯定", "hook_text": "例：我以为 XX 没用，直到我试了这个…"},
        ]

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
