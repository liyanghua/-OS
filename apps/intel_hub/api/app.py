from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from apps.b2b_platform.storage import B2BPlatformStore
from apps.intel_hub.config_loader import load_runtime_settings, resolve_repo_path
from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records
from apps.intel_hub.ingest.rss_loader import load_rss_records
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
from apps.intel_hub.workflow.collector_worker import process_one_job
from apps.intel_hub.workflow.job_models import CrawlJob
from apps.intel_hub.workflow.job_queue import FileJobQueue
from apps.intel_hub.workflow.session_service import SessionService

from apps.content_planning.gateway.sse_handler import sse_stream
from apps.content_planning.gateway.event_bus import event_bus, ObjectEvent
from apps.content_planning.gateway.session_manager import session_manager


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


# 小红书等第三方 CDN 图片在浏览器端会被防盗链拦截，统一通过 /img-proxy 走后端代抓。
# 已下载到本地或已是站内路径的不再代理。
_PROXY_IMG_HOST_ALLOW: tuple[str, ...] = (
    "xhscdn.com",
    "xhs.cn",
    "xiaohongshu.com",
    "douyinpic.com",
    "douyincdn.com",
    "weibocdn.com",
    "sinaimg.cn",
)


def _should_proxy_img(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    return any(host == h or host.endswith("." + h) for h in _PROXY_IMG_HOST_ALLOW)


def _proxy_img_filter(url: Any) -> str:
    """Jinja 过滤器：把第三方图床外链改写成 /img-proxy 代理路径。

    - 空值/相对路径/站内静态目录直接原样返回；
    - 命中白名单的 http(s) 外链改写为 ``/img-proxy?url=<encoded>``。
    """
    if not url:
        return ""
    s = str(url)
    if s.startswith("/"):  # 站内绝对路径（含 /source-images, /generated-images）
        return s
    if not _should_proxy_img(s):
        return s
    return "/img-proxy?url=" + quote(s, safe="")


TEMPLATE_ENV.filters["proxy_img"] = _proxy_img_filter


class CrawlJobRequest(BaseModel):
    platform: str = "xhs"
    job_type: str = "keyword_search"
    keywords: str = ""
    max_notes: int = 20
    max_comments: int = 10
    priority: int = 5
    login_type: str = "qrcode"
    sort_type: str = "popularity_descending"


class StartAgentRunRequest(BaseModel):
    """POST /xhs-opportunities/agent-runs 请求体。

    默认 ``max_notes=1`` 走"先跑 1 条预览"路径；前端"再跑 5 条 / 全部"
    会带 ``skip_note_ids`` 实现增量补跑，避免重复处理同一篇笔记。
    """

    lens_id: str
    max_notes: int = 1
    skip_note_ids: list[str] = []
    note_id: str | None = None


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
    enable_embedded_crawl_worker: bool | None = None,
    xhs_opportunities_dir: str | Path | None = None,
) -> FastAPI:
    settings = load_runtime_settings(runtime_config_path)
    repository = repository or Repository(settings.resolved_storage_path())
    job_queue = FileJobQueue(settings.resolved_job_queue_path())
    session_svc = SessionService(resolve_repo_path("data/sessions"))
    review_store = review_store or XHSReviewStore(resolve_repo_path("data/xhs_review.sqlite"))
    platform_store = platform_store or B2BPlatformStore(resolve_repo_path(settings.b2b_platform_db_path))
    from apps.content_planning.storage.plan_store import ContentPlanStore

    _plan_store = content_plan_store or ContentPlanStore(resolve_repo_path("data/content_plan.sqlite"))
    # 机会卡 / 笔记上下文落盘目录，可由 create_app 注入用于测试隔离；
    # 默认指向 ``data/output/xhs_opportunities/``。
    _xhs_output_dir = (
        Path(xhs_opportunities_dir)
        if xhs_opportunities_dir is not None
        else resolve_repo_path("data/output/xhs_opportunities")
    )
    _xhs_cards_json = _xhs_output_dir / "opportunity_cards.json"
    _xhs_details_json = _xhs_output_dir / "pipeline_details.json"
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

    def _refresh_note_ctx_index() -> None:
        """重新读 ``pipeline_details.json``，把新增笔记并入内存索引。

        Agent 增量跑完后会 merge 新条目进 ``pipeline_details.json``，
        但 ``_note_ctx_index`` 在 ``create_app`` 启动时已加载完成。
        机会卡详情页命中 miss 时调用本函数做一次延迟刷新，避免重启进程。
        """
        try:
            new_idx = _load_note_context_index()
        except Exception:  # noqa: BLE001
            return
        _note_ctx_index.clear()
        _note_ctx_index.update(new_idx)

    crawl_status_path = settings.resolved_crawl_status_path()
    alerts_path = settings.resolved_alerts_path()
    embedded_worker_enabled = (
        settings.embedded_crawl_worker_enabled
        if enable_embedded_crawl_worker is None
        else enable_embedded_crawl_worker
    )

    worker_wakeup = asyncio.Event()
    worker_task: asyncio.Task[None] | None = None

    async def _embedded_worker_loop() -> None:
        while True:
            await worker_wakeup.wait()
            worker_wakeup.clear()
            while True:
                did_work = await process_one_job(
                    job_queue,
                    session_service=session_svc,
                    status_path=crawl_status_path,
                    alerts_path=alerts_path,
                    runtime_config_path=runtime_config_path,
                )
                if not did_work:
                    break
                if job_queue.pending_count() > 0:
                    continue
                if job_queue.has_running_jobs():
                    break

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal worker_task
        if embedded_worker_enabled:
            if job_queue.pending_count() > 0:
                worker_wakeup.set()
            worker_task = asyncio.create_task(_embedded_worker_loop())
        try:
            yield
        finally:
            if worker_task:
                worker_task.cancel()
                with suppress(asyncio.CancelledError):
                    await worker_task

    app = FastAPI(title="Ontology Intel Hub", lifespan=lifespan)

    def _safe_read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else (default or {})
        except Exception:
            return default or {}

    def _normalize_platform(platform: str | None) -> str:
        value = (platform or "").strip().lower()
        if value in {"xhs", "xiaohongshu", "rednote"}:
            return "xhs"
        if value in {"dy", "douyin", "tiktok_cn"}:
            return "dy"
        return "xhs"

    def _platform_label(platform: str | None) -> str:
        normalized = _normalize_platform(platform)
        return "抖音" if normalized == "dy" else "小红书"

    def _platform_status_path(platform: str | None) -> Path:
        normalized = _normalize_platform(platform)
        base = crawl_status_path
        return base.with_name(f"{base.stem}_{normalized}{base.suffix or '.json'}")

    def _parse_iso(ts: str | None) -> datetime | None:
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def _keyword_result_url(keyword: str, platform: str | None = None) -> str:
        from urllib.parse import quote as _urlq

        p = _normalize_platform(platform)
        if keyword:
            return f"/notes?platform={_urlq(p)}&category={_urlq(keyword)}"
        return f"/notes?platform={_urlq(p)}"

    def _job_elapsed_ms(job: CrawlJob) -> int:
        start = _parse_iso(job.started_at)
        if not start:
            return 0
        end = _parse_iso(job.completed_at) or datetime.now(tz=start.tzinfo or timezone.utc)
        return max(0, int((end - start).total_seconds() * 1000))

    def _build_crawl_progress(job: CrawlJob, crawl: dict[str, Any]) -> dict[str, Any]:
        keyword = job.display_keyword or str((job.payload or {}).get("keywords", "") or "")
        max_notes = int((job.payload or {}).get("max_notes", 20) or 20)
        platform = _normalize_platform(job.platform or (job.payload or {}).get("platform"))
        notes_collected = 0
        if keyword and job.status in ("running", "completed", "failed", "dead"):
            notes_collected = _count_notes_by_source_keyword(keyword, platform=platform)

        progress_pct = min(100, notes_collected * 100 // max(1, max_notes))
        if job.status == "completed":
            progress_pct = 100
        elif job.status in ("failed", "dead"):
            progress_pct = min(progress_pct, 99)

        return {
            "job_id": job.job_id,
            "job_group_id": job.job_group_id,
            "status": job.status,
            "job_type": job.job_type,
            "platform": platform,
            "platform_label": _platform_label(platform),
            "display_keyword": keyword,
            "keyword": keyword,
            "max_notes": max_notes,
            "notes_collected": notes_collected,
            "progress_pct": progress_pct,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "created_at": job.created_at,
            "elapsed_ms": _job_elapsed_ms(job),
            "error": job.error or "",
            "last_heartbeat_at": job.last_heartbeat_at,
            "result_url": _keyword_result_url(keyword, platform=platform),
            "global_status": {
                "status": crawl.get("status", ""),
                "current_keyword": crawl.get("current_keyword", ""),
                "notes_found": crawl.get("notes_found", 0),
                "notes_saved": crawl.get("notes_saved", 0),
            },
        }

    def _build_queue_summary(base_job: CrawlJob | None = None, limit: int = 5) -> dict[str, Any]:
        jobs = job_queue.list_jobs(limit=max(limit, 20))
        batch_group_id = base_job.job_group_id if base_job else None
        batch_jobs = job_queue.list_batch_jobs(batch_group_id) if batch_group_id else []
        pending_batch_jobs = [j for j in batch_jobs if j.status == "pending" and j.job_type == "keyword_search"]
        active_batch_job = next((j for j in batch_jobs if j.status == "running"), None)
        batch_total = len([j for j in batch_jobs if j.job_type == "keyword_search"])
        batch_completed = len(
            [j for j in batch_jobs if j.job_type == "keyword_search" and j.status == "completed"]
        )
        pending_count = len([j for j in jobs if j.status == "pending"])
        running_count = len([j for j in jobs if j.status == "running"])
        recent_jobs = [
            {
                "job_id": j.job_id,
                "job_group_id": j.job_group_id,
                "job_type": j.job_type,
                "status": j.status,
                "display_keyword": j.display_keyword,
                "created_at": j.created_at,
                "started_at": j.started_at,
                "completed_at": j.completed_at,
            }
            for j in jobs[:limit]
        ]
        return {
            "batch_job_group_id": batch_group_id or "",
            "active_job": {
                "job_id": active_batch_job.job_id,
                "display_keyword": active_batch_job.display_keyword,
                "status": active_batch_job.status,
                "job_type": active_batch_job.job_type,
            } if active_batch_job else None,
            "pending_jobs": [
                {
                    "job_id": j.job_id,
                    "display_keyword": j.display_keyword,
                    "status": j.status,
                    "job_type": j.job_type,
                }
                for j in pending_batch_jobs[:limit]
            ],
            "pending_count": pending_count,
            "running_count": running_count,
            "batch_total": batch_total,
            "batch_completed": batch_completed,
            "recent_jobs": recent_jobs,
            "has_pipeline_refresh": any(j.job_type == "pipeline_refresh" and j.status in ("pending", "running") for j in jobs),
        }

    def _build_pipeline_status(base_job: CrawlJob | None) -> dict[str, Any]:
        if not base_job:
            return {"status": "not_started", "job_id": "", "job_group_id": ""}

        group_jobs = job_queue.list_group_jobs(base_job.job_group_id)
        pipeline_jobs = [j for j in group_jobs if j.job_type == "pipeline_refresh"]
        if not pipeline_jobs:
            return {"status": "not_started", "job_id": "", "job_group_id": base_job.job_group_id}

        pipeline_jobs.sort(key=lambda j: j.created_at, reverse=True)
        target = pipeline_jobs[0]
        return {
            "status": target.status,
            "job_id": target.job_id,
            "job_group_id": target.job_group_id,
            "started_at": target.started_at,
            "completed_at": target.completed_at,
            "last_heartbeat_at": target.last_heartbeat_at,
            "error": target.error or "",
        }

    def _derive_observer_state(
        base_job: CrawlJob | None,
        pipeline: dict[str, Any],
        crawl: dict[str, Any],
    ) -> tuple[str, str]:
        if not base_job:
            return "idle", ""

        now = datetime.now(tz=timezone.utc)
        crawl_updated_at = _parse_iso(crawl.get("updated_at"))
        heartbeat_at = _parse_iso(base_job.last_heartbeat_at)

        if base_job.status in ("failed", "dead"):
            return "failed", ""

        if base_job.status == "pending":
            age = now - (_parse_iso(base_job.created_at) or now)
            if age.total_seconds() >= 30:
                return "stalled", "worker_not_running"
            return "queued", ""

        if base_job.status == "running":
            freshness_anchor = crawl_updated_at or heartbeat_at or _parse_iso(base_job.started_at)
            # 评论爬取阶段单条笔记可能耗时数分钟，按 phase 分级阈值，避免误判 stalled
            phase = (crawl.get("phase") or "").strip()
            stale_threshold = 300 if phase == "crawling_comments" else 20
            if freshness_anchor and (now - freshness_anchor).total_seconds() >= stale_threshold:
                return "stalled", "status_stale"
            return "crawling", ""

        if base_job.status == "completed":
            pipeline_status = pipeline.get("status", "not_started")
            if pipeline_status == "running":
                return "pipeline_running", ""
            if pipeline_status == "pending":
                return "crawl_completed_waiting_pipeline", "pipeline_not_ready"
            if pipeline_status in ("failed", "dead"):
                return "failed", ""
            if pipeline_status == "completed":
                return "result_ready", ""
            return "result_ready", ""

        return "idle", ""

    def _build_crawl_observer(preferred_job_id: str | None = None) -> dict[str, Any]:
        active_job = job_queue.latest_active_job(preferred_job_id=preferred_job_id)
        active_platform = _normalize_platform(active_job.platform if active_job else "xhs")
        crawl = _safe_read_json(_platform_status_path(active_platform), {"status": "idle", "message": "暂无抓取记录"})
        pipeline = _build_pipeline_status(active_job)
        derived_state, stalled_reason = _derive_observer_state(active_job, pipeline, crawl)
        active_payload = _build_crawl_progress(active_job, crawl) if active_job else None
        unresolved_alerts = [a for a in _safe_read_json(alerts_path, {}).get("alerts", []) if not a.get("resolved", False)]

        actions = {
            "view_result_url": active_payload["result_url"] if active_payload and derived_state == "result_ready" else "",
            "retry_job_id": active_job.job_id if active_job and active_job.status in ("failed", "dead") else "",
            "dismissible": True,
        }

        return {
            "active_job": active_payload,
            "queue": _build_queue_summary(active_job),
            "crawl": {
                "platform": active_platform,
                "platform_label": _platform_label(active_platform),
                "status": crawl.get("status", "idle"),
                "current_keyword": crawl.get("current_keyword", ""),
                "current_keyword_index": crawl.get("current_keyword_index", 0),
                "total_keywords": crawl.get("total_keywords", 0),
                "notes_saved": crawl.get("notes_saved", 0),
                "notes_failed": crawl.get("notes_failed", 0),
                "comments_saved": crawl.get("comments_saved", 0),
                "traces_saved": crawl.get("traces_saved", 0),
                "session_id": crawl.get("session_id", ""),
                "duration_seconds": crawl.get("duration_seconds", 0),
                "avg_note_delay_seconds": crawl.get("avg_note_delay_seconds", 0),
                "updated_at": crawl.get("updated_at", ""),
                "errors": crawl.get("errors", []),
                "phase": crawl.get("phase", ""),
                "comment_notes_total": crawl.get("comment_notes_total", 0),
                "comment_notes_done": crawl.get("comment_notes_done", 0),
                "current_comment_note_id": crawl.get("current_comment_note_id", ""),
            },
            "pipeline": pipeline,
            "derived_state": derived_state,
            "stalled_reason": stalled_reason,
            "actions": actions,
            "alerts": {
                "count": len(unresolved_alerts),
                "items": unresolved_alerts[:5],
            },
        }

    _intel_hub_static = Path(__file__).resolve().parent / "static"
    if _intel_hub_static.is_dir():
        app.mount("/static", StaticFiles(directory=str(_intel_hub_static)), name="intel_hub_static")

    _generated_images_dir = Path(__file__).resolve().parents[3] / "data" / "generated_images"
    _generated_images_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/generated-images", StaticFiles(directory=str(_generated_images_dir)), name="generated_images")

    _source_images_dir = Path(__file__).resolve().parents[3] / "data" / "source_images"
    _source_images_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/source-images", StaticFiles(directory=str(_source_images_dir)), name="source_images")

    _generated_videos_dir = Path(__file__).resolve().parents[3] / "data" / "generated_videos"
    _generated_videos_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/generated-videos", StaticFiles(directory=str(_generated_videos_dir)), name="generated_videos")

    # 1×1 透明 PNG（24 字节），用于代理失败时的占位返回，避免前端 onerror 抖动。
    _PROXY_PLACEHOLDER_PNG = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc"
        b"\xff\xff?\x03\x00\x07\x01\x02\xfe\xa9\xb6,\xed\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    @app.get("/img-proxy")
    async def img_proxy(url: str) -> Response:
        """代抓第三方图床（主要是小红书 xhscdn）以绕过防盗链。

        - 仅允许 host 命中白名单的 http(s) 链接；
        - 转发时附带桌面 UA 与 ``Referer: https://www.xiaohongshu.com/``；
        - 失败/超时返回 1x1 透明 PNG，避免前端 ``onerror`` 抖动。
        """
        if not _should_proxy_img(url):
            raise HTTPException(status_code=400, detail="url not allowed")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                upstream = await client.get(url, headers=headers)
            if upstream.status_code >= 400:
                return Response(
                    content=_PROXY_PLACEHOLDER_PNG,
                    media_type="image/png",
                    headers={"Cache-Control": "public, max-age=300"},
                )
            content_type = upstream.headers.get("content-type", "image/jpeg")
            return Response(
                content=upstream.content,
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except Exception:
            return Response(
                content=_PROXY_PLACEHOLDER_PNG,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=60"},
            )

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

    @app.get("/b2b/workspaces/{workspace_id}/feedback")
    async def b2b_workspace_feedback(workspace_id: str, request: Request) -> dict[str, Any]:
        _require_workspace_auth(request, workspace_id, allowed_roles=("admin", "strategist", "reviewer", "viewer"))
        feedback = _plan_store.load_feedback_records(workspace_id=workspace_id)
        winning = _plan_store.load_winning_patterns(workspace_id=workspace_id)
        failed = _plan_store.load_failed_patterns(workspace_id=workspace_id)
        return {"feedback_records": feedback, "winning_patterns": winning, "failed_patterns": failed}

    @app.get("/b2b/workspaces/{workspace_id}/pipeline")
    async def b2b_workspace_pipeline(workspace_id: str, request: Request) -> dict[str, Any]:
        _require_workspace_auth(request, workspace_id, allowed_roles=("admin", "strategist", "reviewer", "viewer"))
        publish_results = platform_store.list_publish_results(workspace_id=workspace_id)
        feedback = _plan_store.load_feedback_records(workspace_id=workspace_id)
        total_pubs = len(publish_results)
        total_fb = len(feedback)
        avg_eng = 0.0
        if feedback:
            engs = [fr.get("engagement_proxy", 0.0) for fr in feedback if fr.get("engagement_proxy")]
            avg_eng = sum(engs) / len(engs) if engs else 0.0
        return {
            "workspace_id": workspace_id,
            "total_published": total_pubs,
            "total_feedback": total_fb,
            "avg_engagement_proxy": round(avg_eng, 4),
            "publish_results": [p.model_dump(mode="json") for p in publish_results],
        }

    @app.post("/objects/{object_type}/{object_id}/assign")
    async def assign_object(object_type: str, object_id: str, request: Request) -> dict[str, Any]:
        from apps.b2b_platform.schemas import ObjectAssignment

        body = await request.json()
        ws_id = body.get("workspace_id", "")
        assignment = ObjectAssignment(
            workspace_id=ws_id,
            object_type=cast(Any, object_type),
            object_id=object_id,
            assignee_user_id=body.get("assignee_user_id", ""),
            assigned_by=body.get("assigned_by", ""),
            role_hint=body.get("role_hint", ""),
        )
        platform_store.save_assignment(assignment)
        return assignment.model_dump(mode="json")

    @app.post("/objects/{object_type}/{object_id}/comments")
    async def add_comment(object_type: str, object_id: str, request: Request) -> dict[str, Any]:
        from apps.b2b_platform.schemas import ObjectComment

        body = await request.json()
        comment = ObjectComment(
            workspace_id=body.get("workspace_id", ""),
            object_type=cast(Any, object_type),
            object_id=object_id,
            author_user_id=body.get("author_user_id", ""),
            content=body.get("content", ""),
        )
        platform_store.save_comment(comment)
        return comment.model_dump(mode="json")

    @app.get("/objects/{object_type}/{object_id}/comments")
    async def get_comments(object_type: str, object_id: str, request: Request) -> dict[str, Any]:
        ws_id = request.query_params.get("workspace_id", "")
        comments = platform_store.list_comments(ws_id, object_type=object_type, object_id=object_id)
        return {"items": [c.model_dump(mode="json") for c in comments]}

    @app.post("/approvals/{request_id}/decision")
    async def approval_decision(request_id: str, request: Request) -> dict[str, Any]:
        from datetime import UTC, datetime

        body = await request.json()
        reqs = platform_store.list_approval_requests(body.get("workspace_id", ""))
        target = None
        for r in reqs:
            if r.request_id == request_id:
                target = r
                break
        if not target:
            raise HTTPException(status_code=404, detail="approval request not found")
        target.status = body.get("decision", "approved")
        target.reviewer_id = body.get("reviewer_id", "")
        target.decision_at = datetime.now(UTC)
        target.notes = body.get("notes", "")
        platform_store.save_approval_request(target)
        return target.model_dump(mode="json")

    @app.get("/b2b/workspaces/{workspace_id}/timeline")
    async def workspace_timeline(workspace_id: str, request: Request) -> dict[str, Any]:
        _require_workspace_auth(
            request,
            workspace_id,
            allowed_roles=("admin", "strategist", "editor", "reviewer", "designer", "viewer"),
        )
        events = platform_store.list_timeline_events(workspace_id)
        return {"items": [e.model_dump(mode="json") for e in events]}

    @app.get("/objects/{object_type}/{object_id}/readiness")
    async def get_delivery_readiness(object_type: str, object_id: str) -> dict[str, Any]:
        """交付门控：读取对象的就绪清单（B2B 协同）。"""
        checklist = platform_store.get_readiness_checklist(object_id)
        if checklist is None:
            return {"checklist": None, "object_type": object_type, "object_id": object_id}
        return {"checklist": checklist.model_dump(mode="json")}

    @app.put("/objects/{object_type}/{object_id}/readiness")
    async def put_delivery_readiness(object_type: str, object_id: str, request: Request) -> dict[str, Any]:
        """交付门控：写入/更新就绪清单。"""
        from apps.b2b_platform.schemas import ReadinessChecklist

        body = await request.json()
        merged = {**body, "object_type": object_type, "object_id": object_id}
        checklist = ReadinessChecklist.model_validate(merged)
        platform_store.save_readiness_checklist(checklist)
        return checklist.model_dump(mode="json")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        notes_total = len(_get_notes())
        xhs_cards_total = review_store.card_count()
        try:
            review_summary = review_store.get_review_summary()
            promoted_total = int(review_summary.get("promoted_opportunities", 0) or 0)
        except Exception:
            promoted_total = 0
        return _render(
            "dashboard.html",
            {
                "request": request,
                "notes_total": notes_total,
                "xhs_cards_total": xhs_cards_total,
                "promoted_total": promoted_total,
            },
        )

    @app.get("/expert-strategy-workbench", response_class=HTMLResponse)
    async def expert_strategy_workbench(request: Request) -> HTMLResponse:
        """专家策略工作台：行业 Know-how 导入 → 策略规则提炼/评审 → 行业策略库发布。"""
        return _render(
            "expert_strategy_workbench.html",
            {"request": request},
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
                    "title": "信号列表",
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
                    "title": "机会卡",
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
                    "title": "风险卡",
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
    async def crawl_status(platform: str = "xhs") -> dict[str, Any]:
        normalized_platform = _normalize_platform(platform)
        status_path = _platform_status_path(platform)
        if not status_path.exists():
            return {"status": "idle", "message": "暂无抓取记录", "platform": normalized_platform}
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            payload["platform"] = normalized_platform
            return payload
        except Exception:
            return {"status": "idle", "message": "状态文件读取失败", "platform": normalized_platform}

    @app.get("/crawl-observer")
    async def crawl_observer(job_id: str | None = None) -> dict[str, Any]:
        return _build_crawl_observer(job_id)

    # ── Phase 3: Job Queue API ──────────────────────────────────

    @app.post("/crawl-jobs")
    async def create_crawl_job(req: CrawlJobRequest) -> dict[str, Any]:
        job_group_id = job_queue.find_open_batch() or ""
        platform = _normalize_platform(req.platform)
        job = CrawlJob(
            platform=platform,
            job_type=req.job_type,
            payload={
                "platform": platform,
                "keywords": req.keywords,
                "max_notes": req.max_notes,
                "max_comments": req.max_comments,
                "login_type": req.login_type,
                "sort_type": req.sort_type,
            },
            display_keyword=req.keywords,
            priority=req.priority,
            job_group_id=job_group_id,
        )
        job_queue.enqueue(job)
        worker_wakeup.set()
        return {
            "job_id": job.job_id,
            "job_group_id": job.job_group_id,
            "status": job.status,
            "message": "任务已入队",
        }

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
            worker_wakeup.set()
            return {"job_id": job_id, "message": "任务已重新入队"}
        raise HTTPException(status_code=400, detail="任务不可重试")

    @app.get("/crawl-jobs/{job_id}/progress")
    async def crawl_job_progress(job_id: str) -> dict[str, Any]:
        """单任务进度：合并 job 状态 + 全局 crawl_status + 该关键词已落地条数。"""
        job = job_queue.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        crawl = _safe_read_json(_platform_status_path(job.platform), {})
        return _build_crawl_progress(job, crawl)

    @app.get("/sessions")
    async def list_sessions(platform: str | None = None) -> dict[str, Any]:
        sessions = session_svc.list_sessions(platform)
        return {
            "total": len(sessions),
            "sessions": [s.to_dict() for s in sessions],
        }

    @app.get("/alerts")
    async def get_alerts() -> dict[str, Any]:
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

    def _get_notes(*, force_reload: bool = False) -> list[dict[str, Any]]:
        if force_reload:
            _notes_cache.pop("records", None)
        if "records" not in _notes_cache:
            all_records: list[dict[str, Any]] = []
            for src in settings.mediacrawler_sources:
                if not src.get("enabled", True):
                    continue
                out = resolve_repo_path(src.get("output_path", ""))
                if out.exists():
                    source_platform = _normalize_platform(src.get("platform", "xhs"))
                    all_records.extend(load_mediacrawler_records(str(out), platform=source_platform))
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

    def _count_notes_by_source_keyword(keyword: str, *, platform: str | None = None) -> int:
        """统计已落地的笔记中 source_keyword == keyword 的数量；每次强制刷新缓存。"""
        if not keyword:
            return 0
        kw = keyword.strip()
        p = _normalize_platform(platform)
        notes = _get_notes(force_reload=True)
        return sum(
            1
            for n in notes
            if (n.get("keyword") or "").strip() == kw and _normalize_platform(n.get("platform")) == p
        )

    def _build_category_index(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按笔记的采集关键词（source_keyword）构建分类索引。"""
        counter: dict[str, int] = {}
        for n in notes:
            kw = (n.get("keyword") or "").strip() or "未分类"
            counter[kw] = counter.get(kw, 0) + 1
        items = [{"key": k, "count": v} for k, v in counter.items()]
        # 未分类沉底；其余按 count desc、再按 key 字典序
        items.sort(key=lambda x: (x["key"] == "未分类", -x["count"], x["key"]))
        return items

    @app.get("/notes")
    async def notes_list(
        request: Request,
        page: int = 1,
        page_size: int = 24,
        platform: str = "xhs",
        lens: str | None = None,
        category: str | None = None,
        q: str | None = None,
        keyword: str | None = None,  # 向后兼容旧链接：等价 q
    ) -> Any:
        from apps.intel_hub.config_loader import (
            load_category_lenses,
            route_keyword_to_lens_id,
        )

        all_notes = _get_notes()
        current_platform = _normalize_platform(platform)
        platform_notes = [n for n in all_notes if _normalize_platform(n.get("platform")) == current_platform]
        total_all = len(platform_notes)
        categories = _build_category_index(platform_notes)

        # 类目（CategoryLens）Tab
        all_lenses_map = load_category_lenses()
        lens_counter: dict[str, int] = {}
        for n in platform_notes:
            lid = n.get("lens_id") or route_keyword_to_lens_id(n.get("keyword"))
            if lid:
                lens_counter[lid] = lens_counter.get(lid, 0) + 1
        lens_tabs = []
        for lid, lens_obj in all_lenses_map.items():
            lens_tabs.append(
                {
                    "lens_id": lid,
                    "category_cn": lens_obj.category_cn,
                    "count": lens_counter.get(lid, 0),
                }
            )
        lens_tabs.sort(key=lambda x: (-x["count"], x["lens_id"]))

        # 向后兼容：旧 ?keyword=xxx → 视为 q
        if not q and keyword:
            q = keyword

        filtered = platform_notes
        if lens:
            want_lens = lens.strip()
            filtered = [
                n for n in filtered
                if (n.get("lens_id") or route_keyword_to_lens_id(n.get("keyword"))) == want_lens
            ]
        if category:
            want = category.strip()
            if want == "未分类":
                filtered = [n for n in filtered if not (n.get("keyword") or "").strip()]
            else:
                filtered = [n for n in filtered if (n.get("keyword") or "").strip() == want]
        if q:
            needle = q.lower()
            filtered = [
                n for n in filtered
                if needle in (str(n.get("title", "")) + str(n.get("raw_text", ""))).lower()
            ]

        total = len(filtered)
        start = (max(page, 1) - 1) * page_size
        page_notes = filtered[start : start + page_size]

        # 给每条 note 注入 lens_id（模板可能要展示类目标签）
        for n in page_notes:
            if not n.get("lens_id"):
                n["lens_id"] = route_keyword_to_lens_id(n.get("keyword"))

        platform_tabs = [
            {"key": "xhs", "label": "小红书", "count": sum(1 for nn in all_notes if _normalize_platform(nn.get("platform")) == "xhs")},
            {"key": "dy", "label": "抖音", "count": sum(1 for nn in all_notes if _normalize_platform(nn.get("platform")) == "dy")},
        ]

        if _wants_html(request):
            return _render("notes.html", {
                "request": request,
                "notes": page_notes,
                "total": total,
                "total_all": total_all,
                "page": page,
                "page_size": page_size,
                "categories": categories,
                "current_platform": current_platform,
                "current_platform_label": _platform_label(current_platform),
                "current_category": category or "",
                "current_lens": lens or "",
                "lens_tabs": lens_tabs,
                "platform_tabs": platform_tabs,
                "q": q or "",
            })
        return {
            "total": total,
            "total_all": total_all,
            "page": page,
            "page_size": page_size,
            "categories": categories,
            "current_platform": current_platform,
            "current_platform_label": _platform_label(current_platform),
            "current_category": category or "",
            "current_lens": lens or "",
            "lens_tabs": lens_tabs,
            "platform_tabs": platform_tabs,
            "q": q or "",
            "items": page_notes,
        }

    @app.get("/notes/{note_id}")
    async def note_detail(request: Request, note_id: str, platform: str | None = None) -> Any:
        from apps.intel_hub.config_loader import (
            load_category_lenses,
            route_keyword_to_lens_id,
        )

        all_notes = _get_notes()
        p = _normalize_platform(platform) if platform else ""
        note = next(
            (
                n
                for n in all_notes
                if (n.get("raw_payload") or {}).get("note_id") == note_id
                and (not p or _normalize_platform(n.get("platform")) == p)
            ),
            None,
        )
        if note is None:
            raise HTTPException(status_code=404, detail=f"笔记 {note_id} 未找到")

        # 解析该 note 的 lens_id（若 ingest 时未带，按关键词兜底）
        lens_id = note.get("lens_id") or route_keyword_to_lens_id(note.get("keyword"))
        note["lens_id"] = lens_id
        lens_obj = None
        if lens_id:
            lens_obj = load_category_lenses().get(lens_id)

        context = {
            "request": request,
            "note": note,
            "lens_id": lens_id,
            "lens_obj": lens_obj,
        }
        if _wants_html(request):
            return _render("note_detail.html", context)
        return note

    # ── 类目透镜（CategoryLens 只读） ───────────────────

    @app.get("/category-lenses")
    async def category_lens_list(request: Request) -> Any:
        from apps.intel_hub.config_loader import (
            load_category_lenses,
            load_lens_keyword_routing,
        )

        lenses = load_category_lenses()
        routing = load_lens_keyword_routing()
        rows = [
            {
                "lens_id": lens.lens_id,
                "category_cn": lens.category_cn,
                "version": lens.version,
                "core_consumption_logic": lens.core_consumption_logic,
                "keyword_aliases": lens.keyword_aliases,
                "primary_user_jobs": lens.primary_user_jobs,
            }
            for lens in lenses.values()
        ]
        if _wants_html(request):
            return _render(
                "category_lenses.html",
                {
                    "request": request,
                    "lenses": rows,
                    "routing": routing,
                },
            )
        return {"lenses": rows, "routing": routing}

    @app.get("/category-lenses/{lens_id}")
    async def category_lens_detail(request: Request, lens_id: str) -> Any:
        from apps.intel_hub.config_loader import load_category_lenses

        lenses = load_category_lenses()
        lens = lenses.get(lens_id)
        if lens is None:
            raise HTTPException(status_code=404, detail=f"类目透镜 {lens_id} 未找到")
        payload = lens.model_dump(mode="json")
        if _wants_html(request):
            return _render(
                "category_lens_detail.html",
                {"request": request, "lens": payload},
            )
        return payload

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
        source_note_ids = card_dict.get("source_note_ids") or []
        missing_ids: list[str] = []
        for nid in source_note_ids:
            if nid in _note_ctx_index:
                source_notes.append(_note_ctx_index[nid])
            else:
                missing_ids.append(nid)
        # Agent 单条 / 增量跑出来的新笔记，启动期 cache miss 时即时刷新一次。
        if missing_ids and source_note_ids:
            _refresh_note_ctx_index()
            for nid in missing_ids:
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
                "is_promoted": card_dict.get("opportunity_status") == "promoted",
                "opportunity_id": opportunity_id,
            })
        card_dict["source_notes"] = source_notes
        return card_dict

    @app.get("/api/image-library")
    async def image_library(limit: int = 200) -> dict[str, Any]:
        """Return all note images from pipeline_details as a flat library for the ref-image picker."""
        groups: list[dict[str, Any]] = []
        for _nid, entry in list(_note_ctx_index.items())[:limit]:
            nc = entry.get("note_context", {})
            if not nc:
                continue
            imgs: list[dict[str, str]] = []
            seen: set[str] = set()
            cover = nc.get("cover_image", "")
            if cover and cover not in seen:
                seen.add(cover)
                imgs.append({"url": cover, "label": "封面"})
            for i, u in enumerate(nc.get("image_urls", [])):
                if u and u not in seen:
                    seen.add(u)
                    imgs.append({"url": u, "label": f"图{i+1}"})
            if not imgs:
                continue
            groups.append({
                "note_id": nc.get("note_id", _nid),
                "title": nc.get("title", ""),
                "likes": nc.get("like_count", 0),
                "collects": nc.get("collect_count", 0),
                "comments": nc.get("comment_count", 0),
                "images": imgs,
            })
        groups.sort(key=lambda g: g.get("likes", 0), reverse=True)
        return {"groups": groups, "total": len(groups)}

    @app.get("/xhs-opportunities")
    async def xhs_opportunities(
        request: Request,
        page: int = 1,
        page_size: int = 15,
        type: str | None = None,
        status: str | None = None,
        qualified: str | None = None,
        lens: str | None = None,
    ) -> Any:
        review_store.sync_cards_from_json(_xhs_cards_json)

        qualified_bool = None
        if qualified == "true":
            qualified_bool = True
        elif qualified == "false":
            qualified_bool = False

        # 先按 opportunity_type/status/qualified 过滤，再按 lens_id 手动过滤（分页后）
        # 当 lens 过滤生效时，拉大 page_size 获取全量再切片，避免跨页错位
        effective_page_size = page_size if not lens else max(page_size, 500)
        result = review_store.list_cards(
            opportunity_type=type,
            opportunity_status=status,
            qualified=qualified_bool,
            page=1 if lens else page,
            page_size=effective_page_size,
        )
        items = result["items"]
        if lens:
            items = [c for c in items if getattr(c, "lens_id", None) == lens]
            total = len(items)
            start = (page - 1) * page_size
            end = start + page_size
            items = items[start:end]
        else:
            total = result["total"]
        page_cards = [c.model_dump(mode="json") for c in items]
        total_pages = max(1, (total + page_size - 1) // page_size)

        tc = review_store.type_counts()
        all_types = sorted(tc.keys())

        # 计算 lens 分布（在全量 card 上统计）
        all_cards_full = review_store.list_cards(page=1, page_size=10_000)["items"]
        lens_counts: dict[str, int] = {}
        for c in all_cards_full:
            lid = getattr(c, "lens_id", None)
            key = lid or "__unassigned__"
            lens_counts[key] = lens_counts.get(key, 0) + 1
        all_lenses = sorted([k for k in lens_counts if k != "__unassigned__"])

        # 生成 lens_id -> category_cn 映射，便于 UI 展示
        try:
            from apps.intel_hub.config_loader import load_category_lenses
            lens_meta = load_category_lenses()
        except Exception:
            lens_meta = {}
        lens_labels = {lid: (lens_meta.get(lid).category_cn if lens_meta.get(lid) else lid) for lid in all_lenses}

        # lens_type_nav：当前 lens 范围内的 opportunity_type 计数（按数量倒序）
        scope_cards = all_cards_full
        if lens:
            scope_cards = [c for c in all_cards_full if getattr(c, "lens_id", None) == lens]
        scope_type_counts: dict[str, int] = {}
        for c in scope_cards:
            ot = getattr(c, "opportunity_type", None)
            if ot:
                scope_type_counts[ot] = scope_type_counts.get(ot, 0) + 1
        lens_type_nav = sorted(scope_type_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        lens_type_nav = [
            {"type": t, "count": cnt, "label": _xhs_type_labels.get(t, t)}
            for t, cnt in lens_type_nav
        ]

        # 读取 lens bundle 摘要（若存在）
        lens_bundle_summary: dict[str, dict[str, Any]] = {}
        bundles_dir = resolve_repo_path("data/output/xhs_opportunities/lens_bundles")
        if bundles_dir.exists():
            for lens_file in bundles_dir.glob("*.json"):
                try:
                    data = json.loads(lens_file.read_text(encoding="utf-8"))
                    lens_bundle_summary[lens_file.stem] = {
                        "score": (data.get("evidence_score") or {}).get("total"),
                        "decision": (data.get("recommended_action") or {}).get("decision"),
                        "hot_keyword_count": len(data.get("layer1_signals", {}).get("hot_keywords", [])),
                    }
                except Exception:
                    continue

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
            "lens_counts": lens_counts,
        }

        # 当前 lens 是否有 in-flight Agent 任务（用于刷新页面时自动续接抽屉）
        active_agent_task_id: str | None = None
        if lens:
            try:
                from apps.intel_hub.services.agent_run_registry import (
                    agent_run_registry,
                )
                active = agent_run_registry.get_active_by_lens(lens)
                if active is not None:
                    active_agent_task_id = active.task_id
            except Exception:
                active_agent_task_id = None

        # lens_label 给空态文案与抽屉标题用
        current_lens_label = lens_labels.get(lens) if lens else ""

        # 区分两种空态：全库无卡 vs 当前 lens 过滤后为空
        empty_state_kind = "none"
        if not page_cards:
            empty_state_kind = "lens_empty" if (lens and stats["total_cards"] > 0) else "global_empty"

        # 按 source_note_ids[0] 分组并 join 笔记元信息（封面、标题），让同
        # 来源的多张机会卡在前端被一眼看清是同一篇笔记产出的不同角度。
        notes_index: dict[str, dict[str, Any]] = {}
        try:
            for n in _get_notes():
                nid = (n.get("raw_payload") or {}).get("note_id")
                if nid:
                    notes_index[str(nid)] = n
        except Exception:
            notes_index = {}

        groups: dict[str, dict[str, Any]] = {}
        for card_dict in page_cards:
            snids = card_dict.get("source_note_ids") or []
            snid = snids[0] if snids else ""
            note_meta = notes_index.get(snid)
            cover_url = ""
            if note_meta:
                imgs = note_meta.get("image_list") or []
                if imgs:
                    first = imgs[0]
                    cover_url = first.get("url") if isinstance(first, dict) else str(first)
            grp = groups.setdefault(snid, {
                "note_id": snid,
                "note_meta": (
                    {
                        "title": (note_meta or {}).get("title") or "",
                        "cover_url": cover_url,
                        "platform": (note_meta or {}).get("platform") or "xhs",
                    }
                    if note_meta
                    else None
                ),
                "cards": [],
            })
            grp["cards"].append(card_dict)
        for grp in groups.values():
            grp["cards"].sort(key=lambda c: -float(c.get("confidence") or 0.0))
        note_groups = sorted(
            groups.values(),
            key=lambda g: (
                -max((float(c.get("confidence") or 0.0) for c in g["cards"]), default=0.0),
                g["note_id"] or "",
            ),
        )

        # lens 维度下的笔记总数：抽屉的"再跑全部"用它做上限提示
        lens_notes_total = 0
        if lens:
            try:
                from apps.intel_hub.config_loader import route_keyword_to_lens_id

                lens_notes_total = sum(
                    1
                    for n in _get_notes()
                    if (n.get("lens_id") or route_keyword_to_lens_id(n.get("keyword")))
                    == lens
                )
            except Exception:
                lens_notes_total = 0

        if _wants_html(request):
            return _render("xhs_opportunities.html", {
                "request": request,
                "cards": page_cards,
                "note_groups": note_groups,
                "stats": stats,
                "type_labels": _xhs_type_labels,
                "type_colors": _xhs_type_colors,
                "type_bg": _xhs_type_bg,
                "status_labels": _xhs_status_labels,
                "status_colors": _xhs_status_colors,
                "all_types": all_types,
                "all_lenses": all_lenses,
                "lens_labels": lens_labels,
                "lens_type_nav": lens_type_nav,
                "lens_bundle_summary": lens_bundle_summary,
                "type_filter": type,
                "status_filter": status,
                "lens_filter": lens,
                "lens_label": current_lens_label,
                "lens_notes_total": lens_notes_total,
                "active_agent_task_id": active_agent_task_id,
                "empty_state_kind": empty_state_kind,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            })
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": page_cards,
            "stats": stats,
            "lens_bundle_summary": lens_bundle_summary,
        }

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
    _cp_adapter = IntelHubAdapter(review_store=review_store)
    _cp_flow = OpportunityToPlanFlow(
        adapter=_cp_adapter,
        plan_store=_plan_store,
        platform_store=platform_store,
    )
    set_flow(_cp_flow)

    from apps.content_planning.agents.tool_registry import register_builtin_tools
    register_builtin_tools()

    app.include_router(content_planning_router)
    app.include_router(content_planning_router_alias)

    # ── 视觉策略编译器路由挂载（SOP→RuleSpec→StrategyCandidate→CreativeBrief→PromptSpec） ──
    from apps.content_planning.api.visual_strategy_routes import (
        router as visual_strategy_router,
        configure as configure_visual_strategy,
    )
    from apps.content_planning.storage.rule_store import RuleStore as _VSRuleStore
    from apps.growth_lab.storage.visual_strategy_store import VisualStrategyStore as _VSStore

    _vs_rule_store = _VSRuleStore()
    _vs_store_instance = _VSStore()

    def _vs_review_card_provider(opportunity_id: str):
        return review_store.get_card(opportunity_id)

    def _vs_send_to_workbench_handler(*, opportunity_id, candidate, brief, prompt_spec, notes=""):
        """把 CreativeBrief / PromptSpec 翻译成 visual-builder bootstrap 字段。"""
        plan_store = getattr(_cp_flow, "_store", None)
        if plan_store is None:
            return {"updated": []}

        quick_draft = {
            "selected_title": brief.copywriting.headline or candidate.name,
            "final_body": prompt_spec.positive_prompt_zh,
            "selling_points": list(brief.copywriting.selling_points),
            "labels": list(brief.copywriting.labels),
            "source": "visual_strategy_compiler",
            "creative_brief_id": brief.id,
            "strategy_candidate_id": candidate.id,
            "archetype": candidate.archetype,
        }

        style_tags: list[str] = []
        if brief.style.tone:
            style_tags.append(brief.style.tone)
        style_tags.extend(brief.style.color_palette[:3])
        if brief.style.lighting:
            style_tags.append(brief.style.lighting)

        must_include: list[str] = list(brief.product.visible_features)
        must_include.extend(brief.scene.props[:2])

        saved_prompt = {
            "slot_id": "main_image_1",
            "subject": brief.scene.background or brief.style.tone or candidate.name,
            "style_tags": style_tags,
            "must_include": must_include,
            "avoid_items": list(brief.negative)[:8],
            "negative_prompt": prompt_spec.negative_prompt_zh,
            "creative_brief_id": brief.id,
            "strategy_candidate_id": candidate.id,
            "sources": [
                {"priority": 1, "field": "creative_brief.copy.headline",
                 "content": brief.copywriting.headline},
                {"priority": 2, "field": "creative_brief.scene.background",
                 "content": brief.scene.background},
            ],
        }

        try:
            plan_store.update_field(opportunity_id, "quick_draft", quick_draft)
            plan_store.update_field(opportunity_id, "saved_prompts", [saved_prompt])
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return {
            "updated": ["quick_draft", "saved_prompts"],
            "creative_brief_id": brief.id,
            "prompt_spec_id": prompt_spec.id,
        }

    configure_visual_strategy(
        rule_store=_vs_rule_store,
        visual_strategy_store=_vs_store_instance,
        review_card_provider=_vs_review_card_provider,
        send_to_workbench_handler=_vs_send_to_workbench_handler,
    )
    app.include_router(visual_strategy_router)

    # ── 视觉策略编译器：HTML 控制台路由 ─────────────────────────
    # 与 visual_strategy_router 暴露的 JSON 端点共用同一个 RuleStore，
    # 这里只挂可访问的 HTML 页面（评审台 / 行业策略库管理）。
    _SUPPORTED_REVIEW_STATUSES = {"draft", "approved", "needs_edit", "rejected"}

    @app.get("/content-planning/visual-strategy/rule-review", response_class=HTMLResponse)
    async def rule_review_console_html(
        request: Request,
        category: str = "",
        dimension: str = "",
        review_status: str = "",
    ) -> HTMLResponse:
        """策略评审台：从 RuleStore 预读规则列表。"""
        category_q = (category or "").strip()
        dimension_q = (dimension or "").strip()
        status_q = (review_status or "").strip()
        if status_q and status_q not in _SUPPORTED_REVIEW_STATUSES:
            status_q = ""

        rules = _vs_rule_store.list_rule_specs(
            category=category_q or None,
            dimension=dimension_q or None,
            review_status=status_q or None,
            limit=500,
        )

        all_for_stats = (
            _vs_rule_store.list_rule_specs(
                category=category_q or None,
                dimension=dimension_q or None,
                limit=2000,
            )
            if (category_q or dimension_q)
            else _vs_rule_store.list_rule_specs(limit=2000)
        )
        stats = {"draft": 0, "approved": 0, "needs_edit": 0, "rejected": 0}
        dimensions: set[str] = set()
        for r in all_for_stats:
            dim = r.get("dimension")
            if dim:
                dimensions.add(dim)
            st = (r.get("review") or {}).get("status") or "draft"
            if st in stats:
                stats[st] += 1

        return _render(
            "rule_review.html",
            {
                "request": request,
                "rules": rules,
                "stats": stats,
                "dimensions": sorted(dimensions),
                "filter_category": category_q,
                "filter_dimension": dimension_q,
                "filter_status": status_q,
            },
        )

    @app.get("/content-planning/visual-strategy/rulepacks-console", response_class=HTMLResponse)
    async def rulepacks_console_html(
        request: Request,
        category: str = "",
    ) -> HTMLResponse:
        """行业策略库管理：列出该类目所有 RulePack 版本。

        路径用 ``/rulepacks-console`` 而不是 ``/rulepacks/console``，避免
        与 visual_strategy_router 已注册的 ``GET /rulepacks/{rule_pack_id}``
        路由模板冲突（"console" 会被当作 rule_pack_id 命中 404）。
        """
        category_q = (category or "").strip()
        rule_packs = _vs_rule_store.list_rule_packs(category=category_q or None)
        return _render(
            "rulepacks.html",
            {
                "request": request,
                "rule_packs": rule_packs,
                "filter_category": category_q,
            },
        )

    # ── growth_lab 路由挂载（裂变系统） ─────────────────────────
    from apps.growth_lab.api.routes import router as growth_lab_router
    app.include_router(growth_lab_router)

    # ── 内容策划工作台页面路由 ─────────────────────────────────
    @app.get("/content-planning/stream/{opportunity_id}")
    async def content_planning_stream(request: Request, opportunity_id: str):
        """SSE 事件流：实时推送 Agent 输出与对象变更。"""
        return await sse_stream(request, opportunity_id)

    # ── 机会卡生成 Agent（按类目一键生成 + 可观测 SSE） ────────
    from apps.intel_hub.services.agent_run_registry import agent_run_registry
    from apps.intel_hub.services.opportunity_gen_agent import (
        OpportunityGenAgent,
        channel_for as _agent_channel_for,
    )

    _agent_tasks: dict[str, asyncio.Task[None]] = {}

    @app.post("/xhs-opportunities/agent-runs")
    async def start_agent_run(payload: StartAgentRunRequest) -> dict[str, Any]:
        lens_id = (payload.lens_id or "").strip()
        if not lens_id:
            raise HTTPException(status_code=400, detail="缺少 lens_id")
        try:
            from apps.intel_hub.config_loader import load_category_lenses
            lenses = load_category_lenses()
        except Exception:
            lenses = {}
        lens_obj = lenses.get(lens_id)
        lens_label = (
            getattr(lens_obj, "category_cn", None) or lens_id
        ) if lens_obj is not None else lens_id

        skip_note_ids = [s for s in (payload.skip_note_ids or []) if s]
        note_id_filter = (payload.note_id or "").strip() or None

        try:
            task_id, snap = agent_run_registry.start(
                lens_id,
                lens_label=lens_label,
                options={
                    "max_notes": int(payload.max_notes),
                    "skip_note_ids_count": len(skip_note_ids),
                    "note_id": note_id_filter or "",
                },
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        # 把 /notes 同款数据源注入：runtime settings 中所有启用的 xhs sources（含 fixture_fallback）
        jsonl_dirs: list[Path] = []
        for src in settings.mediacrawler_sources:
            if not src.get("enabled", True):
                continue
            platform_name = str(src.get("platform", "xiaohongshu")).lower()
            if platform_name not in {"xiaohongshu", "xhs", "rednote"}:
                continue
            out = resolve_repo_path(src.get("output_path", ""))
            if out.exists() and out not in jsonl_dirs:
                jsonl_dirs.append(out)
            fb = src.get("fixture_fallback")
            if fb:
                fb_path = resolve_repo_path(fb)
                if fb_path.exists() and fb_path not in jsonl_dirs:
                    jsonl_dirs.append(fb_path)

        agent = OpportunityGenAgent(
            task_id=task_id,
            lens_id=lens_id,
            registry=agent_run_registry,
            review_store=review_store,
            max_notes=int(payload.max_notes),
            jsonl_dirs=jsonl_dirs,
            skip_note_ids=skip_note_ids,
            note_id_filter=note_id_filter,
        )
        task = asyncio.create_task(agent.run(), name=f"agent_run:{task_id}")
        _agent_tasks[task_id] = task

        def _cleanup(_t: asyncio.Task) -> None:
            _agent_tasks.pop(task_id, None)
        task.add_done_callback(_cleanup)

        return {
            "task_id": task_id,
            "lens_id": lens_id,
            "lens_label": lens_label,
            "status": snap.status,
            "stream_url": f"/xhs-opportunities/agent-runs/{task_id}/stream",
        }

    @app.get("/xhs-opportunities/agent-runs/{task_id}")
    async def get_agent_run(task_id: str) -> dict[str, Any]:
        snap = agent_run_registry.get(task_id)
        if snap is None:
            raise HTTPException(status_code=404, detail="任务不存在或已被回收")
        return snap.to_dict()

    @app.get("/xhs-opportunities/agent-runs/{task_id}/stream")
    async def agent_run_stream(request: Request, task_id: str):
        """SSE 流：复用 event_bus channel ``agent_run:{task_id}``。"""
        return await sse_stream(request, _agent_channel_for(task_id))

    @app.post("/xhs-opportunities/agent-runs/{task_id}/cancel")
    async def cancel_agent_run(task_id: str) -> dict[str, Any]:
        ok = agent_run_registry.request_cancel(task_id)
        if not ok:
            raise HTTPException(status_code=404, detail="任务不存在或已结束")
        return {"task_id": task_id, "cancelled": True}

    @app.get("/content-planning/timeline/{opportunity_id}")
    async def content_planning_timeline(request: Request, opportunity_id: str):
        """获取协同时间线（历史消息 + Agent 事件）。"""
        session = session_manager.get_or_create(opportunity_id)
        events = event_bus.get_history(opportunity_id)
        return {
            "session_id": session.session_id,
            "messages": [m.model_dump(mode="json") for m in session.recent_messages(50)],
            "events": [e.model_dump(mode="json") for e in events[-30:]],
            "participants": session.participants,
        }

    @app.get("/content-planning/brief/{opportunity_id}")
    async def content_brief_page(request: Request, opportunity_id: str) -> Any:
        """Brief 确认页 / 机会工作台。"""
        t0 = time.perf_counter()
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")

        source_notes = _cp_adapter.get_source_notes(card.source_note_ids) if card.source_note_ids else []
        source_ctx = []
        for sn in source_notes[:1]:
            ctx = {"note_context": sn} if isinstance(sn, dict) else {"note_context": {}}
            source_ctx.append(ctx)

        review_summary = _cp_adapter.get_review_summary(opportunity_id)
        session_data = _cp_flow.get_session_data(opportunity_id)
        stale_flags = session_data.get("stale_flags", {})
        pipeline_run_id = session_data.get("pipeline_run_id", "")
        refresh_requested = _refresh_requested(request)

        if refresh_requested:
            try:
                brief = _cp_flow.build_brief(opportunity_id)
                brief_dict = brief.model_dump(mode="json")
            except Exception:
                brief_dict = session_data.get("brief", {})
        else:
            brief_dict = session_data.get("brief", {})
        needs_build = not bool(brief_dict)

        card_dict = card.model_dump(mode="json") if hasattr(card, "model_dump") else card
        if _wants_html(request):
            response = _render("content_brief.html", {
                "request": request,
                "opportunity_id": opportunity_id,
                "card": card_dict,
                "brief": brief_dict,
                "source_notes": source_ctx,
                "review_summary": review_summary or {},
                "stale_flags": stale_flags,
                "pipeline_run_id": pipeline_run_id,
                "needs_build": needs_build,
                "refresh_url": f"/content-planning/brief/{opportunity_id}?refresh=1",
            })
            response.headers["X-Render-Timing-Ms"] = str(int((time.perf_counter() - t0) * 1000))
            return response
        return {"card": card_dict, "brief": brief_dict}

    @app.get("/content-planning/strategy/{opportunity_id}")
    async def content_strategy_page(request: Request, opportunity_id: str) -> Any:
        """模板与策略页 / 策划工作台。"""
        t0 = time.perf_counter()
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")

        session_data = _cp_flow.get_session_data(opportunity_id)
        stale_flags = session_data.get("stale_flags", {})
        refresh_requested = _refresh_requested(request)

        if refresh_requested:
            try:
                data = _cp_flow.build_note_plan(opportunity_id, with_generation=False)
            except Exception as exc:
                data = {
                    "brief": session_data.get("brief", {}),
                    "match_result": session_data.get("match_result", {}),
                    "strategy": session_data.get("strategy", {}),
                    "error": str(exc),
                }
        else:
            data = {
                "brief": session_data.get("brief", {}),
                "match_result": session_data.get("match_result", {}),
                "strategy": session_data.get("strategy", {}),
            }
        needs_build = not bool(data.get("strategy"))

        if _wants_html(request):
            response = _render("content_strategy.html", {
                "request": request,
                "opportunity_id": opportunity_id,
                "card": card.model_dump(mode="json"),
                "brief": data.get("brief", {}),
                "match_result": data.get("match_result", {}),
                "strategy": data.get("strategy", {}),
                "stale_flags": stale_flags,
                "needs_build": needs_build,
                "refresh_url": f"/content-planning/strategy/{opportunity_id}?refresh=1",
            })
            response.headers["X-Render-Timing-Ms"] = str(int((time.perf_counter() - t0) * 1000))
            return response
        return data

    @app.get("/content-planning/plan/{opportunity_id}")
    async def content_plan_page(request: Request, opportunity_id: str) -> Any:
        """内容策划页 / 资产工作台。"""
        t0 = time.perf_counter()
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")

        session_data = _cp_flow.get_session_data(opportunity_id)
        stale_flags = session_data.get("stale_flags", {})
        refresh_requested = _refresh_requested(request)

        if refresh_requested:
            try:
                data = _cp_flow.build_note_plan(opportunity_id, with_generation=True)
            except Exception as exc:
                data = {
                    "brief": session_data.get("brief", {}),
                    "match_result": session_data.get("match_result", {}),
                    "strategy": session_data.get("strategy", {}),
                    "note_plan": session_data.get("note_plan", {}),
                    "generated": {
                        "titles": session_data.get("titles", {}),
                        "body": session_data.get("body", {}),
                        "image_briefs": session_data.get("image_briefs", {}),
                    },
                    "error": str(exc),
                }
        else:
            data = {
                "brief": session_data.get("brief", {}),
                "match_result": session_data.get("match_result", {}),
                "strategy": session_data.get("strategy", {}),
                "note_plan": session_data.get("note_plan", {}),
                "generated": {
                    "titles": session_data.get("titles", {}),
                    "body": session_data.get("body", {}),
                    "image_briefs": session_data.get("image_briefs", {}),
                },
            }
        needs_build = not bool(data.get("note_plan"))

        if _wants_html(request):
            response = _render("content_plan.html", {
                "request": request,
                "opportunity_id": opportunity_id,
                "brief": data.get("brief", {}),
                "strategy": data.get("strategy", {}),
                "match_result": data.get("match_result", {}),
                "note_plan": data.get("note_plan", {}),
                "generated": data.get("generated"),
                "stale_flags": stale_flags,
                "needs_build": needs_build,
                "refresh_url": f"/content-planning/plan/{opportunity_id}?refresh=1",
            })
            response.headers["X-Render-Timing-Ms"] = str(int((time.perf_counter() - t0) * 1000))
            return response
        return data

    @app.get("/content-planning/assets/{opportunity_id}")
    async def content_assets_page(request: Request, opportunity_id: str) -> Any:
        """资产工作台。"""
        t0 = time.perf_counter()
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")

        try:
            bundle = _cp_flow.assemble_asset_bundle(opportunity_id)
            bundle_dict = bundle.model_dump(mode="json") if hasattr(bundle, "model_dump") else {}
        except Exception:
            bundle_dict = {}
        session_data = _cp_flow.get_session_data(opportunity_id)

        if _wants_html(request):
            response = _render("content_assets.html", {
                "request": request,
                "opportunity_id": opportunity_id,
                "bundle": bundle_dict,
                "brief": session_data.get("brief", {}),
                "strategy": session_data.get("strategy", {}),
                "match_result": session_data.get("match_result", {}),
                "generated": {
                    "titles": session_data.get("titles", {}),
                    "body": session_data.get("body", {}),
                    "image_briefs": session_data.get("image_briefs", {}),
                },
                "lineage": bundle_dict.get("lineage", {}),
                "stale_flags": session_data.get("stale_flags", {}),
            })
            response.headers["X-Render-Timing-Ms"] = str(int((time.perf_counter() - t0) * 1000))
            return response
        return {"bundle": bundle_dict}

    # ── 四工作台极简化路由 ──────────────────────────────────

    def _download_image(url: str, dest: Path) -> bool:
        """下载单张图片到本地，返回是否成功。"""
        import urllib.request
        if not url or not url.startswith("http"):
            return False
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://www.xiaohongshu.com/",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                dest.write_bytes(resp.read())
            return dest.stat().st_size > 500
        except Exception:
            return False

    def _persist_source_images(opportunity_id: str, source_notes: list) -> list[dict[str, Any]]:
        """首次加载时把来源笔记图片下载到本地并写入 session。返回 source_images 列表。

        参考图健壮性：cover/image_urls 在尝试下载前先经过
        :func:`apps.content_planning.utils.ref_image_filter.is_usable_ref_url`
        过滤，避免 fixture 占位 URL（example.com / mock-cdn）流到生图链路。
        """
        from apps.content_planning.utils.ref_image_filter import is_usable_ref_url

        try:
            cached = None
            if hasattr(_cp_flow, "_store") and _cp_flow._store:
                row = _cp_flow._store.load_session(opportunity_id)
                if row and row.get("source_images"):
                    cached = row.get("source_images")
            if not cached:
                existing = _cp_flow.get_session_data(opportunity_id)
                cached = existing.get("source_images") if isinstance(existing, dict) else None
            if cached:
                return cached  # type: ignore[return-value]

            out_dir = _source_images_dir / opportunity_id
            out_dir.mkdir(parents=True, exist_ok=True)

            imgs: list[dict[str, Any]] = []
            for sn in source_notes:
                nc = sn.get("note_context", sn) if isinstance(sn, dict) else {}
                note_id = nc.get("note_id", "") or sn.get("note_id", "") or "unknown"
                original_cover = nc.get("cover_image", "")
                original_urls = nc.get("image_urls", []) or []

                cover_usable = is_usable_ref_url(original_cover)
                usable_originals = [u for u in original_urls if is_usable_ref_url(u)]

                local_cover = ""
                if cover_usable:
                    suffix = ".jpg"
                    if ".png" in original_cover:
                        suffix = ".png"
                    elif ".webp" in original_cover:
                        suffix = ".webp"
                    cover_path = out_dir / f"cover_{note_id[:12]}{suffix}"
                    if _download_image(original_cover, cover_path):
                        local_cover = str(cover_path)

                local_urls: list[str] = []
                for idx, img_url in enumerate(usable_originals[:6]):
                    if img_url == original_cover:
                        if local_cover:
                            local_urls.append(local_cover)
                        continue
                    suffix = ".jpg"
                    if ".png" in img_url:
                        suffix = ".png"
                    elif ".webp" in img_url:
                        suffix = ".webp"
                    img_path = out_dir / f"img_{note_id[:12]}_{idx}{suffix}"
                    if _download_image(img_url, img_path):
                        local_urls.append(str(img_path))

                effective_cover = local_cover or (original_cover if cover_usable else "")
                effective_urls = local_urls if local_urls else usable_originals
                ref_quality = "ok" if (effective_cover or effective_urls) else "unusable_fixture"

                imgs.append({
                    "note_id": note_id,
                    "cover_image": effective_cover,
                    "image_urls": effective_urls,
                    "original_cover_url": original_cover,
                    "original_image_urls": original_urls,
                    "title": nc.get("title", "") or sn.get("title", ""),
                    "ref_quality": ref_quality,
                })
            if imgs and hasattr(_cp_flow, "_store") and _cp_flow._store:
                existing_row = _cp_flow._store.load_session(opportunity_id)
                if existing_row is None:
                    _cp_flow._store.save_session(opportunity_id)
                _cp_flow._store.update_field(opportunity_id, "source_images", imgs)
            return imgs
        except Exception:
            return []

    @app.get("/planning/{opportunity_id}")
    async def planning_workspace_page(request: Request, opportunity_id: str) -> Any:
        """策划台聚合 API：汇总机会卡 + brief + 策略 + 笔记计划 + 资产包。"""
        t0 = time.perf_counter()
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")
        card_dict = card.model_dump(mode="json") if hasattr(card, "model_dump") else card

        source_notes = _cp_adapter.get_source_notes(card.source_note_ids) if card.source_note_ids else []
        source_ctx = []
        for sn in source_notes[:1]:
            ctx = {"note_context": sn} if isinstance(sn, dict) else {"note_context": {}}
            source_ctx.append(ctx)

        _persist_source_images(opportunity_id, source_notes)

        review_summary = _cp_adapter.get_review_summary(opportunity_id)

        refresh_requested = _refresh_requested(request)
        if refresh_requested:
            try:
                _cp_flow.build_note_plan(opportunity_id, with_generation=True)
            except Exception:
                pass

        session_data = _cp_flow.get_session_data(opportunity_id)
        brief_dict = session_data.get("brief", {})
        match_result = session_data.get("match_result", {})
        strategy = session_data.get("strategy", {})
        note_plan = session_data.get("note_plan", {})
        generated = {
            "titles": session_data.get("titles", {}),
            "body": session_data.get("body", {}),
            "image_briefs": session_data.get("image_briefs", {}),
        }
        stale_flags = session_data.get("stale_flags", {})
        pipeline_run_id = session_data.get("pipeline_run_id", "")
        needs_build = not bool(brief_dict)

        cached_bundle = session_data.get("asset_bundle", {})
        bundle_dict = cached_bundle if isinstance(cached_bundle, dict) else {}

        from apps.content_planning.viewmodels.planning_workspace_vm import build_workspace_vm
        vm = build_workspace_vm(card_dict, brief_dict, match_result, strategy, note_plan, generated)

        ctx = {
            "request": request,
            "opportunity_id": opportunity_id,
            "card": card_dict,
            "brief": brief_dict,
            "match_result": match_result,
            "strategy": strategy,
            "note_plan": note_plan,
            "generated": generated,
            "stale_flags": stale_flags,
            "pipeline_run_id": pipeline_run_id,
            "needs_build": needs_build,
            "source_notes": source_ctx,
            "review_summary": review_summary or {},
            "bundle": bundle_dict,
            "refresh_url": f"/planning/{opportunity_id}?refresh=1",
            "vm": vm,
        }

        if _wants_html(request):
            response = _render("planning_workspace.html", ctx)
            response.headers["X-Render-Timing-Ms"] = str(int((time.perf_counter() - t0) * 1000))
            return response
        return {k: v for k, v in ctx.items() if k not in ("request", "vm")}

    @app.get("/planning/{opportunity_id}/visual-builder")
    async def visual_builder_page(request: Request, opportunity_id: str) -> Any:
        """视觉工作台独立页：三栏布局，来源证据 + 预览画布 + Prompt 编辑。"""
        t0 = time.perf_counter()
        card = review_store.get_card(opportunity_id)
        if card is None:
            raise HTTPException(status_code=404, detail="机会卡未找到")
        card_dict = card.model_dump(mode="json") if hasattr(card, "model_dump") else card

        source_notes = _cp_adapter.get_source_notes(card.source_note_ids) if card.source_note_ids else []
        source_images = _persist_source_images(opportunity_id, source_notes)

        session_data = _cp_flow.get_session_data(opportunity_id)
        brief_dict = session_data.get("brief", {})
        strategy = session_data.get("strategy", {})
        if not source_images:
            source_images = session_data.get("source_images", [])
        if not source_images and hasattr(_cp_flow, "_store") and _cp_flow._store:
            store_row = _cp_flow._store.load_session(opportunity_id)
            if store_row and store_row.get("source_images"):
                source_images = store_row["source_images"] or []
        if not source_images:
            source_images = []
            for sn in source_notes:
                nc = sn.get("note_context", sn) if isinstance(sn, dict) else {}
                source_images.append({
                    "note_id": nc.get("note_id", ""),
                    "cover_image": nc.get("cover_image", ""),
                    "image_urls": nc.get("image_urls", []),
                    "title": nc.get("title", "") or sn.get("title", ""),
                })

        def _to_web_url(path_or_url: str) -> str:
            if not path_or_url:
                return ""
            if path_or_url.startswith("http"):
                return path_or_url
            src_dir_str = str(_source_images_dir)
            if path_or_url.startswith(src_dir_str):
                return "/source-images" + path_or_url[len(src_dir_str):]
            return path_or_url

        display_images = []
        for si in source_images:
            display_images.append({
                **si,
                "cover_image": _to_web_url(si.get("cover_image", "")),
                "image_urls": [_to_web_url(u) for u in si.get("image_urls", [])],
            })

        # ── bootstrap：把策划台已产出的内容直接接力到视觉工作台 ──
        from apps.content_planning.utils.ref_image_filter import filter_usable_ref_urls

        plan_store = getattr(_cp_flow, "_store", None)

        def _store_field(name: str) -> Any:
            try:
                return plan_store.get_field(opportunity_id, name) if plan_store else None
            except Exception:
                return None

        quick_draft = _store_field("quick_draft") or session_data.get("quick_draft") or None
        saved_prompts_raw = _store_field("saved_prompts") or session_data.get("saved_prompts") or []
        saved_prompts = saved_prompts_raw if isinstance(saved_prompts_raw, list) else []
        titles = session_data.get("titles") or {}
        body = session_data.get("body") or {}
        image_briefs = session_data.get("image_briefs") or {}
        slot_briefs_raw = []
        if isinstance(image_briefs, dict):
            slot_briefs_raw = image_briefs.get("slot_briefs", []) or []

        gen_history = _store_field("generated_images") or session_data.get("generated_images") or []
        latest_generated_images: list[dict[str, Any]] = []
        if isinstance(gen_history, list) and gen_history:
            last = gen_history[-1]
            if isinstance(last, dict):
                results = last.get("results", []) if isinstance(last.get("results"), list) else []
                latest_generated_images = [
                    {
                        "url": (r.get("image_url") or r.get("url") or ""),
                        "slot_id": r.get("slot_id", ""),
                        "rating": r.get("rating", ""),
                    }
                    for r in results if isinstance(r, dict) and (r.get("image_url") or r.get("url"))
                ]

        # 计算可用 ref 数（基于 source_images 经过滤后的 URL）
        ref_candidates: list[str] = []
        for si in source_images:
            cover = si.get("cover_image", "") if isinstance(si, dict) else ""
            if cover:
                ref_candidates.append(cover)
            for img in (si.get("image_urls", []) if isinstance(si, dict) else []):
                if img and img != cover:
                    ref_candidates.append(img)
        usable_refs = filter_usable_ref_urls(ref_candidates)
        ref_count = len(usable_refs)

        # 服务端预合成 prompts，避免前端再 roundtrip。saved_prompts 优先。
        initial_prompts: list[dict[str, Any]] = []
        prompts_source = ""
        if saved_prompts:
            initial_prompts = [p for p in saved_prompts if isinstance(p, dict)]
            prompts_source = "saved"
        else:
            try:
                from apps.content_planning.api.routes import _build_rich_prompts
                pre_mode = "ref_image" if ref_count > 0 else "prompt_only"
                rich_prompts, _ = _build_rich_prompts(opportunity_id, session_data, pre_mode)
                initial_prompts = [p.model_dump() for p in rich_prompts] if rich_prompts else []
                prompts_source = "composed"
            except Exception as exc:  # noqa: BLE001
                initial_prompts = []
                prompts_source = "unavailable"
                import sys as _sys
                print(
                    f"[visual-builder] bootstrap 预合成 prompts 失败 opp={opportunity_id} err={exc}",
                    file=_sys.stderr,
                )

        gen_mode_effective = "prompt_only" if ref_count == 0 else "ref_image"

        bootstrap = {
            "opportunity_id": opportunity_id,
            "quick_draft": quick_draft,
            "titles": titles,
            "body": body,
            "image_briefs": image_briefs,
            "slot_briefs": slot_briefs_raw if isinstance(slot_briefs_raw, list) else [],
            "saved_prompts": saved_prompts,
            "initial_prompts": initial_prompts,
            "prompts_source": prompts_source,
            "ref_count": ref_count,
            "has_ref_images": ref_count > 0,
            "gen_mode_effective": gen_mode_effective,
            "latest_generated_images": latest_generated_images,
        }

        ctx = {
            "request": request,
            "opportunity_id": opportunity_id,
            "card": card_dict,
            "brief": brief_dict,
            "strategy": strategy,
            "source_images": display_images,
            "back_url": f"/planning/{opportunity_id}",
            "bootstrap": bootstrap,
        }

        if _wants_html(request):
            response = _render("visual_builder.html", ctx)
            response.headers["X-Render-Timing-Ms"] = str(int((time.perf_counter() - t0) * 1000))
            return response
        return {k: v for k, v in ctx.items() if k != "request"}

    @app.get("/opportunity-workspace")
    async def opportunity_workspace_page(
        request: Request,
        type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
        selected: str | None = None,
    ) -> Any:
        """机会台聚合 API：机会列表 + 可选的卡片详情侧边栏。"""
        t0 = time.perf_counter()
        review_store.sync_cards_from_json(_xhs_cards_json)

        result = review_store.list_cards(
            opportunity_type=type,
            opportunity_status=status,
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

        selected_card = None
        selected_notes: list[dict[str, Any]] = []
        selected_review_summary: dict[str, Any] = {}
        if not selected and page_cards:
            selected = page_cards[0].get("opportunity_id", "")
        if selected:
            sel_card = review_store.get_card(selected)
            if sel_card is not None:
                selected_card = sel_card.model_dump(mode="json") if hasattr(sel_card, "model_dump") else sel_card
                selected_notes = _cp_adapter.get_source_notes(sel_card.source_note_ids) if sel_card.source_note_ids else []
                selected_review_summary = _cp_adapter.get_review_summary(selected) or {}

        ctx = {
            "request": request,
            "cards": page_cards,
            "stats": stats,
            "type_labels": _xhs_type_labels,
            "type_colors": _xhs_type_colors,
            "type_bg": _xhs_type_bg,
            "status_labels": _xhs_status_labels,
            "status_colors": _xhs_status_colors,
            "all_types": all_types,
            "filters": {"type": type, "status": status},
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "selected_card": selected_card,
            "selected_notes": selected_notes,
            "selected_review_summary": selected_review_summary,
        }

        if _wants_html(request):
            response = _render("opportunity_workspace.html", ctx)
            response.headers["X-Render-Timing-Ms"] = str(int((time.perf_counter() - t0) * 1000))
            return response
        return {k: v for k, v in ctx.items() if k != "request"}

    # ── 新增页面路由（全链路体验升级） ─────────────────────────
    @app.get("/workspace", response_class=HTMLResponse)
    async def workspace_home(request: Request) -> HTMLResponse:
        pipeline_stats = {"total": review_store.card_count()}
        return _render("workspace_home.html", {"request": request, "stats": pipeline_stats})

    # ── SystemAssetService（统一资产视图） ────────────────────
    from apps.intel_hub.services.system_asset_service import SystemAssetService

    def _growth_store_factory() -> Any:
        from apps.growth_lab.api.routes import _get_store as _gl_get_store
        return _gl_get_store()

    _system_asset_service = SystemAssetService(
        storage_path=resolve_repo_path("data/runtime_data/system_assets.json"),
        review_store=review_store,
        cp_flow=_cp_flow,
        growth_store_factory=_growth_store_factory,
    )

    _LANE_LABELS = {
        "content_note": "图文笔记",
        "growth_lab": "增长实验",
        "workspace_bundle": "套图",
    }

    @app.get("/asset-workspace")
    async def asset_workspace_page(
        request: Request,
        lane: str | None = None,
        lens: str | None = None,
        status: str | None = None,
        asset_type: str | None = None,
    ) -> Any:
        """系统资产工作台：聚合三主线（图文笔记 / 增长实验 / 套图）统一展示。"""
        assets = _system_asset_service.list_assets(
            lane=lane, lens=lens, status=status, asset_type=asset_type,
        )
        # 按 lane 计数（不受 lane 过滤影响，便于 Tab 显示总数）
        all_assets = (
            assets if lane is None
            else _system_asset_service.list_assets(lens=lens, status=status, asset_type=asset_type)
        )
        lane_counts: dict[str, int] = {"all": len(all_assets)}
        for a in all_assets:
            lane_counts[a.source_lane] = lane_counts.get(a.source_lane, 0) + 1

        items_view = [
            {
                "asset_id": a.asset_id,
                "source_lane": a.source_lane,
                "source_lane_label": _LANE_LABELS.get(a.source_lane, a.source_lane),
                "source_ref": a.source_ref,
                "lens_id": a.lens_id,
                "asset_type": a.asset_type,
                "title": a.title,
                "thumbnails": a.thumbnails,
                "status": a.status,
                "lineage": a.lineage,
                "created_at": a.created_at.isoformat() if a.created_at else "",
                "primary_link": a.primary_link(),
            }
            for a in assets
        ]

        if _wants_html(request):
            return _render("asset_workspace_list.html", {
                "request": request,
                "items": items_view,
                "lane_counts": lane_counts,
                "current_lane": lane,
                "current_lens": lens,
                "current_status": status,
                "current_asset_type": asset_type,
                "lane_labels": _LANE_LABELS,
            })
        return {
            "items": items_view,
            "lane_counts": lane_counts,
            "filters": {
                "lane": lane,
                "lens": lens,
                "status": status,
                "asset_type": asset_type,
            },
        }

    @app.get("/api/system-assets")
    async def api_system_assets(
        lane: str | None = None,
        lens: str | None = None,
        status: str | None = None,
        asset_type: str | None = None,
    ) -> dict[str, Any]:
        """JSON API：供其他页面调用聚合的系统资产列表。"""
        assets = _system_asset_service.list_assets(
            lane=lane, lens=lens, status=status, asset_type=asset_type,
        )
        return {
            "items": [json.loads(a.model_dump_json()) for a in assets],
            "total": len(assets),
            "filters": {
                "lane": lane,
                "lens": lens,
                "status": status,
                "asset_type": asset_type,
            },
        }

    @app.get("/brand-config/{brand_id}", response_class=HTMLResponse)
    async def brand_config_page(request: Request, brand_id: str) -> HTMLResponse:
        brand = platform_store.get_brand(brand_id) if hasattr(platform_store, "get_brand") else None
        brand_dict = brand.model_dump(mode="json") if brand and hasattr(brand, "model_dump") else {"brand_id": brand_id, "name": brand_id}
        guardrails = []
        if hasattr(platform_store, "list_guardrails"):
            guardrails = platform_store.list_guardrails(brand_id)
        return _render("brand_config.html", {"request": request, "brand": brand_dict, "guardrails": guardrails})

    @app.get("/feedback", response_class=HTMLResponse)
    async def feedback_page(request: Request) -> HTMLResponse:
        feedback: list[Any] = []
        winning: list[Any] = []
        failed: list[Any] = []
        publish_results: list[Any] = []
        if hasattr(_plan_store, "load_feedback_records"):
            try:
                feedback = _plan_store.load_feedback_records()
            except TypeError:
                try:
                    feedback = _plan_store.load_feedback_records(workspace_id=None)
                except Exception:
                    feedback = []
        if hasattr(_plan_store, "load_winning_patterns"):
            try:
                winning = _plan_store.load_winning_patterns()
            except TypeError:
                try:
                    winning = _plan_store.load_winning_patterns(workspace_id=None)
                except Exception:
                    winning = []
        if hasattr(_plan_store, "load_failed_patterns"):
            try:
                failed = _plan_store.load_failed_patterns()
            except TypeError:
                try:
                    failed = _plan_store.load_failed_patterns(workspace_id=None)
                except Exception:
                    failed = []
        if hasattr(platform_store, "list_publish_results"):
            try:
                publish_results = platform_store.list_publish_results()
            except TypeError:
                try:
                    publish_results = platform_store.list_publish_results(workspace_id=None)
                except Exception:
                    publish_results = []
        return _render(
            "content_feedback.html",
            {
                "request": request,
                "feedback_records": feedback,
                "winning_patterns": winning,
                "failed_patterns": failed,
                "publish_results": [p.model_dump(mode="json") if hasattr(p, "model_dump") else p for p in publish_results],
            },
        )

    @app.get("/opportunity-pipeline", response_class=HTMLResponse)
    async def opportunity_pipeline_page(request: Request) -> HTMLResponse:
        review_store.sync_cards_from_json(_xhs_cards_json)
        all_cards = review_store.list_cards(page=1, page_size=500)
        cards = [c.model_dump(mode="json") for c in all_cards.get("items", [])]
        by_status: dict[str, list] = {}
        for c in cards:
            ls = c.get("lifecycle_status") or c.get("opportunity_status", "new")
            by_status.setdefault(ls, []).append(c)
        return _render(
            "opportunity_pipeline.html",
            {
                "request": request,
                "by_status": by_status,
                "total": len(cards),
            },
        )

    @app.get("/review-approval", response_class=HTMLResponse)
    async def review_approval_page(request: Request) -> HTMLResponse:
        approvals = []
        if hasattr(platform_store, "list_all_approval_requests"):
            approvals = platform_store.list_all_approval_requests()
        elif hasattr(platform_store, "list_approval_requests"):
            approvals = platform_store.list_approval_requests("")
        return _render(
            "review_approval.html",
            {
                "request": request,
                "approvals": [a.model_dump(mode="json") if hasattr(a, "model_dump") else a for a in approvals],
            },
        )

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
                    "title": "监控列表",
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


def _refresh_requested(request: Request) -> bool:
    value = (request.query_params.get("refresh", "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


app = create_app()
