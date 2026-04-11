"""Plan Graph：LangGraph 风格的状态图编排，定义 Agent 间的依赖关系与执行顺序。

借鉴 DeerFlow 的 Plan Graph 概念：Lead Agent 分解任务为节点，
节点之间通过数据依赖边连接，支持条件分支和并行执行。
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class GraphNode(BaseModel):
    """状态图中的单个节点，对应一个 Agent 任务。"""
    node_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    agent_role: str = ""
    task_description: str = ""
    status: NodeStatus = NodeStatus.PENDING
    dependencies: list[str] = Field(default_factory=list)
    output: Any | None = None
    error: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def is_ready(self, completed_nodes: set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_nodes for dep in self.dependencies)


class GraphEdge(BaseModel):
    """节点间的依赖边。"""
    from_node: str
    to_node: str
    condition: str = ""
    data_key: str = ""


class PlanGraph(BaseModel):
    """Agent 编排状态图。"""
    graph_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    nodes: dict[str, GraphNode] = Field(default_factory=dict)
    edges: list[GraphEdge] = Field(default_factory=list)
    status: str = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_node(self, agent_role: str, task: str = "", dependencies: list[str] | None = None) -> GraphNode:
        node = GraphNode(
            agent_role=agent_role,
            task_description=task,
            dependencies=dependencies or [],
        )
        self.nodes[node.node_id] = node
        return node

    def add_edge(self, from_id: str, to_id: str, condition: str = "", data_key: str = "") -> GraphEdge:
        edge = GraphEdge(from_node=from_id, to_node=to_id, condition=condition, data_key=data_key)
        self.edges.append(edge)
        if to_id in self.nodes and from_id not in self.nodes[to_id].dependencies:
            self.nodes[to_id].dependencies.append(from_id)
        return edge

    def ready_nodes(self) -> list[GraphNode]:
        """Get nodes that are ready to execute (all deps completed)."""
        completed = {nid for nid, n in self.nodes.items() if n.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)}
        return [
            n for n in self.nodes.values()
            if n.status == NodeStatus.PENDING and n.is_ready(completed)
        ]

    def mark_running(self, node_id: str) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].status = NodeStatus.RUNNING
            self.nodes[node_id].started_at = datetime.now(UTC)

    def mark_completed(self, node_id: str, output: Any = None) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].status = NodeStatus.COMPLETED
            self.nodes[node_id].output = output
            self.nodes[node_id].completed_at = datetime.now(UTC)

    def mark_failed(self, node_id: str, error: str = "") -> None:
        if node_id in self.nodes:
            self.nodes[node_id].status = NodeStatus.FAILED
            self.nodes[node_id].error = error
            self.nodes[node_id].completed_at = datetime.now(UTC)

    def is_complete(self) -> bool:
        return all(
            n.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED, NodeStatus.FAILED)
            for n in self.nodes.values()
        )

    def summary(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "status": self.status,
            "total": len(self.nodes),
            "completed": sum(1 for n in self.nodes.values() if n.status == NodeStatus.COMPLETED),
            "failed": sum(1 for n in self.nodes.values() if n.status == NodeStatus.FAILED),
            "pending": sum(1 for n in self.nodes.values() if n.status == NodeStatus.PENDING),
            "running": sum(1 for n in self.nodes.values() if n.status == NodeStatus.RUNNING),
        }


def build_default_graph(opportunity_id: str) -> PlanGraph:
    """Build the default content planning graph (standard pipeline)."""
    g = PlanGraph(opportunity_id=opportunity_id, status="ready")

    n_trend = g.add_node("trend_analyst", "分析机会与趋势")
    n_brief = g.add_node("brief_synthesizer", "编译 OpportunityBrief", [n_trend.node_id])
    n_template = g.add_node("template_planner", "匹配最佳模板", [n_brief.node_id])
    n_strategy = g.add_node("strategy_director", "生成改写策略", [n_template.node_id])
    n_visual = g.add_node("visual_director", "规划视觉方向", [n_strategy.node_id])
    n_asset = g.add_node("asset_producer", "组装资产包", [n_visual.node_id])

    g.add_edge(n_trend.node_id, n_brief.node_id, data_key="card_analysis")
    g.add_edge(n_brief.node_id, n_template.node_id, data_key="brief")
    g.add_edge(n_template.node_id, n_strategy.node_id, data_key="match_result")
    g.add_edge(n_strategy.node_id, n_visual.node_id, data_key="strategy")
    g.add_edge(n_visual.node_id, n_asset.node_id, data_key="image_briefs")

    return g


# ── Workspace-specific subgraphs (DeerFlow-style) ──

def build_opportunity_subgraph(opportunity_id: str) -> PlanGraph:
    """Opportunity workspace: evaluate → sanity check → promote decision."""
    g = PlanGraph(opportunity_id=opportunity_id, status="ready")
    n_eval = g.add_node("trend_analyst", "评估机会质量与时机")
    n_sanity = g.add_node("risk_assessor", "风险与证据完整性检查", [n_eval.node_id])
    n_decision = g.add_node("lead_agent", "推进决策建议", [n_sanity.node_id])
    g.add_edge(n_eval.node_id, n_sanity.node_id, data_key="card_analysis")
    g.add_edge(n_sanity.node_id, n_decision.node_id, data_key="sanity_result")
    return g


def build_planning_subgraph(opportunity_id: str) -> PlanGraph:
    """Planning workspace: brief → templates → strategy → evaluate strategy."""
    g = PlanGraph(opportunity_id=opportunity_id, status="ready")
    n_brief = g.add_node("brief_synthesizer", "编译 OpportunityBrief")
    n_tpl = g.add_node("template_planner", "匹配最佳模板", [n_brief.node_id])
    n_strategy = g.add_node("strategy_director", "生成改写策略", [n_tpl.node_id])
    n_eval = g.add_node("health_checker", "策略健康度检查", [n_strategy.node_id])
    g.add_edge(n_brief.node_id, n_tpl.node_id, data_key="brief")
    g.add_edge(n_tpl.node_id, n_strategy.node_id, data_key="match_result")
    g.add_edge(n_strategy.node_id, n_eval.node_id, data_key="strategy")
    return g


def build_creation_subgraph(opportunity_id: str) -> PlanGraph:
    """Creation workspace: plan → titles → body → image briefs → consistency check."""
    g = PlanGraph(opportunity_id=opportunity_id, status="ready")
    n_plan = g.add_node("plan_compiler", "编译内容计划")
    n_title = g.add_node("brief_synthesizer", "生成标题候选", [n_plan.node_id])
    n_body = g.add_node("strategy_director", "生成正文草稿", [n_title.node_id])
    n_image = g.add_node("visual_director", "规划图位", [n_body.node_id])
    n_check = g.add_node("health_checker", "计划一致性检查", [n_image.node_id])
    g.add_edge(n_plan.node_id, n_title.node_id, data_key="plan")
    g.add_edge(n_title.node_id, n_body.node_id, data_key="titles")
    g.add_edge(n_body.node_id, n_image.node_id, data_key="body")
    g.add_edge(n_image.node_id, n_check.node_id, data_key="image_briefs")
    return g


def build_asset_subgraph(opportunity_id: str) -> PlanGraph:
    """Asset workspace: assemble bundle → generate variants → judge → export."""
    g = PlanGraph(opportunity_id=opportunity_id, status="ready")
    n_bundle = g.add_node("asset_producer", "组装资产包")
    n_variant = g.add_node("asset_producer", "生成变体集", [n_bundle.node_id])
    n_judge = g.add_node("judge_agent", "评估资产质量", [n_variant.node_id])
    n_export = g.add_node("asset_producer", "导出资产包", [n_judge.node_id])
    g.add_edge(n_bundle.node_id, n_variant.node_id, data_key="asset_bundle")
    g.add_edge(n_variant.node_id, n_judge.node_id, data_key="variants")
    g.add_edge(n_judge.node_id, n_export.node_id, data_key="judge_result")
    return g


WORKSPACE_GRAPH_BUILDERS = {
    "opportunity": build_opportunity_subgraph,
    "planning": build_planning_subgraph,
    "creation": build_creation_subgraph,
    "asset": build_asset_subgraph,
}


def build_agent_pipeline_graph(opportunity_id: str) -> PlanGraph:
    """Build the full agent pipeline graph with plan compilation step."""
    g = PlanGraph(opportunity_id=opportunity_id, status="ready")

    n_trend = g.add_node("trend_analyst", "分析机会与趋势")
    n_brief = g.add_node("brief_synthesizer", "编译 OpportunityBrief", [n_trend.node_id])
    n_template = g.add_node("template_planner", "匹配最佳模板", [n_brief.node_id])
    n_strategy = g.add_node("strategy_director", "生成改写策略", [n_template.node_id])
    n_plan = g.add_node("plan_compiler", "编译内容计划", [n_strategy.node_id])
    n_visual = g.add_node("visual_director", "规划视觉方向", [n_plan.node_id])
    n_asset = g.add_node("asset_producer", "组装资产包", [n_visual.node_id])

    g.add_edge(n_trend.node_id, n_brief.node_id, data_key="card_analysis")
    g.add_edge(n_brief.node_id, n_template.node_id, data_key="brief")
    g.add_edge(n_template.node_id, n_strategy.node_id, data_key="match_result")
    g.add_edge(n_strategy.node_id, n_plan.node_id, data_key="strategy")
    g.add_edge(n_plan.node_id, n_visual.node_id, data_key="plan")
    g.add_edge(n_visual.node_id, n_asset.node_id, data_key="image_briefs")

    return g
