from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from apps.b2b_platform.storage import B2BPlatformStore
from apps.intel_hub.config_loader import load_runtime_settings, resolve_repo_path
from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records
from apps.intel_hub.ingest.rss_loader import count_rss_records, load_rss_records
from apps.intel_hub.schemas import ReviewUpdateRequest
from apps.template_extraction.agent import TemplateRetriever, TemplateMatcher
from apps.template_extraction.labeling import label_note_by_rules
from apps.intel_hub.parsing.xhs_note_parser import parse_note
from apps.intel_hub.schemas.opportunity_review import OpportunityReview
from apps.intel_hub.services.opportunity_promoter import evaluate_opportunity_promotion
from apps.intel_hub.services.review_aggregator import (
    aggregate_all_opportunities_review_stats,
    aggregate_reviews_for_opportunity,
)
from apps.intel_hub.storage.repository import Repository
from apps.intel_hub.storage.xhs_review_store import XHSReviewStore
from apps.intel_hub.workflow.job_models import CrawlJob
from apps.intel_hub.workflow.job_queue import FileJobQueue
from apps.intel_hub.workflow.session_service import SessionService


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


class CrawlJobRequest(BaseModel):
    platform: str = "xhs"
    job_type: str = "keyword_search"
    keywords: str = ""
    max_notes: int = 10
    max_comments: int = 10
    priority: int = 5
    login_type: str = "qrcode"


class B2BBootstrapRequest(BaseModel):
    organization_name: str
    workspace_name: str
    brand_name: str
    campaign_name: str
    admin_user_id: str
    admin_display_name: str


class CreateBrandRequest(BaseModel):
    name: str
    category: str = "generic"
    positioning: str = ""
    tone_of_voice: list[str] = Field(default_factory=list)
    product_lines: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    competitor_refs: list[str] = Field(default_factory=list)
    content_goals: list[str] = Field(default_factory=list)


class CreateCampaignRequest(BaseModel):
    brand_id: str
    name: str
    objective: str = "content_growth"


class CreateMembershipRequest(BaseModel):
    user_id: str
    display_name: str
    role: str


class CreateConnectorRequest(BaseModel):
    platform: str
    connector_type: str
    status: str = "active"
    config: dict[str, Any] = Field(default_factory=dict)


class QueueOpportunityRequest(BaseModel):
    brand_id: str
    campaign_id: str
    queue_status: str = "new"


