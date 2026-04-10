"""PlanGraph 执行引擎 v2：条件分支 + checkpoint + 中间件集成。"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Awaitable

from apps.content_planning.agents.base import AgentContext, AgentResult, BaseAgent
from apps.content_planning.agents.plan_graph import GraphEdge, GraphNode, NodeStatus, PlanGraph

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger.setLevel(logging.DEBUG)

NodeCallback = Callable[[str, str, dict[str, Any]], Awaitable[None] | None]


class GraphCheckpointer:
    """SQLite-based checkpoint for graph execution state."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else Path("data/graph_checkpoints.sqlite")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    graph_id TEXT NOT NULL,
                    opportunity_id TEXT NOT NULL,
                    graph_json TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    results_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    status TEXT NOT NULL DEFAULT 'active'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cp_graph ON checkpoints(graph_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cp_opp ON checkpoints(opportunity_id)")

    def save(self, graph: PlanGraph, context: AgentContext, results: dict[str, AgentResult]) -> str:
        import uuid
        cp_id = uuid.uuid4().hex[:16]
        results_data = {k: v.model_dump(mode="json") for k, v in results.items()}
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO checkpoints (checkpoint_id, graph_id, opportunity_id, graph_json, context_json, results_json) VALUES (?, ?, ?, ?, ?, ?)",
                (cp_id, graph.graph_id, graph.opportunity_id,
                 graph.model_dump_json(), context.model_dump_json(),
                 json.dumps(results_data, ensure_ascii=False)),
            )
        return cp_id

    def load(self, checkpoint_id: str) -> tuple[PlanGraph, AgentContext, dict[str, AgentResult]] | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)).fetchone()
        if row is None:
            return None
        graph = PlanGraph.model_validate_json(row["graph_json"])
        context = AgentContext.model_validate_json(row["context_json"])
        results_data = json.loads(row["results_json"])
        results = {k: AgentResult.model_validate(v) for k, v in results_data.items()}
        return graph, context, results

    def load_latest(self, opportunity_id: str) -> tuple[PlanGraph, AgentContext, dict[str, AgentResult]] | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE opportunity_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                (opportunity_id,),
            ).fetchone()
        if row is None:
            return None
        graph = PlanGraph.model_validate_json(row["graph_json"])
        context = AgentContext.model_validate_json(row["context_json"])
        results_data = json.loads(row["results_json"])
        results = {k: AgentResult.model_validate(v) for k, v in results_data.items()}
        return graph, context, results


