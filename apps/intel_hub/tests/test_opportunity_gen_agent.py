"""OpportunityGenAgent 单元测试 — stub VLM/LLM，断言事件序列与入库行为。"""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from apps.content_planning.gateway.event_bus import event_bus
from apps.intel_hub.services.agent_run_registry import AgentRunRegistry
from apps.intel_hub.services.opportunity_gen_agent import (
    OpportunityGenAgent,
    channel_for,
)


WIG_RAW_NOTE = {
    "note_id": "wig_001",
    "type": "normal",
    "title": "30+ 男士头顶发片救星 真发遮盖发缝量身定制",
    "desc": "脱发三年终于找到救星，超薄仿真头皮，戴上去自然到自己都看不出来；上班、出差、运动都不掉，发缝完全藏住，干净利落。",
    "tags": "假发,头顶发片,真发,发缝,男士假发",
    "liked_count": "1234",
    "collected_count": "200",
    "comment_count": "33",
    "share_count": "12",
    "image_list": "https://example.com/a.jpg,https://example.com/b.jpg",
    "lens_id": "wig",
    "source_keyword": "头顶发片",
}


def _make_raw_note(idx: int) -> dict[str, Any]:
    return {
        **WIG_RAW_NOTE,
        "note_id": f"wig_{idx:03d}",
        "title": f"假发笔记 {idx} · 测试用样本",
    }


def _write_jsonl_dir(base: Path, raw_notes: list[dict[str, Any]]) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    out = base / "search_contents_test.jsonl"
    out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in raw_notes),
        encoding="utf-8",
    )
    return base


class _StubReviewStore:
    """最小行为复刻：sync_cards_from_json 计数、可读 cards 数量。"""

    def __init__(self) -> None:
        self.synced_paths: list[Path] = []
        self.cards_count: int = 0

    def sync_cards_from_json(self, path: str | Path) -> int:
        self.synced_paths.append(Path(path))
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.cards_count = len(data) if isinstance(data, list) else 0
        except Exception:
            self.cards_count = 0
        return self.cards_count


class _SSECollector:
    """订阅 event_bus channel，把事件按 event_type 收集成顺序列表。"""

    def __init__(self, channel: str) -> None:
        self.channel = channel
        self.events: list[dict[str, Any]] = []
        self._task: asyncio.Task | None = None
        self._queue: asyncio.Queue | None = None

    async def __aenter__(self) -> "_SSECollector":
        self._queue = event_bus.subscribe(self.channel)
        self._task = asyncio.create_task(self._consume())
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self._queue is not None:
            event_bus.unsubscribe(self.channel, self._queue)

    async def _consume(self) -> None:
        assert self._queue is not None
        while True:
            evt = await self._queue.get()
            self.events.append(
                {"event_type": evt.event_type, "payload": evt.payload}
            )

    def types(self) -> list[str]:
        return [e["event_type"] for e in self.events]


class OpportunityGenAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_source_emits_failed_with_guidance(self) -> None:
        registry = AgentRunRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            empty_jsonl = tmpdir / "jsonl_empty"
            empty_jsonl.mkdir()
            output_dir = tmpdir / "out"

            task_id, _ = registry.start("wig", lens_label="假发")
            agent = OpportunityGenAgent(
                task_id=task_id,
                lens_id="wig",
                registry=registry,
                review_store=_StubReviewStore(),
                jsonl_dir=empty_jsonl,
                output_dir=output_dir,
            )

            async with _SSECollector(channel_for(task_id)) as col:
                await agent.run()
                # 给事件 loop 一拍把消息派发完
                await asyncio.sleep(0.05)

            self.assertIn("agent_run:started", col.types())
            self.assertIn("agent_run:failed", col.types())
            failed_payload = next(
                e["payload"] for e in col.events if e["event_type"] == "agent_run:failed"
            )
            self.assertEqual(failed_payload["error_kind"], "no_source")
            self.assertIn("/notes?lens=wig", failed_payload["suggested_url"])
            snap = registry.get(task_id)
            self.assertEqual(snap.status, "failed")
            self.assertEqual(snap.error["error_kind"], "no_source")

    async def test_full_pipeline_emits_5_milestones_and_persists(self) -> None:
        registry = AgentRunRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            jsonl_dir = _write_jsonl_dir(tmpdir / "jsonl", [WIG_RAW_NOTE])
            output_dir = tmpdir / "out"
            store = _StubReviewStore()

            # Patch VLM/LLM 客户端：保证测试不走外网，且降级路径已被规则层覆盖
            from apps.intel_hub.extraction import llm_client

            orig_call_text = llm_client.call_text_llm
            orig_call_vlm = llm_client.call_vlm
            orig_avail = llm_client.is_llm_available
            orig_v_avail = llm_client.is_vlm_available
            llm_client.call_text_llm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.call_vlm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.is_llm_available = lambda: False  # type: ignore[assignment]
            llm_client.is_vlm_available = lambda: False  # type: ignore[assignment]

            try:
                task_id, _ = registry.start("wig", lens_label="假发")
                agent = OpportunityGenAgent(
                    task_id=task_id,
                    lens_id="wig",
                    registry=registry,
                    review_store=store,
                    max_notes=5,
                    jsonl_dir=jsonl_dir,
                    output_dir=output_dir,
                )
                async with _SSECollector(channel_for(task_id)) as col:
                    await agent.run()
                    await asyncio.sleep(0.05)
            finally:
                llm_client.call_text_llm = orig_call_text  # type: ignore[assignment]
                llm_client.call_vlm = orig_call_vlm  # type: ignore[assignment]
                llm_client.is_llm_available = orig_avail  # type: ignore[assignment]
                llm_client.is_vlm_available = orig_v_avail  # type: ignore[assignment]

            types = col.types()
            self.assertEqual(types[0], "agent_run:started")
            stage_started = [t for t in types if t == "agent_run:stage_started"]
            stage_completed = [t for t in types if t == "agent_run:stage_completed"]
            self.assertEqual(len(stage_started), 5, f"types={types}")
            self.assertEqual(len(stage_completed), 5, f"types={types}")
            self.assertIn("agent_run:done", types)

            snap = registry.get(task_id)
            self.assertEqual(snap.status, "done")
            for m in snap.milestones:
                self.assertEqual(m["status"], "completed")

            # opportunity_cards.json 应存在并被 sync 一次
            self.assertEqual(len(store.synced_paths), 1)
            self.assertTrue(store.synced_paths[0].exists())
            cards = json.loads(store.synced_paths[0].read_text(encoding="utf-8"))
            self.assertIsInstance(cards, list)
            # 至少不报错；规则层可能产出 0 张卡片，关键是文件成功落地
            self.assertGreaterEqual(store.cards_count, 0)

    async def test_lens_mutex_blocks_double_start(self) -> None:
        registry = AgentRunRegistry()
        registry.start("wig")
        with self.assertRaises(RuntimeError):
            registry.start("wig")
        # 不同 lens 互不影响
        registry.start("tablecloth")

    async def test_default_max_notes_is_one(self) -> None:
        """没有显式传 max_notes 时应只跑 1 篇笔记。"""
        registry = AgentRunRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            jsonl_dir = _write_jsonl_dir(
                tmpdir / "jsonl",
                [_make_raw_note(i) for i in range(1, 6)],
            )
            output_dir = tmpdir / "out"
            store = _StubReviewStore()
            task_id, _ = registry.start("wig", lens_label="假发")
            agent = OpportunityGenAgent(
                task_id=task_id,
                lens_id="wig",
                registry=registry,
                review_store=store,
                jsonl_dir=jsonl_dir,
                output_dir=output_dir,
            )
            self.assertEqual(agent.max_notes, 1)

            # 拉到 raw 列表后只切到 1 条 —— 通过 M1 完成事件汇总验证。
            from apps.intel_hub.extraction import llm_client
            orig = (
                llm_client.call_text_llm,
                llm_client.call_vlm,
                llm_client.is_llm_available,
                llm_client.is_vlm_available,
            )
            llm_client.call_text_llm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.call_vlm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.is_llm_available = lambda: False  # type: ignore[assignment]
            llm_client.is_vlm_available = lambda: False  # type: ignore[assignment]
            try:
                async with _SSECollector(channel_for(task_id)) as col:
                    await agent.run()
                    await asyncio.sleep(0.05)
            finally:
                (
                    llm_client.call_text_llm,
                    llm_client.call_vlm,
                    llm_client.is_llm_available,
                    llm_client.is_vlm_available,
                ) = orig

            snap = registry.get(task_id)
            self.assertEqual(snap.counters.get("notes_total"), 1)
            self.assertEqual(snap.counters.get("notes_done"), 1)
            self.assertIn("agent_run:done", col.types())

    async def test_note_id_filter_picks_specified_note(self) -> None:
        registry = AgentRunRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            jsonl_dir = _write_jsonl_dir(
                tmpdir / "jsonl",
                [_make_raw_note(i) for i in range(1, 6)],
            )
            output_dir = tmpdir / "out"
            store = _StubReviewStore()
            task_id, _ = registry.start("wig", lens_label="假发")
            agent = OpportunityGenAgent(
                task_id=task_id,
                lens_id="wig",
                registry=registry,
                review_store=store,
                max_notes=10,
                note_id_filter="wig_003",
                jsonl_dir=jsonl_dir,
                output_dir=output_dir,
            )
            from apps.intel_hub.extraction import llm_client
            orig = (
                llm_client.call_text_llm,
                llm_client.call_vlm,
                llm_client.is_llm_available,
                llm_client.is_vlm_available,
            )
            llm_client.call_text_llm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.call_vlm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.is_llm_available = lambda: False  # type: ignore[assignment]
            llm_client.is_vlm_available = lambda: False  # type: ignore[assignment]
            try:
                async with _SSECollector(channel_for(task_id)) as col:
                    await agent.run()
                    await asyncio.sleep(0.05)
            finally:
                (
                    llm_client.call_text_llm,
                    llm_client.call_vlm,
                    llm_client.is_llm_available,
                    llm_client.is_vlm_available,
                ) = orig

            snap = registry.get(task_id)
            self.assertEqual(snap.counters.get("notes_total"), 1)
            # 检查事件中提到的 note_id 是 wig_003
            m1_progress_note_ids = {
                e["payload"].get("note_id")
                for e in col.events
                if e["event_type"] == "agent_run:item_progress"
                and e["payload"].get("stage_id") == "M1"
                and e["payload"].get("note_id")
            }
            self.assertEqual(m1_progress_note_ids, {"wig_003"})

    async def test_skip_note_ids_excludes_processed(self) -> None:
        registry = AgentRunRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            jsonl_dir = _write_jsonl_dir(
                tmpdir / "jsonl",
                [_make_raw_note(i) for i in range(1, 6)],
            )
            output_dir = tmpdir / "out"
            store = _StubReviewStore()
            task_id, _ = registry.start("wig", lens_label="假发")
            agent = OpportunityGenAgent(
                task_id=task_id,
                lens_id="wig",
                registry=registry,
                review_store=store,
                max_notes=10,
                skip_note_ids=["wig_001", "wig_002", "wig_003"],
                jsonl_dir=jsonl_dir,
                output_dir=output_dir,
            )
            from apps.intel_hub.extraction import llm_client
            orig = (
                llm_client.call_text_llm,
                llm_client.call_vlm,
                llm_client.is_llm_available,
                llm_client.is_vlm_available,
            )
            llm_client.call_text_llm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.call_vlm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.is_llm_available = lambda: False  # type: ignore[assignment]
            llm_client.is_vlm_available = lambda: False  # type: ignore[assignment]
            try:
                async with _SSECollector(channel_for(task_id)) as col:
                    await agent.run()
                    await asyncio.sleep(0.05)
            finally:
                (
                    llm_client.call_text_llm,
                    llm_client.call_vlm,
                    llm_client.is_llm_available,
                    llm_client.is_vlm_available,
                ) = orig

            snap = registry.get(task_id)
            self.assertEqual(snap.counters.get("notes_total"), 2)
            m1_progress_note_ids = {
                e["payload"].get("note_id")
                for e in col.events
                if e["event_type"] == "agent_run:item_progress"
                and e["payload"].get("stage_id") == "M1"
                and e["payload"].get("note_id")
            }
            self.assertEqual(m1_progress_note_ids, {"wig_004", "wig_005"})

    async def test_skip_all_emits_all_consumed(self) -> None:
        """当所有现存笔记都在 skip 列表里时，应以 all_consumed 友好失败收尾。"""
        registry = AgentRunRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            jsonl_dir = _write_jsonl_dir(
                tmpdir / "jsonl",
                [_make_raw_note(i) for i in range(1, 4)],
            )
            output_dir = tmpdir / "out"
            store = _StubReviewStore()
            task_id, _ = registry.start("wig", lens_label="假发")
            agent = OpportunityGenAgent(
                task_id=task_id,
                lens_id="wig",
                registry=registry,
                review_store=store,
                max_notes=10,
                skip_note_ids=["wig_001", "wig_002", "wig_003"],
                jsonl_dir=jsonl_dir,
                output_dir=output_dir,
            )
            async with _SSECollector(channel_for(task_id)) as col:
                await agent.run()
                await asyncio.sleep(0.05)

            self.assertIn("agent_run:failed", col.types())
            failed = next(
                e["payload"] for e in col.events if e["event_type"] == "agent_run:failed"
            )
            self.assertEqual(failed["error_kind"], "all_consumed")
            snap = registry.get(task_id)
            self.assertEqual(snap.error["error_kind"], "all_consumed")

    async def test_run_writes_task_scoped_snapshot(self) -> None:
        """M5 应同时写全局 cards.json 与任务级 runs/{lens}_{task}.json 两份。"""
        registry = AgentRunRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            jsonl_dir = _write_jsonl_dir(tmpdir / "jsonl", [WIG_RAW_NOTE])
            output_dir = tmpdir / "out"
            store = _StubReviewStore()
            task_id, _ = registry.start("wig", lens_label="假发")
            agent = OpportunityGenAgent(
                task_id=task_id,
                lens_id="wig",
                registry=registry,
                review_store=store,
                max_notes=1,
                jsonl_dir=jsonl_dir,
                output_dir=output_dir,
            )
            from apps.intel_hub.extraction import llm_client
            orig = (
                llm_client.call_text_llm,
                llm_client.call_vlm,
                llm_client.is_llm_available,
                llm_client.is_vlm_available,
            )
            llm_client.call_text_llm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.call_vlm = lambda *a, **kw: ""  # type: ignore[assignment]
            llm_client.is_llm_available = lambda: False  # type: ignore[assignment]
            llm_client.is_vlm_available = lambda: False  # type: ignore[assignment]
            try:
                await agent.run()
                await asyncio.sleep(0.02)
            finally:
                (
                    llm_client.call_text_llm,
                    llm_client.call_vlm,
                    llm_client.is_llm_available,
                    llm_client.is_vlm_available,
                ) = orig

            self.assertTrue((output_dir / "opportunity_cards.json").exists())
            self.assertTrue((output_dir / "runs").exists())
            run_files = list((output_dir / "runs").glob(f"wig_{task_id}.json"))
            self.assertEqual(len(run_files), 1, f"runs={list((output_dir / 'runs').iterdir())}")


if __name__ == "__main__":
    unittest.main()