def create_app(
    runtime_config_path: str | Path | None = None,
    *,
    repository: Repository | None = None,
    review_store: XHSReviewStore | None = None,
    content_plan_store: Any | None = None,
    platform_store: B2BPlatformStore | None = None,
) -> FastAPI:
    settings = load_runtime_settings(runtime_config_path)
    repository = repository or Repository(settings.resolved_storage_path())
    job_queue = FileJobQueue(resolve_repo_path("data/job_queue.json"))
    session_svc = SessionService(resolve_repo_path("data/sessions"))
    review_store = review_store or XHSReviewStore(resolve_repo_path("data/xhs_review.sqlite"))
    platform_store = platform_store or B2BPlatformStore(resolve_repo_path(settings.b2b_platform_db_path))
    _xhs_cards_json = resolve_repo_path("data/output/xhs_opportunities/opportunity_cards.json")
    _xhs_details_json = resolve_repo_path("data/output/xhs_opportunities/pipeline_details.json")
    if _xhs_cards_json.exists():
        review_store.sync_cards_from_json(_xhs_cards_json)

    def _load_note_context_index() -> dict[str, dict[str, Any]]:
        if not _xhs_details_json.exists():
            return {}
        try:
            details = json.loads(_xhs_details_json.read_text(encoding="utf-8"))
        except Exception:
            return {}
        idx: dict[str, dict[str, Any]] = {}
        for d in details:
            nid = d.get("note_id", "")
            if not nid:
                continue
            idx[nid] = {
                "note_context": d.get("note_context", {}),
                "visual_signals": d.get("visual_signals", {}),
                "selling_theme_signals": d.get("selling_theme_signals", {}),
                "scene_signals": d.get("scene_signals", {}),
                "cross_modal_validation": d.get("cross_modal_validation", {}),
            }
        return idx

    _note_ctx_index: dict[str, dict[str, Any]] = _load_note_context_index()

    app = FastAPI(title="Ontology Intel Hub")

    def list_payload(
        table_name: str,
        page: int,
        page_size: int,
        entity: str | None,
        topic: str | None,
        platform: str | None,
        review_status: str | None,
        reviewer: str | None,
        status: str | None,
    ) -> dict[str, Any]:
        return repository.list_models(
            table_name,
            page=page,
            page_size=page_size,
            entity=entity,
            topic=topic,
            platform=platform,
            review_status=review_status,
            reviewer=reviewer,
            status=status,
        )

    def _require_workspace_auth(
        request: Request,
        workspace_id: str,
        *,
        allowed_roles: tuple[str, ...],
    ) -> Any:
        user_id = request.headers.get("x-user-id", "")
        api_token = request.headers.get("x-api-token", "")
        try:
            return platform_store.authorize(
                workspace_id=workspace_id,
                user_id=user_id,
                api_token=api_token,
                allowed_roles=allowed_roles,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/b2b/bootstrap")
    async def b2b_bootstrap(body: B2BBootstrapRequest) -> dict[str, Any]:
        result = platform_store.bootstrap_workspace(
            organization_name=body.organization_name,
            workspace_name=body.workspace_name,
            brand_name=body.brand_name,
            campaign_name=body.campaign_name,
            admin_user_id=body.admin_user_id,
            admin_display_name=body.admin_display_name,
        )
        return result.model_dump(mode="json")

    @app.post("/b2b/workspaces/{workspace_id}/brands")
    async def create_b2b_brand(workspace_id: str, body: CreateBrandRequest, request: Request) -> dict[str, Any]:
        _require_workspace_auth(request, workspace_id, allowed_roles=("admin", "strategist"))
        brand = platform_store.create_brand(
            workspace_id=workspace_id,
            name=body.name,
            category=body.category,
            positioning=body.positioning,
            tone_of_voice=body.tone_of_voice,
            product_lines=body.product_lines,
            forbidden_terms=body.forbidden_terms,
            competitor_refs=body.competitor_refs,
            content_goals=body.content_goals,
        )
        return brand.model_dump(mode="json")

    @app.post("/b2b/workspaces/{workspace_id}/campaigns")
    async def create_b2b_campaign(workspace_id: str, body: CreateCampaignRequest, request: Request) -> dict[str, Any]:
        _require_workspace_auth(request, workspace_id, allowed_roles=("admin", "strategist"))
        campaign = platform_store.create_campaign(
            workspace_id=workspace_id,
            brand_id=body.brand_id,
            name=body.name,
            objective=body.objective,
        )
        return campaign.model_dump(mode="json")

    @app.post("/b2b/workspaces/{workspace_id}/memberships")
    async def create_b2b_membership(workspace_id: str, body: CreateMembershipRequest, request: Request) -> dict[str, Any]:
        _require_workspace_auth(request, workspace_id, allowed_roles=("admin",))
        membership = platform_store.create_membership(
            workspace_id=workspace_id,
            user_id=body.user_id,
            display_name=body.display_name,
            role=body.role,
        )
        return membership.model_dump(mode="json")

    @app.post("/b2b/workspaces/{workspace_id}/connectors")
    async def create_b2b_connector(workspace_id: str, body: CreateConnectorRequest, request: Request) -> dict[str, Any]:
        auth = _require_workspace_auth(request, workspace_id, allowed_roles=("admin", "strategist"))
        connector = platform_store.create_connector(
            workspace_id=workspace_id,
            actor_user_id=auth.user_id,
            platform=body.platform,
            connector_type=body.connector_type,
            config=body.config,
            status=body.status,
        )
        return connector.model_dump(mode="json")

    @app.post("/b2b/workspaces/{workspace_id}/opportunities/{opportunity_id}/queue")
    async def queue_b2b_opportunity(
        workspace_id: str,
        opportunity_id: str,
        body: QueueOpportunityRequest,
        request: Request,
    ) -> dict[str, Any]:
        auth = _require_workspace_auth(request, workspace_id, allowed_roles=("admin", "strategist", "editor"))
        entry = platform_store.queue_opportunity(
            workspace_id=workspace_id,
            brand_id=body.brand_id,
            campaign_id=body.campaign_id,
            opportunity_id=opportunity_id,
            actor_user_id=auth.user_id,
            queue_status=body.queue_status,
        )
        return entry.model_dump(mode="json")

    @app.get("/b2b/workspaces/{workspace_id}/usage")
    async def b2b_workspace_usage(workspace_id: str, request: Request) -> dict[str, Any]:
        _require_workspace_auth(request, workspace_id, allowed_roles=("admin", "strategist", "editor", "reviewer", "designer", "viewer"))
        return platform_store.usage_summary(workspace_id)

    @app.get("/b2b/workspaces/{workspace_id}/approvals")
    async def b2b_workspace_approvals(workspace_id: str, request: Request) -> dict[str, Any]:
        _require_workspace_auth(request, workspace_id, allowed_roles=("admin", "strategist", "reviewer", "viewer"))
        approvals = platform_store.list_approvals(workspace_id)
        return {"items": [item.model_dump(mode="json") for item in approvals], "total": len(approvals)}

    @app.get("/b2b/workspaces/{workspace_id}/snapshot")
    async def b2b_workspace_snapshot(workspace_id: str, request: Request) -> dict[str, Any]:
        _require_workspace_auth(request, workspace_id, allowed_roles=("admin", "strategist", "editor", "reviewer", "designer", "viewer"))
        return platform_store.workspace_snapshot(workspace_id)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        signals = list_payload("signals", 1, 10, None, None, None, None, None, None)
        opportunities = list_payload("opportunity_cards", 1, 10, None, None, None, None, None, None)
        risks = list_payload("risk_cards", 1, 10, None, None, None, None, None, None)
        watchlists = list_payload("watchlists", 1, 10, None, None, None, None, None, None)
        notes_total = len(_get_notes())
        rss_counts = count_rss_records()
        xhs_cards_total = review_store.card_count()
        cs_path = resolve_repo_path("data/crawl_status.json")
        try:
            crawl = json.loads(cs_path.read_text(encoding="utf-8")) if cs_path.exists() else {"status": "idle"}
        except Exception:
            crawl = {"status": "idle"}
        return _render(
            "dashboard.html",
            {
                "request": request,
                "signals": signals,
                "opportunities": opportunities,
                "risks": risks,
                "watchlists": watchlists,
                "notes_total": notes_total,
                "rss_counts": rss_counts,
                "xhs_cards_total": xhs_cards_total,
                "crawl": crawl,
            },
        )

    @app.get("/signals")
    async def signals(
        request: Request,
        page: int = 1,
        page_size: int | None = None,
        entity: str | None = None,
        topic: str | None = None,
        platform: str | None = None,
        review_status: str | None = None,
        reviewer: str | None = None,
        status: str | None = None,
    ) -> Any:
        payload = list_payload(
            "signals",
            page,
            page_size or settings.default_page_size,
            entity,
            topic,
            platform,
            review_status,
            reviewer,
            status,
        )
        if _wants_html(request):
            return _render(
                "collection.html",
                {
                    "request": request,
                    "title": "Signals / 信号列表",
                    "collection_name": "Signals",
                    "payload": payload,
                },
            )
        return payload

    @app.get("/opportunities")
    async def opportunities(
        request: Request,
        page: int = 1,
        page_size: int | None = None,
        entity: str | None = None,
        topic: str | None = None,
        platform: str | None = None,
        review_status: str | None = None,
        reviewer: str | None = None,
        status: str | None = None,
    ) -> Any:
        payload = list_payload(
            "opportunity_cards",
            page,
            page_size or settings.default_page_size,
            entity,
            topic,
            platform,
            review_status,
            reviewer,
            status,
        )
        if _wants_html(request):
            return _render(
                "collection.html",
                {
                    "request": request,
                    "title": "Opportunities / 机会卡",
                    "collection_name": "Opportunity",
                    "payload": payload,
                },
            )
        return payload

    @app.post("/opportunities/{card_id}/review")
    async def review_opportunity(card_id: str, review: ReviewUpdateRequest) -> dict[str, Any]:
        try:
            updated_card = repository.update_card_review("opportunity_cards", card_id, review)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Opportunity card {card_id} not found") from exc
        return updated_card.model_dump(mode="json")

    @app.get("/risks")
    async def risks(
        request: Request,
        page: int = 1,
        page_size: int | None = None,
        entity: str | None = None,
        topic: str | None = None,
        platform: str | None = None,
        review_status: str | None = None,
        reviewer: str | None = None,
        status: str | None = None,
    ) -> Any:
        payload = list_payload(
            "risk_cards",
            page,
            page_size or settings.default_page_size,
            entity,
            topic,
            platform,
            review_status,
            reviewer,
            status,
        )
        if _wants_html(request):
            return _render(
                "collection.html",
                {
                    "request": request,
                    "title": "Risks / 风险卡",
                    "collection_name": "Risk",
                    "payload": payload,
                },
            )
        return payload

    @app.post("/risks/{card_id}/review")
    async def review_risk(card_id: str, review: ReviewUpdateRequest) -> dict[str, Any]:
        try:
            updated_card = repository.update_card_review("risk_cards", card_id, review)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Risk card {card_id} not found") from exc
        return updated_card.model_dump(mode="json")

    @app.get("/crawl-status")
    async def crawl_status() -> dict[str, Any]:
        status_path = resolve_repo_path("data/crawl_status.json")
        if not status_path.exists():
            return {"status": "idle", "message": "暂无抓取记录"}
        try:
            return json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            return {"status": "idle", "message": "状态文件读取失败"}

    # ── Phase 3: Job Queue API ──────────────────────────────────

    @app.post("/crawl-jobs")
    async def create_crawl_job(req: CrawlJobRequest) -> dict[str, Any]:
        job = CrawlJob(
            platform=req.platform,
            job_type=req.job_type,
            payload={
                "keywords": req.keywords,
                "max_notes": req.max_notes,
                "max_comments": req.max_comments,
                "login_type": req.login_type,
            },
            priority=req.priority,
        )
        job_queue.enqueue(job)
        return {"job_id": job.job_id, "status": job.status, "message": "任务已入队"}

    @app.get("/crawl-jobs")
    async def list_crawl_jobs(
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        jobs = job_queue.list_jobs(status=status, limit=limit)
        return {
            "total": len(jobs),
            "jobs": [j.to_dict() for j in jobs],
            "stats": job_queue.stats(),
        }

    @app.get("/crawl-jobs/{job_id}")
    async def get_crawl_job(job_id: str) -> dict[str, Any]:
        job = job_queue.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return job.to_dict()

    @app.post("/crawl-jobs/{job_id}/retry")
    async def retry_crawl_job(job_id: str) -> dict[str, Any]:
        if job_queue.retry(job_id):
            return {"job_id": job_id, "message": "任务已重新入队"}
        raise HTTPException(status_code=400, detail="任务不可重试")

    @app.get("/sessions")
    async def list_sessions(platform: str | None = None) -> dict[str, Any]:
        sessions = session_svc.list_sessions(platform)
        return {
            "total": len(sessions),
            "sessions": [s.to_dict() for s in sessions],
        }

    @app.get("/alerts")
    async def get_alerts() -> dict[str, Any]:
        alerts_path = resolve_repo_path("data/alerts.json")
        file_alerts: list[dict[str, Any]] = []
        if alerts_path.exists():
            try:
                file_alerts = json.loads(alerts_path.read_text(encoding="utf-8")).get("alerts", [])
            except Exception:
                pass
        session_alerts = session_svc.get_alerts()
        return {"alerts": file_alerts + session_alerts}

    # ── 原始小红书笔记浏览 ──────────────────────────────────

    _notes_cache: dict[str, Any] = {}

    def _get_notes() -> list[dict[str, Any]]:
        if "records" not in _notes_cache:
            all_records: list[dict[str, Any]] = []
            for src in settings.mediacrawler_sources:
                if not src.get("enabled", True):
                    continue
                out = resolve_repo_path(src.get("output_path", ""))
                if out.exists():
                    all_records.extend(load_mediacrawler_records(str(out), platform=src.get("platform", "xiaohongshu")))
            seen: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for r in all_records:
                nid = (r.get("raw_payload") or {}).get("note_id", "")
                if nid and nid not in seen:
                    seen.add(nid)
                    deduped.append(r)
            deduped.sort(key=lambda r: r.get("metrics", {}).get("engagement", 0), reverse=True)
            _notes_cache["records"] = deduped
        return _notes_cache["records"]

    @app.get("/notes")
    async def notes_list(request: Request, page: int = 1, page_size: int = 12, keyword: str | None = None) -> Any:
        all_notes = _get_notes()
        if keyword:
            keyword_lower = keyword.lower()
            all_notes = [n for n in all_notes if keyword_lower in (n.get("title", "") + n.get("raw_text", "")).lower()]
        total = len(all_notes)
        start = (max(page, 1) - 1) * page_size
        page_notes = all_notes[start : start + page_size]
        if _wants_html(request):
            return _render("notes.html", {
                "request": request,
                "notes": page_notes,
                "total": total,
                "page": page,
                "page_size": page_size,
                "keyword": keyword or "",
            })
        return {"total": total, "page": page, "page_size": page_size, "items": page_notes}

    @app.get("/notes/{note_id}")
    async def note_detail(request: Request, note_id: str) -> Any:
        all_notes = _get_notes()
        note = next((n for n in all_notes if (n.get("raw_payload") or {}).get("note_id") == note_id), None)
        if note is None:
            raise HTTPException(status_code=404, detail=f"笔记 {note_id} 未找到")
        if _wants_html(request):
            return _render("note_detail.html", {"request": request, "note": note})
        return note

    # ── RSS 趋势浏览 ──────────────────────────────────

    @app.get("/rss/tech")
    async def rss_tech_list(
        request: Request,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        feed: str | None = None,
    ) -> Any:
        return _rss_list(request, "tech", "科技趋势", page, page_size, keyword, feed)

    @app.get("/rss/news")
    async def rss_news_list(
        request: Request,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        feed: str | None = None,
    ) -> Any:
        return _rss_list(request, "news", "新闻媒体", page, page_size, keyword, feed)

    def _rss_list(
        request: Request,
        category: str,
        page_title: str,
        page: int,
        page_size: int,
        keyword: str | None,
        feed: str | None,
    ) -> Any:
        items = load_rss_records(category=category)
        feed_names = sorted({r["feed_name"] for r in items if r.get("feed_name")})
        if feed:
            items = [r for r in items if r.get("feed_id") == feed or r.get("feed_name") == feed]
        if keyword:
            kw = keyword.lower()
            items = [r for r in items if kw in (r.get("title", "") + r.get("summary", "")).lower()]
        total = len(items)
        start = (max(page, 1) - 1) * page_size
        page_items = items[start : start + page_size]
        if _wants_html(request):
            return _render("rss_feed.html", {
                "request": request,
                "items": page_items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "keyword": keyword or "",
                "feed_filter": feed or "",
                "feed_names": feed_names,
                "category": category,
                "page_title": page_title,
            })
        return {"total": total, "page": page, "page_size": page_size, "category": category, "items": page_items}

    # ── XHS 三维结构化机会卡 + 检视反馈 ──────────────────────────────────

    _xhs_type_labels = {
        "visual": "视觉差异化",
        "demand": "需求卖点",
        "product": "产品机会",
        "content": "内容主题",
        "scene": "场景专属",
    }
    _xhs_type_colors = {
        "visual": "#7b1fa2",
        "demand": "#1565c0",
        "product": "#2e7d32",
        "content": "#e65100",
        "scene": "#00695c",
    }
    _xhs_type_bg = {
        "visual": "#f3e5f5",
        "demand": "#e3f2fd",
        "product": "#e8f5e9",
        "content": "#fff3e0",
        "scene": "#e0f2f1",
    }
    _xhs_status_labels = {
        "pending_review": "待检视",
        "reviewed": "已检视",
        "promoted": "已升级",
        "rejected": "已驳回",
    }
    _xhs_status_colors = {
        "pending_review": "#757575",
        "reviewed": "#1565c0",
        "promoted": "#2e7d32",
        "rejected": "#c62828",
    }

    @app.get("/xhs-opportunities/review-summary")
    async def xhs_review_summary() -> dict[str, Any]:
        review_store.sync_cards_from_json(_xhs_cards_json)
        return aggregate_all_opportunities_review_stats(review_store)

    @app.get("/xhs-opportunities/{opportunity_id}/reviews")
    async def xhs_card_reviews(opportunity_id: str) -> dict[str, Any]:
        reviews = review_store.get_reviews(opportunity_id)
        return {"opportunity_id": opportunity_id, "reviews": [r.model_dump(mode="json") for r in reviews]}

    @app.post("/xhs-opportunities/{opportunity_id}/reviews")
    async def submit_xhs_review(opportunity_id: str, request: Request) -> dict[str, Any]:
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"机会卡 {opportunity_id} 未找到")

        body = await request.json()
        review = OpportunityReview(
            opportunity_id=opportunity_id,
            reviewer=body.get("reviewer", "anonymous"),
            manual_quality_score=int(body.get("manual_quality_score", 5)),
            is_actionable=bool(body.get("is_actionable", False)),
            evidence_sufficient=bool(body.get("evidence_sufficient", False)),
            review_notes=body.get("review_notes"),
        )
        review_store.save_review(review)
        stats = aggregate_reviews_for_opportunity(review_store, opportunity_id)
        new_status = evaluate_opportunity_promotion(review_store, opportunity_id)
        updated_card = review_store.get_card(opportunity_id)
        return {
            "review": review.model_dump(mode="json"),
            "aggregated_stats": stats,
            "opportunity_status": new_status,
            "card": updated_card.model_dump(mode="json") if updated_card else None,
        }

    @app.get("/xhs-opportunities/{opportunity_id}")
    async def xhs_opportunity_detail(request: Request, opportunity_id: str) -> Any:
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"机会卡 {opportunity_id} 未找到")

        reviews = review_store.get_reviews(opportunity_id)

        source_notes: list[dict[str, Any]] = []
        card_dict = card.model_dump(mode="json")
        for nid in card_dict.get("source_note_ids", []):
            if nid in _note_ctx_index:
                source_notes.append(_note_ctx_index[nid])

        if _wants_html(request):
            return _render("xhs_opportunity_detail.html", {
                "request": request,
                "card": card_dict,
                "reviews": [r.model_dump(mode="json") for r in reviews],
                "source_notes": source_notes,
                "type_labels": _xhs_type_labels,
                "type_colors": _xhs_type_colors,
                "type_bg": _xhs_type_bg,
                "status_labels": _xhs_status_labels,
                "status_colors": _xhs_status_colors,
            })
        return card_dict

    @app.get("/xhs-opportunities")
    async def xhs_opportunities(
        request: Request,
        page: int = 1,
        page_size: int = 15,
        type: str | None = None,
        status: str | None = None,
        qualified: str | None = None,
    ) -> Any:
        review_store.sync_cards_from_json(_xhs_cards_json)

        qualified_bool = None
        if qualified == "true":
            qualified_bool = True
        elif qualified == "false":
            qualified_bool = False

        result = review_store.list_cards(
            opportunity_type=type,
            opportunity_status=status,
            qualified=qualified_bool,
            page=page,
            page_size=page_size,
        )
        page_cards = [c.model_dump(mode="json") for c in result["items"]]
        total = result["total"]
        total_pages = max(1, (total + page_size - 1) // page_size)

        tc = review_store.type_counts()
        all_types = sorted(tc.keys())

        details_path = resolve_repo_path("data/output/xhs_opportunities/pipeline_details.json")
        total_notes = 0
        if details_path.exists():
            try:
                total_notes = len(json.loads(details_path.read_text(encoding="utf-8")))
            except Exception:
                pass

        stats = {
            "total_notes": total_notes,
            "total_cards": review_store.card_count(),
            "type_counts": tc,
        }

        if _wants_html(request):
            return _render("xhs_opportunities.html", {
                "request": request,
                "cards": page_cards,
                "stats": stats,
                "type_labels": _xhs_type_labels,
                "type_colors": _xhs_type_colors,
                "type_bg": _xhs_type_bg,
                "status_labels": _xhs_status_labels,
                "status_colors": _xhs_status_colors,
                "all_types": all_types,
                "type_filter": type,
                "status_filter": status,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            })
        return {"total": total, "page": page, "page_size": page_size, "items": page_cards, "stats": stats}

    # ── 桌布主图策略模板展示 ──────────────────────────────────

    _tpl_retriever = TemplateRetriever()

    @app.get("/strategy-templates")
    async def strategy_templates(request: Request) -> Any:
        templates = _tpl_retriever.list_templates()
        tpl_dicts = [t.model_dump(mode="json") for t in templates]

        all_notes = _get_notes()
        notes_total = len(all_notes)

        labeled_count = 0
        match_examples: list[dict[str, Any]] = []

        if templates and all_notes:
            matcher = TemplateMatcher(templates)
            sample_notes = all_notes[:30]
            for note_rec in sample_notes:
                raw_payload = note_rec.get("raw_payload", {})
                title = note_rec.get("title", "")
                body = note_rec.get("raw_text", "")
                image_list = note_rec.get("image_list", [])
                tags = note_rec.get("tags", [])
                author = note_rec.get("author", "")

                try:
                    from apps.intel_hub.schemas.xhs_raw import XHSNoteRaw

                    cover_img = image_list[0] if image_list else ""
                    if isinstance(cover_img, dict):
                        cover_img = cover_img.get("url", "")

                    raw_note = XHSNoteRaw(
                        note_id=raw_payload.get("note_id", ""),
                        title=title,
                        body=body,
                        author=author,
                        platform="xiaohongshu",
                        image_count=len(image_list),
                        cover_image=cover_img,
                        tags=tags if isinstance(tags, list) else [],
                    )
                    parsed = parse_note(raw_note)
                    labeled = label_note_by_rules(parsed)
                    labeled_count += 1

                    cover_labels = [r.label_id for r in labeled.cover_task_labels[:3]]
                    semantic_labels = [r.label_id for r in labeled.business_semantic_labels[:2]]
                    all_labels = cover_labels + semantic_labels

                    top_matches = matcher.match_templates(
                        opportunity_card=None,
                        product_brief=title + " " + body[:100],
                        intent="",
                        top_k=1,
                    )
                    if top_matches and top_matches[0].score > 0:
                        m = top_matches[0]
                        match_examples.append({
                            "title": title,
                            "body": body,
                            "cover_image": cover_img,
                            "labels": all_labels,
                            "matched_template_name": m.template_name,
                            "match_score": m.score,
                            "match_reason": m.reason,
                        })
                except Exception:
                    continue

            match_examples.sort(key=lambda x: x["match_score"], reverse=True)
            match_examples = match_examples[:10]

        if _wants_html(request):
            return _render("strategy_templates.html", {
                "request": request,
                "templates": tpl_dicts,
                "notes_total": notes_total,
                "labeled_count": labeled_count,
                "match_examples": match_examples,
            })
        return {
            "templates": tpl_dicts,
            "notes_total": notes_total,
            "labeled_count": labeled_count,
            "match_examples": match_examples,
        }

    # ── content_planning 路由挂载 ──────────────────────────────
    from apps.content_planning.api.routes import (
        router as content_planning_router,
        router_alias as content_planning_router_alias,
        set_flow,
    )
    from apps.content_planning.services.opportunity_to_plan_flow import OpportunityToPlanFlow
    from apps.content_planning.adapters.intel_hub_adapter import IntelHubAdapter
    from apps.content_planning.storage.plan_store import ContentPlanStore

    _cp_adapter = IntelHubAdapter(review_store=review_store)
    _plan_store = content_plan_store or ContentPlanStore(resolve_repo_path("data/content_plan.sqlite"))
    _cp_flow = OpportunityToPlanFlow(
        adapter=_cp_adapter,
        plan_store=_plan_store,
        platform_store=platform_store,
    )
    set_flow(_cp_flow)
    app.include_router(content_planning_router)
    app.include_router(content_planning_router_alias)

    # ── 内容策划工作台页面路由 ─────────────────────────────────
    @app.get("/content-planning/brief/{opportunity_id}")
    async def content_brief_page(request: Request, opportunity_id: str) -> Any:
        """Brief 确认页 / 机会工作台。"""
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")

        try:
            brief = _cp_flow.build_brief(opportunity_id)
            brief_dict = brief.model_dump(mode="json")
        except Exception:
            brief_dict = {}

        source_notes = _cp_adapter.get_source_notes(card.source_note_ids) if card.source_note_ids else []
        source_ctx = []
        for sn in source_notes[:1]:
            ctx = {"note_context": sn} if isinstance(sn, dict) else {"note_context": {}}
            source_ctx.append(ctx)

        review_summary = _cp_adapter.get_review_summary(opportunity_id)
        session_data = _cp_flow.get_session_data(opportunity_id)
        stale_flags = session_data.get("stale_flags", {})
        pipeline_run_id = session_data.get("pipeline_run_id", "")

        if _wants_html(request):
            return _render("content_brief.html", {
                "request": request,
                "opportunity_id": opportunity_id,
                "card": card,
                "brief": brief_dict,
                "source_notes": source_ctx,
                "review_summary": review_summary or {},
                "stale_flags": stale_flags,
                "pipeline_run_id": pipeline_run_id,
            })
        return {"card": card.model_dump(mode="json") if hasattr(card, "model_dump") else card, "brief": brief_dict}

    @app.get("/content-planning/strategy/{opportunity_id}")
    async def content_strategy_page(request: Request, opportunity_id: str) -> Any:
        """模板与策略页 / 策划工作台。"""
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")

        try:
            data = _cp_flow.build_note_plan(opportunity_id, with_generation=False)
        except Exception as exc:
            data = {"brief": {}, "match_result": {}, "strategy": {}, "error": str(exc)}

        session_data = _cp_flow.get_session_data(opportunity_id)
        stale_flags = session_data.get("stale_flags", {})

        if _wants_html(request):
            return _render("content_strategy.html", {
                "request": request,
                "opportunity_id": opportunity_id,
                "card": card.model_dump(mode="json"),
                "brief": data.get("brief", {}),
                "match_result": data.get("match_result", {}),
                "strategy": data.get("strategy", {}),
                "stale_flags": stale_flags,
            })
        return data

    @app.get("/content-planning/plan/{opportunity_id}")
    async def content_plan_page(request: Request, opportunity_id: str) -> Any:
        """内容策划页 / 资产工作台。"""
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")

        try:
            data = _cp_flow.build_note_plan(opportunity_id, with_generation=True)
        except Exception as exc:
            data = {"brief": {}, "match_result": {}, "strategy": {}, "note_plan": {}, "error": str(exc)}

        session_data = _cp_flow.get_session_data(opportunity_id)
        stale_flags = session_data.get("stale_flags", {})

        if _wants_html(request):
            return _render("content_plan.html", {
                "request": request,
                "opportunity_id": opportunity_id,
                "brief": data.get("brief", {}),
                "strategy": data.get("strategy", {}),
                "match_result": data.get("match_result", {}),
                "note_plan": data.get("note_plan", {}),
                "generated": data.get("generated"),
                "stale_flags": stale_flags,
            })
        return data

    @app.get("/content-planning/assets/{opportunity_id}")
    async def content_assets_page(request: Request, opportunity_id: str) -> Any:
        """资产工作台。"""
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")

        try:
            bundle = _cp_flow.assemble_asset_bundle(opportunity_id)
            bundle_dict = bundle.model_dump(mode="json") if hasattr(bundle, "model_dump") else {}
        except Exception:
            bundle_dict = {}

        try:
            data = _cp_flow.build_note_plan(opportunity_id, with_generation=True)
        except Exception:
            data = {}

        session_data = _cp_flow.get_session_data(opportunity_id)

        if _wants_html(request):
            return _render("content_assets.html", {
                "request": request,
                "opportunity_id": opportunity_id,
                "bundle": bundle_dict,
                "brief": data.get("brief", {}),
                "strategy": data.get("strategy", {}),
                "match_result": data.get("match_result", {}),
                "generated": data.get("generated"),
                "lineage": bundle_dict.get("lineage", {}),
                "stale_flags": session_data.get("stale_flags", {}),
            })
        return {"bundle": bundle_dict}

    @app.get("/watchlists")
    async def watchlists(
        request: Request,
        page: int = 1,
        page_size: int | None = None,
        entity: str | None = None,
        topic: str | None = None,
        platform: str | None = None,
        review_status: str | None = None,
        reviewer: str | None = None,
        status: str | None = None,
    ) -> Any:
        payload = list_payload(
            "watchlists",
            page,
            page_size or settings.default_page_size,
            entity,
            topic,
            platform,
            review_status,
            reviewer,
            status,
        )
        if _wants_html(request):
            return _render(
                "collection.html",
                {
                    "request": request,
                    "title": "Watchlists / 监控列表",
                    "collection_name": "Watchlist",
                    "payload": payload,
                },
            )
        return payload

    return app


def _render(template_name: str, context: dict[str, Any]) -> HTMLResponse:
    template = TEMPLATE_ENV.get_template(template_name)
    return HTMLResponse(template.render(**context))


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


app = create_app()