class GraphExecutor:
    """Execute a PlanGraph with condition evaluation, callbacks, and checkpointing."""

    def __init__(self, *, checkpointer: GraphCheckpointer | None = None) -> None:
        self._agent_factory: dict[str, type[BaseAgent]] = {}
        self._checkpointer = checkpointer
        self._middleware_chain = None
        self._load_agent_classes()

    def set_middleware_chain(self, chain: Any) -> None:
        self._middleware_chain = chain

    def _load_agent_classes(self) -> None:
        try:
            from apps.content_planning.agents.trend_analyst import TrendAnalystAgent
            from apps.content_planning.agents.brief_synthesizer import BriefSynthesizerAgent
            from apps.content_planning.agents.template_planner import TemplatePlannerAgent
            from apps.content_planning.agents.strategy_director import StrategyDirectorAgent
            from apps.content_planning.agents.visual_director import VisualDirectorAgent
            from apps.content_planning.agents.asset_producer import AssetProducerAgent
            from apps.content_planning.agents.plan_compiler import PlanCompilerAgent
            self._agent_factory = {
                "trend_analyst": TrendAnalystAgent,
                "brief_synthesizer": BriefSynthesizerAgent,
                "template_planner": TemplatePlannerAgent,
                "strategy_director": StrategyDirectorAgent,
                "plan_compiler": PlanCompilerAgent,
                "visual_director": VisualDirectorAgent,
                "asset_producer": AssetProducerAgent,
            }
        except ImportError:
            logger.warning("Some agent classes not importable for GraphExecutor")

    async def execute(
        self,
        graph: PlanGraph,
        context: AgentContext,
        *,
        on_node_start: NodeCallback | None = None,
        on_node_complete: NodeCallback | None = None,
        on_node_fail: NodeCallback | None = None,
    ) -> dict[str, AgentResult]:
        """Execute all nodes in the graph respecting dependencies and conditions."""
        results: dict[str, AgentResult] = {}
        max_iterations = len(graph.nodes) + 2

        for round_i in range(max_iterations):
            if graph.is_complete():
                break
            ready = graph.ready_nodes()
            completed_count = sum(1 for n in graph.nodes.values() if n.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED))
            logger.info("[Executor] ROUND=%d ready=%d completed=%d total=%d",
                         round_i, len(ready), completed_count, len(graph.nodes))
            if not ready:
                remaining = [n for n in graph.nodes.values() if n.status == NodeStatus.PENDING]
                if remaining:
                    for n in remaining:
                        if self._should_skip_by_condition(graph, n, context):
                            graph.mark_completed(n.node_id, {"skipped_by_condition": True})
                            n.status = NodeStatus.SKIPPED
                        else:
                            graph.mark_failed(n.node_id, "Deadlock: dependencies not met")
                            await self._fire(on_node_fail, n.node_id, n.agent_role, {"error": "Deadlock"})
                break

            for node in ready:
                if self._should_skip_by_condition(graph, node, context):
                    graph.mark_completed(node.node_id, {"skipped_by_condition": True})
                    node.status = NodeStatus.SKIPPED
                    continue

            ready = [n for n in ready if n.status == NodeStatus.PENDING]
            if not ready:
                continue

            tasks = [
                self._run_node(graph, node, context, results,
                               on_node_start=on_node_start,
                               on_node_complete=on_node_complete,
                               on_node_fail=on_node_fail)
                for node in ready
            ]
            node_results = await asyncio.gather(*tasks, return_exceptions=True)

            for node, result in zip(ready, node_results):
                if isinstance(result, Exception):
                    graph.mark_failed(node.node_id, str(result))
                    logger.error("Node %s (%s) failed: %s", node.node_id, node.agent_role, result)
                    await self._fire(on_node_fail, node.node_id, node.agent_role, {"error": str(result)})
                elif isinstance(result, AgentResult):
                    graph.mark_completed(node.node_id, result.model_dump(mode="json"))
                    results[node.node_id] = result
                    self._propagate_output(node.agent_role, result, context)
                else:
                    graph.mark_failed(node.node_id, "Unexpected result type")
                    await self._fire(on_node_fail, node.node_id, node.agent_role, {"error": "Unexpected result type"})

            if self._checkpointer:
                try:
                    self._checkpointer.save(graph, context, results)
                except Exception:
                    logger.debug("Checkpoint save failed", exc_info=True)

        graph.status = "completed" if graph.is_complete() else "partial"
        return results

    async def execute_from_checkpoint(
        self,
        checkpoint_id: str,
        *,
        on_node_start: NodeCallback | None = None,
        on_node_complete: NodeCallback | None = None,
        on_node_fail: NodeCallback | None = None,
    ) -> dict[str, AgentResult] | None:
        """Resume execution from a saved checkpoint."""
        if self._checkpointer is None:
            return None
        loaded = self._checkpointer.load(checkpoint_id)
        if loaded is None:
            return None
        graph, context, prior_results = loaded
        new_results = await self.execute(
            graph, context,
            on_node_start=on_node_start,
            on_node_complete=on_node_complete,
            on_node_fail=on_node_fail,
        )
        prior_results.update(new_results)
        return prior_results

    def _should_skip_by_condition(self, graph: PlanGraph, node: GraphNode, context: AgentContext) -> bool:
        """Evaluate edge conditions to determine if a node should be skipped."""
        incoming_edges = [e for e in graph.edges if e.to_node == node.node_id]
        for edge in incoming_edges:
            if not edge.condition:
                continue
            if not self._evaluate_condition(edge.condition, context):
                return True
        return False

    def _evaluate_condition(self, condition: str, context: AgentContext) -> bool:
        """Evaluate a simple condition string against context.

        Supports: 'context.{field} is not None', 'context.{field} is None',
                  'context.extra.{key} exists'
        """
        condition = condition.strip()
        if condition.startswith("context.") and condition.endswith("is not None"):
            field = condition.replace("context.", "").replace(" is not None", "").strip()
            return getattr(context, field, None) is not None
        if condition.startswith("context.") and condition.endswith("is None"):
            field = condition.replace("context.", "").replace(" is None", "").strip()
            return getattr(context, field, None) is None
        if condition.startswith("context.extra.") and condition.endswith("exists"):
            key = condition.replace("context.extra.", "").replace(" exists", "").strip()
            return key in context.extra
        return True

    async def _run_node(
        self,
        graph: PlanGraph,
        node: GraphNode,
        context: AgentContext,
        prior_results: dict[str, AgentResult],
        *,
        on_node_start: NodeCallback | None = None,
        on_node_complete: NodeCallback | None = None,
        on_node_fail: NodeCallback | None = None,
    ) -> AgentResult:
        """Run a single graph node with lifecycle callbacks and optional middleware."""
        graph.mark_running(node.node_id)
        logger.info("[Executor] NODE_START node=%s role=%s", node.node_id, node.agent_role)
        await self._fire(on_node_start, node.node_id, node.agent_role, {"task": node.task_description})

        agent_cls = self._agent_factory.get(node.agent_role)
        if agent_cls is None:
            raise ValueError(f"No agent class for role: {node.agent_role}")

        t0 = time.perf_counter()
        agent = agent_cls()

        if self._middleware_chain is not None:
            result = self._middleware_chain.execute(context, node.agent_role, agent.run)
        else:
            result = agent.run(context)

        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info("[Executor] NODE_DONE node=%s role=%s dur=%dms conf=%.2f",
                     node.node_id, node.agent_role, duration_ms, result.confidence)

        await self._fire(on_node_complete, node.node_id, node.agent_role, {
            "duration_ms": duration_ms,
            "confidence": result.confidence,
            "explanation": result.explanation[:200],
            "output_summary": self._build_output_summary(node.agent_role, result),
            "suggestions": [{"label": s.label, "action": s.action} for s in (result.suggestions or [])[:4]],
        })
        return result

    def _build_output_summary(self, agent_role: str, result: AgentResult) -> dict[str, Any]:
        """Extract key preview fields from output_object per agent role."""
        obj = result.output_object
        if obj is None:
            return {}
        try:
            if agent_role == "trend_analyst":
                return {
                    "strength_score": getattr(obj, "opportunity_strength_score", None) or 0,
                    "insight": getattr(obj, "insight_statement", "") or "",
                    "recommendation": getattr(obj, "action_recommendation", "") or "",
                    "opportunity_type": getattr(obj, "opportunity_type", "") or "",
                }
            elif agent_role == "brief_synthesizer":
                return {
                    "opportunity_title": getattr(obj, "opportunity_title", "") or "",
                    "content_goal": getattr(obj, "content_goal", "") or "",
                    "primary_value": getattr(obj, "primary_value", "") or "",
                    "planning_direction": getattr(obj, "planning_direction", "") or "",
                    "why_now": getattr(obj, "why_now", "") or "",
                }
            elif agent_role == "template_planner":
                if isinstance(obj, dict):
                    top3 = obj.get("top3", [])[:3]
                    return {
                        "top3": [
                            {"name": t.get("template_name", ""), "score": t.get("score", 0), "reason": t.get("reason", "")}
                            for t in top3
                        ],
                        "total": obj.get("total", 0),
                    }
                return {}
            elif agent_role == "strategy_director":
                return {
                    "positioning": getattr(obj, "positioning_statement", "") or "",
                    "tone": getattr(obj, "tone_of_voice", "") or "",
                    "hook": getattr(obj, "new_hook", "") or "",
                    "scenes": (getattr(obj, "scene_emphasis", None) or [])[:3],
                }
            elif agent_role == "plan_compiler":
                return {
                    "theme": getattr(obj, "theme", "") or "",
                    "target_user": getattr(obj, "target_user", "") or "",
                    "selling_point": getattr(obj, "core_selling_point", "") or "",
                    "note_goal": getattr(obj, "note_goal", "") or "",
                }
            elif agent_role == "visual_director":
                slots = getattr(obj, "slot_briefs", None) or []
                mode = getattr(obj, "mode", "") or ""
                return {
                    "slot_count": len(slots),
                    "mode": mode,
                    "slots_preview": [
                        {"role": getattr(s, "role", ""), "subject": getattr(s, "subject", "")}
                        for s in slots[:3]
                    ],
                }
            elif agent_role == "asset_producer":
                titles = getattr(obj, "title_candidates", None) or []
                body = getattr(obj, "body_draft", "") or ""
                return {
                    "title_count": len(titles),
                    "body_length": len(body),
                    "export_status": getattr(obj, "export_status", "") or "",
                }
        except Exception:
            logger.debug("Failed to build output_summary for %s", agent_role, exc_info=True)
        return {}

    def _propagate_output(self, agent_role: str, result: AgentResult, context: AgentContext) -> None:
        """Propagate node output to context for downstream nodes."""
        obj = result.output_object
        if obj is None:
            return
        if agent_role == "trend_analyst":
            context.extra["card_analysis"] = obj
        elif agent_role == "brief_synthesizer":
            context.brief = obj
        elif agent_role == "template_planner":
            if isinstance(obj, dict):
                try:
                    from apps.content_planning.schemas.template_match_result import (
                        TemplateMatchEntry,
                        TemplateMatchResult,
                    )
                    top3 = obj.get("top3", [])
                    entries = [TemplateMatchEntry(**e) for e in top3] if top3 else []
                    match_obj = TemplateMatchResult(
                        opportunity_id=context.opportunity_id,
                        brief_id=getattr(context.brief, "brief_id", "") if context.brief else "",
                        primary_template=entries[0] if entries else TemplateMatchEntry(),
                        secondary_templates=entries[1:] if len(entries) > 1 else [],
                    )
                    context.match_result = match_obj
                except Exception:
                    logger.debug("Failed to convert match_result dict to TemplateMatchResult", exc_info=True)
                    context.match_result = obj
            else:
                context.match_result = obj
            if context.template is None and isinstance(obj, dict):
                top3 = obj.get("top3", [])
                if top3:
                    try:
                        from apps.template_extraction.agent import TemplateRetriever
                        tpl_id = top3[0].get("template_id", "")
                        if tpl_id:
                            retriever = TemplateRetriever()
                            for t in retriever.list_templates():
                                if getattr(t, "template_id", "") == tpl_id:
                                    context.template = t
                                    break
                    except Exception:
                        logger.debug("Auto-select template from match_result failed", exc_info=True)
        elif agent_role == "strategy_director":
            context.strategy = obj
        elif agent_role == "plan_compiler":
            context.plan = obj
        elif agent_role == "visual_director":
            context.image_briefs = obj
        elif agent_role == "asset_producer":
            context.asset_bundle = obj

        context.artifacts.append({
            "agent_role": agent_role,
            "type": type(obj).__name__ if obj else "None",
            "timestamp": time.time(),
        })

    async def _fire(
        self,
        callback: NodeCallback | None,
        node_id: str,
        agent_role: str,
        data: dict[str, Any],
    ) -> None:
        if callback is None:
            return
        try:
            ret = callback(node_id, agent_role, data)
            if asyncio.iscoroutine(ret):
                await ret
        except Exception:
            logger.debug("Callback error for node %s", node_id, exc_info=True)

    def execute_sync(self, graph: PlanGraph, context: AgentContext) -> dict[str, AgentResult]:
        """Synchronous wrapper for execute()."""
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.execute(graph, context))
                return future.result()
        except RuntimeError:
            return asyncio.run(self.execute(graph, context))
