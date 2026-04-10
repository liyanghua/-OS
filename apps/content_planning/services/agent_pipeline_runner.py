"""AgentPipelineRunner：Agent 一键策划全链路编排器。

桥接 GraphExecutor（Agent 图执行）+ OpportunityToPlanFlow（Session 持久化）+ EventBus（SSE 实时推送）。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from apps.content_planning.adapters.intel_hub_adapter import IntelHubAdapter
from apps.content_planning.agents.base import AgentContext, AgentResult
from apps.content_planning.agents.graph_executor import GraphExecutor
from apps.content_planning.agents.plan_graph import PlanGraph, build_agent_pipeline_graph
from apps.content_planning.gateway.event_bus import ObjectEvent, event_bus

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger.setLevel(logging.DEBUG)

_ROLE_LABELS: dict[str, str] = {
    "trend_analyst": "趋势分析",
    "brief_synthesizer": "Brief 编译",
    "template_planner": "模板匹配",
    "strategy_director": "策略生成",
    "plan_compiler": "计划编译",
    "visual_director": "视觉规划",
    "asset_producer": "资产组装",
}


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineRun:
    run_id: str = ""
    opportunity_id: str = ""
    graph_id: str = ""
    status: PipelineStatus = PipelineStatus.PENDING
    graph: PlanGraph | None = None
    results: dict[str, AgentResult] = field(default_factory=dict)
    context: AgentContext | None = None
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""
    _task: asyncio.Task | None = field(default=None, repr=False)

    def summary(self) -> dict[str, Any]:
        gs = self.graph.summary() if self.graph else {}
        elapsed = (self.finished_at or time.time()) - self.started_at if self.started_at else 0
        return {
            "run_id": self.run_id,
            "opportunity_id": self.opportunity_id,
            "graph_id": self.graph_id,
            "status": self.status.value,
            "graph_summary": gs,
            "elapsed_ms": int(elapsed * 1000),
            "error": self.error,
        }


class AgentPipelineRunner:
    """一键策划全链路编排器。"""

    def __init__(
        self,
        adapter: IntelHubAdapter | None = None,
        plan_store: Any | None = None,
        platform_store: Any | None = None,
    ) -> None:
        self._adapter = adapter or IntelHubAdapter()
        self._executor = GraphExecutor()
        self._plan_store = plan_store
        self._platform_store = platform_store
        self._runs: dict[str, PipelineRun] = {}

    async def trigger(
        self,
        opportunity_id: str,
        *,
        skip_stages: list[str] | None = None,
        execution_mode: str = "deep",
    ) -> PipelineRun:
        existing = self._runs.get(opportunity_id)
        if existing and existing.status == PipelineStatus.RUNNING:
            return existing

        run_id = uuid.uuid4().hex[:16]
        graph = build_agent_pipeline_graph(opportunity_id)

        if skip_stages:
            for nid, node in list(graph.nodes.items()):
                if node.agent_role in skip_stages:
                    graph.mark_completed(nid, {"skipped": True})

        context = self._build_context(opportunity_id, execution_mode=execution_mode)

        run = PipelineRun(
            run_id=run_id,
            opportunity_id=opportunity_id,
            graph_id=graph.graph_id,
            graph=graph,
            context=context,
        )
        self._runs[opportunity_id] = run

        logger.info("[Pipeline] TRIGGERED run=%s opp=%s nodes=%d",
                     run_id, opportunity_id, len(graph.nodes))

        run._task = asyncio.create_task(self._execute_safe(run))
        return run

    async def _execute_safe(self, run: PipelineRun) -> None:
        """Wrapper to guarantee exceptions are always logged."""
        try:
            await self._execute(run)
        except Exception:
            logger.exception("[Pipeline] UNHANDLED_EXCEPTION in _execute for run=%s", run.run_id)

    async def get_status(self, opportunity_id: str) -> dict[str, Any] | None:
        run = self._runs.get(opportunity_id)
        if run is None:
            return None
        s = run.summary()
        if run.graph:
            s["nodes"] = {
                nid: {
                    "agent_role": n.agent_role,
                    "label": _ROLE_LABELS.get(n.agent_role, n.agent_role),
                    "status": n.status.value,
                    "started_at": n.started_at.isoformat() if n.started_at else None,
                    "completed_at": n.completed_at.isoformat() if n.completed_at else None,
                    "error": n.error,
                }
                for nid, n in run.graph.nodes.items()
            }
        return s

    async def cancel(self, opportunity_id: str) -> bool:
        run = self._runs.get(opportunity_id)
        if run is None or run.status != PipelineStatus.RUNNING:
            return False
        if run._task and not run._task.done():
            run._task.cancel()
        run.status = PipelineStatus.CANCELLED
        run.finished_at = time.time()
        await self._emit(opportunity_id, "agent_pipeline_cancelled", {"run_id": run.run_id})
        return True

    def _build_context(self, opportunity_id: str, *, execution_mode: str = "deep") -> AgentContext:
        card = self._adapter.get_card(opportunity_id)
        source_notes: list[Any] = []
        review_summary: dict[str, Any] = {}

        if card:
            note_ids = getattr(card, "source_note_ids", []) or []
            if note_ids:
                source_notes = self._adapter.get_source_notes(note_ids)
            review_summary = self._adapter.get_review_summary(opportunity_id)

        template = None
        try:
            from apps.template_extraction.agent import TemplateRetriever
            retriever = TemplateRetriever()
            templates = retriever.list_templates()
            if templates:
                template = templates[0]
        except Exception:
            logger.debug("Template retrieval failed", exc_info=True)

        return AgentContext(
            opportunity_id=opportunity_id,
            source_notes=source_notes,
            review_summary=review_summary,
            template=template,
            extra={
                "card": card,
                "execution_mode": execution_mode,
            },
        )

    async def _execute(self, run: PipelineRun) -> None:
        run.status = PipelineStatus.RUNNING
        run.started_at = time.time()
        logger.info("[Pipeline] EXECUTE_START run=%s opp=%s", run.run_id, run.opportunity_id)

        await self._emit(run.opportunity_id, "agent_pipeline_started", {
            "run_id": run.run_id,
            "graph_id": run.graph_id,
            "nodes": [
                {"node_id": n.node_id, "agent_role": n.agent_role, "label": _ROLE_LABELS.get(n.agent_role, n.agent_role)}
                for n in run.graph.nodes.values()
            ],
        })
        await asyncio.sleep(0.3)

        try:
            results = await self._executor.execute(
                run.graph,
                run.context,
                on_node_start=lambda nid, role, data: self._emit(
                    run.opportunity_id, "agent_node_started",
                    {"run_id": run.run_id, "node_id": nid, "agent_role": role, "label": _ROLE_LABELS.get(role, role), **data},
                ),
                on_node_complete=lambda nid, role, data: self._on_node_complete(run, nid, role, data),
                on_node_fail=lambda nid, role, data: self._emit(
                    run.opportunity_id, "agent_node_failed",
                    {"run_id": run.run_id, "node_id": nid, "agent_role": role, "label": _ROLE_LABELS.get(role, role), **data},
                ),
            )
            run.results = results
            run.status = PipelineStatus(run.graph.status) if run.graph else PipelineStatus.COMPLETED

            self._persist_to_session(run)

            elapsed_ms = int((time.time() - run.started_at) * 1000)
            gs = run.graph.summary() if run.graph else {}
            logger.info("[Pipeline] EXECUTE_DONE run=%s status=%s elapsed=%dms completed=%d failed=%d",
                         run.run_id, run.status.value, elapsed_ms,
                         gs.get("completed", 0), gs.get("failed", 0))

            asset_bundle_id = ""
            if run.context and run.context.asset_bundle:
                asset_bundle_id = getattr(run.context.asset_bundle, "bundle_id", "")

            await self._emit(run.opportunity_id, "agent_pipeline_completed", {
                "run_id": run.run_id,
                "graph_summary": gs,
                "asset_bundle_id": asset_bundle_id,
                "status": run.status.value,
            })

        except asyncio.CancelledError:
            run.status = PipelineStatus.CANCELLED
            logger.info("[Pipeline] CANCELLED run=%s opp=%s", run.run_id, run.opportunity_id)
        except Exception as exc:
            run.status = PipelineStatus.FAILED
            run.error = str(exc)
            logger.error("[Pipeline] EXECUTE_FAIL run=%s opp=%s error=%s",
                          run.run_id, run.opportunity_id, exc, exc_info=True)
            await self._emit(run.opportunity_id, "agent_pipeline_failed", {
                "run_id": run.run_id,
                "error": str(exc),
            })
        finally:
            run.finished_at = time.time()

    async def _on_node_complete(self, run: PipelineRun, node_id: str, agent_role: str, data: dict[str, Any]) -> None:
        logger.info("[Pipeline] NODE_DONE run=%s node=%s role=%s dur=%dms conf=%.2f expl=%.60s",
                     run.run_id, node_id, agent_role,
                     data.get("duration_ms", 0), data.get("confidence", 0),
                     data.get("explanation", "")[:60])
        self._update_lifecycle(run, agent_role)
        self._persist_stage(run, agent_role)

        await self._emit(run.opportunity_id, "agent_node_completed", {
            "run_id": run.run_id,
            "node_id": node_id,
            "agent_role": agent_role,
            "label": _ROLE_LABELS.get(agent_role, agent_role),
            **data,
        })

    def _update_lifecycle(self, run: PipelineRun, agent_role: str) -> None:
        ctx = run.context
        if ctx is None:
            return
        if agent_role == "brief_synthesizer" and ctx.brief:
            if hasattr(ctx.brief, "lifecycle_status"):
                ctx.brief.lifecycle_status = "in_planning"
        elif agent_role == "strategy_director" and ctx.strategy:
            if hasattr(ctx.strategy, "lifecycle_status"):
                ctx.strategy.lifecycle_status = "in_planning"
        elif agent_role == "plan_compiler" and ctx.plan:
            if hasattr(ctx.plan, "lifecycle_status"):
                ctx.plan.lifecycle_status = "in_planning"
        elif agent_role == "asset_producer" and ctx.asset_bundle:
            if hasattr(ctx.asset_bundle, "lifecycle_status"):
                ctx.asset_bundle.lifecycle_status = "ready"

    def _persist_stage(self, run: PipelineRun, agent_role: str) -> None:
        if self._plan_store is None or run.context is None:
            return
        ctx = run.context
        opp_id = run.opportunity_id
        try:
            self._plan_store.save_session(
                opp_id,
                session_status="agent_pipeline",
                brief=ctx.brief,
                match_result=ctx.match_result,
                strategy=ctx.strategy,
                plan=ctx.plan,
                image_briefs=ctx.image_briefs,
                asset_bundle=ctx.asset_bundle,
                pipeline_run_id=run.run_id,
            )
        except Exception:
            logger.debug("Persist stage %s failed for %s", agent_role, opp_id, exc_info=True)

    def _persist_to_session(self, run: PipelineRun) -> None:
        if self._plan_store is None or run.context is None:
            return
        ctx = run.context
        status = "ready" if run.status == PipelineStatus.COMPLETED else "partial"
        try:
            self._plan_store.save_session(
                run.opportunity_id,
                session_status=status,
                brief=ctx.brief,
                match_result=ctx.match_result,
                strategy=ctx.strategy,
                plan=ctx.plan,
                image_briefs=ctx.image_briefs,
                asset_bundle=ctx.asset_bundle,
                pipeline_run_id=run.run_id,
            )
        except Exception:
            logger.debug("Final persist failed for %s", run.opportunity_id, exc_info=True)

    async def _emit(self, opportunity_id: str, event_type: str, payload: dict[str, Any]) -> None:
        await event_bus.publish(ObjectEvent(
            event_type=event_type,
            opportunity_id=opportunity_id,
            object_type="agent_pipeline",
            payload=payload,
        ))

    async def trigger_batch(
        self,
        opportunity_ids: list[str],
        *,
        execution_mode: str = "deep",
    ) -> dict[str, PipelineRun]:
        runs: dict[str, PipelineRun] = {}
        for opp_id in opportunity_ids:
            run = await self.trigger(opp_id, execution_mode=execution_mode)
            runs[opp_id] = run
        return runs

    async def get_batch_status(self, opportunity_ids: list[str]) -> dict[str, Any]:
        statuses = {}
        for opp_id in opportunity_ids:
            status = await self.get_status(opp_id)
            if status:
                statuses[opp_id] = status
        return statuses
