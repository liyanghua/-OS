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
from apps.intel_hub.schemas import ReviewUpdateRequest
from apps.intel_hub.storage.repository import Repository
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
