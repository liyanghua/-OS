"""PlanGraph 执行引擎：按依赖关系编排 Agent 执行。"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from apps.content_planning.agents.base import AgentContext, AgentResult, BaseAgent
from apps.content_planning.agents.plan_graph import NodeStatus, PlanGraph

logger = logging.getLogger(__name__)


class GraphExecutor:
    """Execute a PlanGraph, respecting dependencies and supporting parallel nodes."""

    def __init__(self):
        self._agent_factory: dict[str, type[BaseAgent]] = {}
        self._load_agent_classes()

    def _load_agent_classes(self) -> None:
        try:
            from apps.content_planning.agents.trend_analyst import TrendAnalystAgent
            from apps.content_planning.agents.brief_synthesizer import BriefSynthesizerAgent
            from apps.content_planning.agents.template_planner import TemplatePlannerAgent
            from apps.content_planning.agents.strategy_director import StrategyDirectorAgent
            from apps.content_planning.agents.visual_director import VisualDirectorAgent
            from apps.content_planning.agents.asset_producer import AssetProducerAgent
            self._agent_factory = {
                "trend_analyst": TrendAnalystAgent,
                "brief_synthesizer": BriefSynthesizerAgent,
                "template_planner": TemplatePlannerAgent,
                "strategy_director": StrategyDirectorAgent,
                "visual_director": VisualDirectorAgent,
                "asset_producer": AssetProducerAgent,
            }
        except ImportError:
            logger.warning("Some agent classes not importable for GraphExecutor")

    async def execute(self, graph: PlanGraph, context: AgentContext) -> dict[str, AgentResult]:
        """Execute all nodes in the graph respecting dependencies."""
        results: dict[str, AgentResult] = {}
        max_iterations = len(graph.nodes) + 2

        for _ in range(max_iterations):
            if graph.is_complete():
                break
            ready = graph.ready_nodes()
            if not ready:
                remaining = [n for n in graph.nodes.values() if n.status == NodeStatus.PENDING]
                if remaining:
                    for n in remaining:
                        graph.mark_failed(n.node_id, "Deadlock: dependencies not met")
                break

            tasks = [self._run_node(graph, node, context, results) for node in ready]
            node_results = await asyncio.gather(*tasks, return_exceptions=True)

            for node, result in zip(ready, node_results):
                if isinstance(result, Exception):
                    graph.mark_failed(node.node_id, str(result))
                    logger.error("Node %s (%s) failed: %s", node.node_id, node.agent_role, result)
                elif isinstance(result, AgentResult):
                    graph.mark_completed(node.node_id, result.model_dump(mode="json"))
                    results[node.node_id] = result
                    self._propagate_output(node.agent_role, result, context)
                else:
                    graph.mark_failed(node.node_id, "Unexpected result type")

        graph.status = "completed" if graph.is_complete() else "partial"
        return results

    async def _run_node(self, graph: PlanGraph, node: Any, context: AgentContext,
                        prior_results: dict[str, AgentResult]) -> AgentResult:
        """Run a single graph node."""
        graph.mark_running(node.node_id)
        agent_cls = self._agent_factory.get(node.agent_role)
        if agent_cls is None:
            raise ValueError(f"No agent class for role: {node.agent_role}")
        agent = agent_cls()
        return agent.run(context)

    def _propagate_output(self, agent_role: str, result: AgentResult, context: AgentContext) -> None:
        """Propagate node output to context for downstream nodes."""
        obj = result.output_object
        if obj is None:
            return
        if agent_role == "brief_synthesizer":
            context.brief = obj
        elif agent_role == "template_planner":
            context.match_result = obj
        elif agent_role == "strategy_director":
            context.strategy = obj
        elif agent_role == "visual_director":
            context.image_briefs = obj
        elif agent_role == "asset_producer":
            context.asset_bundle = obj

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
