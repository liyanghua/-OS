from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from apps.intel_hub.config_loader import load_runtime_settings, resolve_repo_path
from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records
from apps.intel_hub.ingest.rss_loader import count_rss_records, load_rss_records
from apps.intel_hub.schemas import ReviewUpdateRequest
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


def create_app(runtime_config_path: str | Path | None = None) -> FastAPI:
    settings = load_runtime_settings(runtime_config_path)
    repository = Repository(settings.resolved_storage_path())
    job_queue = FileJobQueue(resolve_repo_path("data/job_queue.json"))
    session_svc = SessionService(resolve_repo_path("data/sessions"))
    review_store = XHSReviewStore(resolve_repo_path("data/xhs_review.sqlite"))
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
