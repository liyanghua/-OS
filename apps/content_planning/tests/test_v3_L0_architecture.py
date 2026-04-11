"""L0：Hermes 记忆/技能、DeerFlow 图编排、分层导入与无环依赖。"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from apps.content_planning.agents.base import AgentContext, AgentResult
from apps.content_planning.agents.graph_executor import GraphExecutor
from apps.content_planning.agents.memory import AgentMemory, MemoryEntry
from apps.content_planning.agents.plan_graph import (
    PlanGraph,
    WORKSPACE_GRAPH_BUILDERS,
    build_asset_subgraph,
    build_creation_subgraph,
    build_opportunity_subgraph,
    build_planning_subgraph,
    NodeStatus,
)
from apps.content_planning.agents.skill_registry import SkillDefinition, SkillRegistry, skill_registry
from apps.content_planning.services.agent_pipeline_runner import (
    AgentPipelineRunner,
    PipelineRun,
    PipelineStatus,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_agent_memory_init_store_recall_in_memory(tmp_path: Path):
    # 注意：SQLite :memory: 每连接一个独立库；AgentMemory 每次操作新连接，故用临时文件测 store/recall
    mem = AgentMemory(db_path=str(tmp_path / "mem.sqlite"))
    entry = MemoryEntry(
        opportunity_id="opp-1",
        session_id="s1",
        category="lesson",
        content="remember this phrase for recall",
        source_agent="test_agent",
        relevance_score=0.9,
        tags=["t1"],
    )
    mem.store(entry)
    assert entry.memory_id
    rows = mem.recall(opportunity_id="opp-1", limit=10)
    assert len(rows) == 1
    assert rows[0].content == "remember this phrase for recall"
    assert rows[0].session_id == "s1"


def test_agent_memory_init_store_recall_tempfile(tmp_path: Path):
    db = tmp_path / "agent_mem.sqlite"
    mem = AgentMemory(db_path=str(db))
    mem.store(
        MemoryEntry(
            opportunity_id="opp-tmp",
            category="note",
            content="tempfile db entry",
            source_agent="test",
        )
    )
    again = AgentMemory(db_path=str(db))
    hits = again.recall(opportunity_id="opp-tmp")
    assert len(hits) == 1
    assert hits[0].content == "tempfile db entry"


def test_skill_registry_load_defaults_at_least_ten_with_executable_steps():
    reg = SkillRegistry()
    reg.reset()
    n = reg.load_defaults()
    assert n >= 10
    skills = reg.list_skills(enabled_only=True)
    assert len(skills) >= 10
    for s in skills:
        assert isinstance(s, SkillDefinition)
        assert s.executable_steps, f"skill {s.skill_id} missing executable_steps"


def test_cross_session_memory_query(tmp_path: Path):
    mem = AgentMemory(db_path=str(tmp_path / "cross.sqlite"))
    mem.store(
        MemoryEntry(
            opportunity_id="opp-x",
            session_id="session-alpha",
            category="x",
            content="cross session unique token alpha-beta",
            source_agent="a1",
        )
    )
    mem.store(
        MemoryEntry(
            opportunity_id="opp-x",
            session_id="session-beta",
            category="x",
            content="another row for beta",
            source_agent="a2",
        )
    )
    # 不按 session 过滤时应能取到跨会话条目
    all_opp = mem.recall(opportunity_id="opp-x", limit=20)
    assert len(all_opp) >= 2
    # search_sessions 要求 session 非空
    found = mem.search_sessions("cross session unique", limit=5)
    assert any("cross session unique" in e.content for e in found)


def test_memory_miss_returns_empty_list_gracefully(tmp_path: Path):
    mem = AgentMemory(db_path=str(tmp_path / "miss.sqlite"))
    assert mem.search("zzzznonexistenttoken99999xyz") == []
    assert mem.recall(opportunity_id="no-such-opp", limit=5) == []
    assert mem.search_for_opportunity("opp", "x") == []  # 查询过短


@pytest.mark.parametrize(
    "builder",
    [
        build_opportunity_subgraph,
        build_planning_subgraph,
        build_creation_subgraph,
        build_asset_subgraph,
    ],
)
def test_workspace_subgraph_builders_produce_valid_plan_graph(builder):
    g = builder("opp-ws-1")
    assert isinstance(g, PlanGraph)
    assert g.opportunity_id == "opp-ws-1"
    assert g.nodes
    assert g.edges
    for e in g.edges:
        assert e.from_node in g.nodes
        assert e.to_node in g.nodes


def test_workspace_graph_builders_registry():
    assert set(WORKSPACE_GRAPH_BUILDERS.keys()) == {"opportunity", "planning", "creation", "asset"}
    for name, fn in WORKSPACE_GRAPH_BUILDERS.items():
        g = fn("opp-reg")
        assert isinstance(g, PlanGraph)
        assert g.opportunity_id == "opp-reg"


def test_graph_executor_execute_subgraph_with_mocked_node_run():
    executor = GraphExecutor()
    g = build_planning_subgraph("opp-exec")
    start_id = next(iter(g.nodes.keys()))

    async def _fake_run_node(self, graph, node, context, prior_results, **kwargs):
        return AgentResult(agent_role=node.agent_role, confidence=1.0, explanation="mock")

    with patch.object(GraphExecutor, "_run_node", _fake_run_node):
        ctx = AgentContext(opportunity_id="opp-exec")
        results = asyncio.run(
            executor.execute_subgraph(g, start_id, ctx),
        )
    assert isinstance(results, dict)
    assert g.is_complete()
    assert all(n.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED) for n in g.nodes.values())


def test_graph_failed_node_exposes_error_info():
    g = build_opportunity_subgraph("opp-fail")
    any_id = next(iter(g.nodes.keys()))
    g.mark_failed(any_id, "simulated failure for test")
    node = g.nodes[any_id]
    assert node.status == NodeStatus.FAILED
    assert node.error == "simulated failure for test"


async def _rerun_setup_runner() -> tuple[AgentPipelineRunner, str, str]:
    runner = AgentPipelineRunner()
    opp = "opp-rerun"
    g = build_planning_subgraph(opp)
    for nid, n in g.nodes.items():
        g.mark_completed(nid, {"done": True})
    ctx = AgentContext(opportunity_id=opp)
    run = PipelineRun(
        run_id="run-1",
        opportunity_id=opp,
        graph_id=g.graph_id,
        status=PipelineStatus.COMPLETED,
        graph=g,
        context=ctx,
    )
    runner._runs[opp] = run
    target_nid = next(iter(g.nodes.keys()))
    return runner, opp, target_nid


def test_agent_pipeline_runner_rerun_from_node_locates_correct_node():
    async def _body():
        runner, opp, target_nid = await _rerun_setup_runner()
        with patch.object(runner, "_execute_safe", new_callable=AsyncMock):
            bad = await runner.rerun_from_node(opp, "no-such-node")
            assert bad is None
            ok = await runner.rerun_from_node(opp, target_nid)
            assert ok is not None
            assert ok.graph is not None
            assert ok.graph.nodes[target_nid].status == NodeStatus.PENDING

    asyncio.run(_body())


def test_hermes_layer_classes_importable():
    from apps.content_planning.agents import memory as memory_mod
    from apps.content_planning.agents import review_loop as review_mod
    from apps.content_planning.agents import skill_registry as skill_mod

    assert memory_mod.AgentMemory is AgentMemory
    assert skill_mod.SkillRegistry is SkillRegistry
    assert hasattr(review_mod, "PerformanceFeedback")


def test_deerflow_layer_classes_importable():
    from apps.content_planning.agents import graph_executor as ge_mod
    from apps.content_planning.agents import plan_graph as pg_mod

    assert pg_mod.PlanGraph is PlanGraph
    assert ge_mod.GraphExecutor is GraphExecutor


def test_product_layer_schema_classes_importable():
    from apps.content_planning.schemas.asset_bundle import AssetBundle
    from apps.content_planning.schemas.export_package import ExportPackage
    from apps.content_planning.schemas.lineage import PlanLineage

    assert AssetBundle()
    assert ExportPackage()
    assert PlanLineage()


def test_no_circular_imports_between_layers_subprocess():
    root = _repo_root()
    code = """
import apps.content_planning.schemas.export_package
import apps.content_planning.schemas.asset_bundle
import apps.content_planning.agents.plan_graph
import apps.content_planning.agents.graph_executor
import apps.content_planning.agents.memory
import apps.content_planning.agents.skill_registry
import apps.content_planning.agents.review_loop
"""
    env = {**os.environ, "PYTHONPATH": str(root)}
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_singleton_skill_registry_has_defaults():
    assert skill_registry.list_skills(enabled_only=True)
    assert any(s.executable_steps for s in skill_registry.list_skills())
