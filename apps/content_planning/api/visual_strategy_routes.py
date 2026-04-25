"""SOP 视觉策略编译器 API。

承接 docs/SOP_to_content_plan.md 第 12 节。
统一前缀 /content-planning/visual-strategy/*。

Phase 1-3 必备端点：
- POST  /source-documents/import           导入指定 category 下 SOP MD
- POST  /rules/extract                    抽取 RuleSpec 候选
- GET   /rules                            按过滤条件列出 RuleSpec
- GET   /rules/{id}                       单条 RuleSpec
- PATCH /rules/{id}/review                审核动作（approve/reject/...）
- POST  /rulepacks/build                  聚合 approved RuleSpec 发布 RulePack
- GET   /rulepacks                        列出 RulePack
- GET   /rulepacks/{id}                   单个 RulePack
- POST  /compile-from-content             机会卡 → 6 个 StrategyCandidate（核心入口）
- POST  /compile                          手动 ContextSpec → 6 个 StrategyCandidate
- GET   /strategy-packs/{id}              单个 VisualStrategyPack
- GET   /strategy-packs/{id}/candidates   候选列表
- POST  /candidates/{id}/brief            候选 → CreativeBrief
- PATCH /briefs/{id}                      编辑 CreativeBrief（局部覆盖）
- POST  /briefs/{id}/prompt               CreativeBrief → PromptSpec
- POST  /candidates/{id}/send-to-workbench 推送到无线画布
- POST  /feedback                         （Phase 5 路径，MVP 仅落库）
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.content_planning.schemas.context_spec import ContextSpec
from apps.content_planning.schemas.rule_pack import RulePack
from apps.content_planning.schemas.rule_spec import RuleSpec
from apps.content_planning.services.context_compiler import ContextCompiler
from apps.content_planning.services.md_ingestion_service import MDIngestionService
from apps.content_planning.services.rule_extractor import RuleExtractor
from apps.content_planning.services.rule_review_service import RuleReviewService
from apps.content_planning.services.rulepack_builder import RulePackBuilder
from apps.content_planning.storage.rule_store import RuleStore
from apps.growth_lab.schemas.creative_brief import CreativeBrief
from apps.growth_lab.schemas.feedback_record import FeedbackRecord
from apps.growth_lab.schemas.strategy_candidate import StrategyCandidate
from apps.growth_lab.schemas.visual_strategy_pack import VisualStrategyPack
from apps.growth_lab.services.feedback_engine import FeedbackEngine
from apps.growth_lab.services.strategy_compiler import StrategyCompiler
from apps.growth_lab.services.visual_brief_compiler import VisualBriefCompiler
from apps.growth_lab.services.visual_prompt_compiler import VisualPromptCompiler
from apps.growth_lab.storage.visual_strategy_store import VisualStrategyStore

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/content-planning/visual-strategy", tags=["visual_strategy"])


# ── store / service singleton 注入 ──────────────────────────────

_rule_store: RuleStore | None = None
_vs_store: VisualStrategyStore | None = None
_review_card_provider: Any = None  # 注入：根据 opportunity_id 取机会卡
_brand_profile_provider: Any = None  # 注入：根据 brand_id 取 BrandProfile
_send_to_workbench_handler: Any = None  # 注入：写回 plan_store 的 quick_draft / saved_prompts


def configure(
    *,
    rule_store: RuleStore | None = None,
    visual_strategy_store: VisualStrategyStore | None = None,
    review_card_provider: Any = None,
    brand_profile_provider: Any = None,
    send_to_workbench_handler: Any = None,
) -> None:
    """允许 app.py 在启动时注入共享 store 与 provider。"""
    global _rule_store, _vs_store, _review_card_provider, _brand_profile_provider, _send_to_workbench_handler
    if rule_store is not None:
        _rule_store = rule_store
    if visual_strategy_store is not None:
        _vs_store = visual_strategy_store
    if review_card_provider is not None:
        _review_card_provider = review_card_provider
    if brand_profile_provider is not None:
        _brand_profile_provider = brand_profile_provider
    if send_to_workbench_handler is not None:
        _send_to_workbench_handler = send_to_workbench_handler


def _rs() -> RuleStore:
    global _rule_store
    if _rule_store is None:
        _rule_store = RuleStore()
    return _rule_store


def _vs() -> VisualStrategyStore:
    global _vs_store
    if _vs_store is None:
        _vs_store = VisualStrategyStore()
    return _vs_store


# ── request models ─────────────────────────────────────────────

class ImportRequest(BaseModel):
    category: str
    overwrite: bool = False


class ExtractRequest(BaseModel):
    category: str
    use_llm: bool = False
    source_document_ids: list[str] | None = None


class ReviewPatchRequest(BaseModel):
    action: Literal["approve", "reject", "request_edit", "update_weight", "patch"]
    reviewer: str = ""
    comments: str = ""
    new_weight: float | None = None
    patch: dict[str, Any] | None = None


class BuildRequest(BaseModel):
    category: str
    version: str | None = None
    description: str = ""
    activate: bool = True


class CompileFromContentRequest(BaseModel):
    opportunity_id: str
    category: str | None = None
    rule_pack_id: str | None = None
    scene: Literal["taobao_main_image", "xhs_cover", "detail_first_screen", "video_first_frame"] = "taobao_main_image"
    selling_point_spec_id: str | None = None
    brand_id: str | None = None
    store_visual_overrides: dict[str, Any] | None = None
    product_overrides: dict[str, Any] | None = None


class CompileManualRequest(BaseModel):
    category: str
    scene: Literal["taobao_main_image", "xhs_cover", "detail_first_screen", "video_first_frame"] = "taobao_main_image"
    rule_pack_id: str | None = None
    product: dict[str, Any] | None = None
    store_visual: dict[str, Any] | None = None
    audience: dict[str, Any] | None = None
    brand_id: str | None = None


class BriefRequest(BaseModel):
    overrides: dict[str, Any] | None = None


class BriefPatchRequest(BaseModel):
    canvas: dict[str, Any] | None = None
    scene: dict[str, Any] | None = None
    product: dict[str, Any] | None = None
    style: dict[str, Any] | None = None
    people: dict[str, Any] | None = None
    copywriting: dict[str, Any] | None = None
    negative: list[str] | None = None


class PromptRequest(BaseModel):
    provider: str = "comfyui"


class SendToWorkbenchRequest(BaseModel):
    opportunity_id: str
    notes: str = ""


class FeedbackRequest(BaseModel):
    image_variant_id: str = ""
    strategy_candidate_id: str
    decision: Literal["enter_test_pool", "revise", "reject", "winner"] = "enter_test_pool"
    expert_score: dict[str, Any] | None = None
    business_metrics: dict[str, Any] | None = None
    comments: str = ""
    rule_ids: list[str] | None = None


# ── routes ─────────────────────────────────────────────────────

# ── Phase 1：SOP → RuleSpec 生产线 ──────────────────────────────

@router.post("/source-documents/import")
def import_source_documents(req: ImportRequest) -> dict[str, Any]:
    service = MDIngestionService(_rs())
    docs = service.ingest_category(req.category)
    return {
        "category": req.category,
        "imported": len(docs),
        "documents": [d.model_dump(mode="json") for d in docs],
    }


@router.post("/rules/extract")
def extract_rules(req: ExtractRequest) -> dict[str, Any]:
    extractor = RuleExtractor(_rs(), use_llm=req.use_llm)
    docs = _rs().list_source_documents(category=req.category)
    target_docs = docs
    if req.source_document_ids:
        target_docs = [d for d in docs if d.get("id") in req.source_document_ids]
    if not target_docs:
        raise HTTPException(status_code=404, detail=f"未找到 category={req.category} 的 SourceDocument")

    from apps.content_planning.schemas.source_document import SourceDocument

    total: list[RuleSpec] = []
    for raw in target_docs:
        sd = SourceDocument.model_validate(raw)
        total.extend(extractor.extract_from_source(sd))

    return {
        "category": req.category,
        "extracted": len(total),
        "rule_ids": [r.id for r in total],
    }


@router.get("/rules")
def list_rules(
    category: str | None = None,
    dimension: str | None = None,
    review_status: str | None = None,
    rule_pack_id: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    rows = _rs().list_rule_specs(
        category=category,
        dimension=dimension,
        review_status=review_status,
        rule_pack_id=rule_pack_id,
        limit=limit,
    )
    return {"count": len(rows), "rules": rows}


@router.get("/rules/{rule_id}")
def get_rule(rule_id: str) -> dict[str, Any]:
    raw = _rs().get_rule_spec(rule_id)
    if not raw:
        raise HTTPException(status_code=404, detail="rule not found")
    return raw


@router.patch("/rules/{rule_id}/review")
def review_rule(rule_id: str, req: ReviewPatchRequest) -> dict[str, Any]:
    service = RuleReviewService(_rs())
    rule = service.review(
        rule_id,
        action=req.action,
        reviewer=req.reviewer,
        comments=req.comments,
        new_weight=req.new_weight,
        patch=req.patch,
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return rule.model_dump(mode="json")


@router.post("/rulepacks/build")
def build_rulepack(req: BuildRequest) -> dict[str, Any]:
    builder = RulePackBuilder(_rs())
    pack = builder.build(
        category=req.category,
        version=req.version,
        description=req.description,
        activate=req.activate,
    )
    return pack.model_dump(mode="json")


@router.get("/rulepacks")
def list_rulepacks(category: str | None = None) -> dict[str, Any]:
    rows = _rs().list_rule_packs(category=category)
    return {"count": len(rows), "rulepacks": rows}


@router.get("/rulepacks/{rule_pack_id}")
def get_rulepack(rule_pack_id: str) -> dict[str, Any]:
    raw = _rs().get_rule_pack(rule_pack_id)
    if not raw:
        raise HTTPException(status_code=404, detail="rulepack not found")
    return raw


# ── Phase 2-3：策略编译器 + Brief / Prompt ───────────────────────

def _resolve_opportunity_card(opportunity_id: str) -> dict[str, Any]:
    if _review_card_provider is None:
        raise HTTPException(status_code=503, detail="review_card_provider 未配置（app.py 启动期 configure）")
    card = _review_card_provider(opportunity_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"机会卡 {opportunity_id} 未找到")
    return card if isinstance(card, dict) else card.model_dump(mode="json")


def _resolve_brand_profile(brand_id: str | None) -> dict[str, Any] | None:
    if not brand_id or _brand_profile_provider is None:
        return None
    bp = _brand_profile_provider(brand_id)
    if bp is None:
        return None
    return bp if isinstance(bp, dict) else bp.model_dump(mode="json")


@router.post("/compile-from-content")
def compile_from_content(req: CompileFromContentRequest) -> dict[str, Any]:
    card = _resolve_opportunity_card(req.opportunity_id)
    category = req.category or card.get("category", "") or "children_desk_mat"
    bp = _resolve_brand_profile(req.brand_id)

    cc = ContextCompiler(_rs())
    ctx = cc.compile_from_opportunity(
        card,
        category=category,
        scene=req.scene,
        brand_profile=bp,
        store_visual_overrides=req.store_visual_overrides,
        product_overrides=req.product_overrides,
    )

    sc = StrategyCompiler(_rs(), _vs())
    pack = sc.compile(context=ctx, rule_pack_id=req.rule_pack_id)
    candidates = _vs().list_strategy_candidates(pack.id)
    return {
        "context_spec_id": ctx.id,
        "rule_pack_id": pack.rule_pack_id,
        "visual_strategy_pack_id": pack.id,
        "candidates": candidates,
    }


@router.post("/compile")
def compile_manual(req: CompileManualRequest) -> dict[str, Any]:
    bp = _resolve_brand_profile(req.brand_id)
    cc = ContextCompiler(_rs())
    ctx = cc.compile_manual(
        category=req.category,
        scene=req.scene,
        product=req.product,
        store_visual=req.store_visual,
        audience=req.audience,
        brand_profile=bp,
    )
    sc = StrategyCompiler(_rs(), _vs())
    pack = sc.compile(context=ctx, rule_pack_id=req.rule_pack_id)
    return {
        "context_spec_id": ctx.id,
        "rule_pack_id": pack.rule_pack_id,
        "visual_strategy_pack_id": pack.id,
        "candidates": _vs().list_strategy_candidates(pack.id),
    }


@router.get("/strategy-packs/{pack_id}")
def get_strategy_pack(pack_id: str) -> dict[str, Any]:
    raw = _vs().get_visual_strategy_pack(pack_id)
    if not raw:
        raise HTTPException(status_code=404, detail="visual strategy pack not found")
    return raw


@router.get("/strategy-packs/{pack_id}/candidates")
def list_pack_candidates(pack_id: str) -> dict[str, Any]:
    if not _vs().get_visual_strategy_pack(pack_id):
        raise HTTPException(status_code=404, detail="visual strategy pack not found")
    candidates = _vs().list_strategy_candidates(pack_id)
    return {"count": len(candidates), "candidates": candidates}


@router.post("/candidates/{candidate_id}/brief")
def build_candidate_brief(candidate_id: str, req: BriefRequest) -> dict[str, Any]:
    cand_raw = _vs().get_strategy_candidate(candidate_id)
    if not cand_raw:
        raise HTTPException(status_code=404, detail="candidate not found")
    cand = StrategyCandidate.model_validate(cand_raw)

    pack_raw = _vs().get_visual_strategy_pack(cand.visual_strategy_pack_id)
    if not pack_raw:
        raise HTTPException(status_code=404, detail="visual strategy pack not found")
    ctx_raw = _rs().get_context_spec(pack_raw.get("context_spec_id", ""))
    if not ctx_raw:
        raise HTTPException(status_code=404, detail="context_spec not found")
    ctx = ContextSpec.model_validate(ctx_raw)

    bc = VisualBriefCompiler(_vs())
    brief = bc.compile(candidate=cand, context=ctx, overrides=req.overrides)
    return brief.model_dump(mode="json")


@router.patch("/briefs/{brief_id}")
def patch_brief(brief_id: str, req: BriefPatchRequest) -> dict[str, Any]:
    raw = _vs().get_creative_brief(brief_id)
    if not raw:
        raise HTTPException(status_code=404, detail="brief not found")
    brief = CreativeBrief.model_validate(raw)
    payload = req.model_dump(exclude_none=True)
    bc = VisualBriefCompiler(_vs())
    bc._apply_overrides(brief, payload)
    _vs().save_creative_brief(brief.model_dump())
    return brief.model_dump(mode="json")


@router.post("/briefs/{brief_id}/prompt")
def build_prompt(brief_id: str, req: PromptRequest) -> dict[str, Any]:
    raw = _vs().get_creative_brief(brief_id)
    if not raw:
        raise HTTPException(status_code=404, detail="brief not found")
    brief = CreativeBrief.model_validate(raw)
    pc = VisualPromptCompiler(_vs())
    spec = pc.compile(brief=brief, provider=req.provider)  # type: ignore[arg-type]
    return spec.model_dump(mode="json")


@router.post("/candidates/{candidate_id}/send-to-workbench")
def send_to_workbench(candidate_id: str, req: SendToWorkbenchRequest) -> dict[str, Any]:
    cand_raw = _vs().get_strategy_candidate(candidate_id)
    if not cand_raw:
        raise HTTPException(status_code=404, detail="candidate not found")
    cand = StrategyCandidate.model_validate(cand_raw)

    if not cand.creative_brief_id:
        raise HTTPException(status_code=400, detail="候选尚未生成 CreativeBrief，请先 POST /candidates/{id}/brief")
    brief_raw = _vs().get_creative_brief(cand.creative_brief_id)
    if not brief_raw:
        raise HTTPException(status_code=404, detail="brief not found")
    brief = CreativeBrief.model_validate(brief_raw)

    # 构造 PromptSpec（如未生成）
    spec_raw = None
    if cand.prompt_spec_id:
        spec_raw = _vs().get_prompt_spec(cand.prompt_spec_id)
    if not spec_raw:
        pc = VisualPromptCompiler(_vs())
        spec = pc.compile(brief=brief)
        cand.prompt_spec_id = spec.id
        spec_raw = spec.model_dump()
    else:
        from apps.growth_lab.schemas.prompt_spec import PromptSpec
        spec = PromptSpec.model_validate(spec_raw)

    cand.status = "sent_to_workbench"
    _vs().save_strategy_candidate(cand.model_dump())

    handler_result: dict[str, Any] = {}
    if _send_to_workbench_handler is not None:
        try:
            handler_result = _send_to_workbench_handler(
                opportunity_id=req.opportunity_id,
                candidate=cand,
                brief=brief,
                prompt_spec=spec,
                notes=req.notes,
            ) or {}
        except Exception as exc:  # noqa: BLE001
            logger.exception("send_to_workbench_handler 执行失败")
            handler_result = {"error": str(exc)}

    return {
        "candidate_id": cand.id,
        "creative_brief_id": brief.id,
        "prompt_spec_id": spec.id,
        "opportunity_id": req.opportunity_id,
        "visual_builder_url": f"/planning/{req.opportunity_id}/visual-builder?creative_brief_id={brief.id}",
        "handler_result": handler_result,
    }


# ── Phase 5 字段预留：FeedbackRecord 入库 + v0.1 expert_score 调权 ─

@router.post("/feedback")
def submit_feedback(req: FeedbackRequest) -> dict[str, Any]:
    record = FeedbackRecord(
        image_variant_id=req.image_variant_id,
        strategy_candidate_id=req.strategy_candidate_id,
        decision=req.decision,  # type: ignore[arg-type]
        expert_score=req.expert_score or {},  # type: ignore[arg-type]
        business_metrics=req.business_metrics or {},  # type: ignore[arg-type]
        comments=req.comments,
        rule_ids=list(req.rule_ids or []),
    )
    engine = FeedbackEngine(visual_strategy_store=_vs(), rule_store=_rs())
    return engine.submit(record)


@router.get("/rules/{rule_id}/weight-history")
def list_rule_weight_history(rule_id: str) -> dict[str, Any]:
    """查看某条规则的权重变更轨迹（用于审核台审计）。"""
    rule = _rs().get_rule_spec(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"rule_id={rule_id} 不存在")
    history = _rs().list_rule_weight_history(rule_id)
    scoring = rule.get("scoring") or {}
    return {
        "rule_id": rule_id,
        "current_base_weight": float(scoring.get("base_weight", 0.5) or 0.5),
        "history": history,
    }
