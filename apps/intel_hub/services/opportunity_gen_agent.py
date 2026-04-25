"""OpportunityGenAgent — 按类目（lens_id）一键生成机会卡的可观测 Agent。

设计要点：
- 复用现有 ``run_xhs_opportunity_pipeline`` 的步骤函数，但把循环切片到 5
  个里程碑：探查与解析 → 信号提取(VLM/LLM) → 跨模态与映射 → 机会卡编译
  → 透视聚合与入库；
- 每段切口通过 ``event_bus.publish_sync`` 把进度事件广播到 SSE channel
  ``f"agent_run:{task_id}"``，同时把摘要写进 ``AgentRunRegistry``；
- 同步 CPU/IO 密集函数统一通过 ``asyncio.to_thread`` 派发，避免阻塞
  FastAPI event loop（这样 SSE 长连接能稳定 yield heartbeat）。

Agent 不直接接 ``FileJobQueue`` 的采集 worker；当 ``jsonl_dir`` 内不存在
该 lens 关键词笔记时直接 emit ``agent_run:failed { error_kind:"no_source" }``，
引导用户去 ``/notes?lens=...`` 自助补料。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from apps.content_planning.gateway.event_bus import ObjectEvent, event_bus
from apps.intel_hub.config_loader import (
    load_category_lenses,
    resolve_repo_path,
    route_keyword_to_lens_id,
)
from apps.intel_hub.services.agent_run_registry import (
    AgentRunRegistry,
    agent_run_registry,
)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# 公共入口
# ────────────────────────────────────────────────────────────


def channel_for(task_id: str) -> str:
    """SSE 订阅 channel key（与 ``app.get('/.../{id}/stream')`` 保持一致）。"""
    return f"agent_run:{task_id}"


class OpportunityGenAgent:
    """按 ``lens_id`` 跑机会卡生成流水线，并在每个切口广播进度事件。"""

    def __init__(
        self,
        task_id: str,
        lens_id: str,
        *,
        registry: AgentRunRegistry | None = None,
        review_store: Any | None = None,
        max_notes: int = 1,
        jsonl_dir: str | Path | None = None,
        jsonl_dirs: list[str | Path] | None = None,
        output_dir: str | Path | None = None,
        skip_note_ids: list[str] | tuple[str, ...] | None = None,
        note_id_filter: str | None = None,
    ) -> None:
        self.task_id = task_id
        self.lens_id = lens_id
        self.registry = registry or agent_run_registry
        self.review_store = review_store
        self.max_notes = max(1, int(max_notes))
        self.skip_note_ids: set[str] = {nid for nid in (skip_note_ids or ()) if nid}
        self.note_id_filter: str | None = (note_id_filter or "").strip() or None
        self._channel = channel_for(task_id)

        repo_root = resolve_repo_path(".")
        # 数据源优先级：
        # 1) 显式传入的 jsonl_dirs（API 层注入，与 /notes 完全对齐）；
        # 2) 兼容老调用：单个 jsonl_dir；
        # 3) fallback：从 runtime settings.mediacrawler_sources 取所有启用且 platform=xhs 的源；
        # 4) 最后兜底：fixtures + 真实采集目录都扫描。
        self.jsonl_dirs: list[Path] = []
        if jsonl_dirs is not None:
            # 显式注入（包括空 list），用于测试隔离与 API 层精准对齐 /notes 数据源
            self.jsonl_dirs = [Path(d) for d in jsonl_dirs]
        elif jsonl_dir is not None:
            self.jsonl_dirs = [Path(jsonl_dir)]
        else:
            try:
                from apps.intel_hub.config_loader import load_runtime_settings
                settings = load_runtime_settings()
                for src in settings.mediacrawler_sources:
                    if not src.get("enabled", True):
                        continue
                    if str(src.get("platform", "xiaohongshu")).lower() not in {
                        "xiaohongshu", "xhs", "rednote",
                    }:
                        continue
                    out = resolve_repo_path(src.get("output_path", ""))
                    if out.exists():
                        self.jsonl_dirs.append(out)
                    fb = src.get("fixture_fallback")
                    if fb:
                        fb_path = resolve_repo_path(fb)
                        if fb_path.exists() and fb_path not in self.jsonl_dirs:
                            self.jsonl_dirs.append(fb_path)
            except Exception:  # noqa: BLE001
                logger.warning("load runtime mediacrawler_sources failed", exc_info=True)
            if not self.jsonl_dirs:
                fixtures = repo_root / "data" / "fixtures" / "mediacrawler_output" / "xhs" / "jsonl"
                mc = repo_root / "third_party" / "MediaCrawler" / "data" / "xhs" / "jsonl"
                if fixtures.exists():
                    self.jsonl_dirs.append(fixtures)
                if mc.exists() and mc not in self.jsonl_dirs:
                    self.jsonl_dirs.append(mc)

        # 兼容老属性（用于单测断言或单目录场景）：
        self.jsonl_dir = self.jsonl_dirs[0] if self.jsonl_dirs else (
            repo_root / "data" / "fixtures" / "mediacrawler_output" / "xhs" / "jsonl"
        )
        self.output_dir = Path(output_dir or (repo_root / "data" / "output" / "xhs_opportunities"))

    # ── 主流程 ──────────────────────────────────────────────────

    async def run(self) -> None:
        """异步执行；任何异常都被吞下并以 failed 事件结束，不会冒泡到调用方。"""
        try:
            self.registry.mark_running(self.task_id)

            from apps.intel_hub.config_loader import load_lens_keyword_routing

            lenses = load_category_lenses()
            lens_obj = lenses.get(self.lens_id)
            lens_label = (
                getattr(lens_obj, "category_cn", None) or self.lens_id
            ) if lens_obj is not None else self.lens_id

            self._emit(
                "agent_run:started",
                {
                    "task_id": self.task_id,
                    "lens_id": self.lens_id,
                    "lens_label": lens_label,
                    "max_notes": self.max_notes,
                    "milestones": [
                        {"id": m["id"], "label": m["label"], "weight": m["weight"]}
                        for m in self.registry.get(self.task_id).milestones
                    ],
                },
            )

            # ── M1: 探查与解析 ─────────────────────────────────
            if self._cancelled():
                return self._finish_cancelled()

            self._stage_started("M1", "探查与解析", total=0)
            # I/O 量级 < 1ms / KB，直接同步调用，避免 TestClient/portal 下
            # asyncio.to_thread 调度回主 loop 出现的体感延迟。
            raw_dicts, comment_index = self._load_lens_raw_dicts(
                self.jsonl_dirs or [self.jsonl_dir], self.lens_id
            )
            if not raw_dicts:
                self._emit(
                    "agent_run:failed",
                    {
                        "error_kind": "no_source",
                        "message": f"该类目「{lens_label}」当前还没有原始笔记可供分析。",
                        "suggestion": "请先去素材中心采集相关关键词的小红书笔记，再回来重新生成。",
                        "suggested_url": f"/notes?lens={self.lens_id}",
                    },
                )
                self.registry.mark_failed(
                    self.task_id,
                    error_kind="no_source",
                    message="该类目暂无原始笔记可供生成机会卡。",
                    suggestion="先去素材中心补料，再回来生成。",
                    suggested_url=f"/notes?lens={self.lens_id}",
                )
                return

            # 增量补跑过滤：note_id 优先（精确指定单条），否则跳过已处理。
            if self.note_id_filter:
                raw_dicts = [r for r in raw_dicts if r.get("note_id") == self.note_id_filter]
            elif self.skip_note_ids:
                raw_dicts = [
                    r for r in raw_dicts if r.get("note_id") not in self.skip_note_ids
                ]

            if not raw_dicts:
                # 已处理全部笔记或指定的单条不存在 —— 用 all_consumed 让前端展示
                # "本类目所有笔记都已生成过机会卡了"的友好态。
                kind = "note_not_found" if self.note_id_filter else "all_consumed"
                msg = (
                    f"指定的笔记 {self.note_id_filter} 不在本类目下。"
                    if self.note_id_filter
                    else f"该类目「{lens_label}」下的笔记都已经生成过机会卡了。"
                )
                self._emit(
                    "agent_run:failed",
                    {
                        "error_kind": kind,
                        "message": msg,
                        "suggestion": "可去素材中心采集更多新笔记，或直接查看现有机会卡。",
                        "suggested_url": f"/xhs-opportunities?lens={self.lens_id}",
                    },
                )
                self.registry.mark_failed(
                    self.task_id,
                    error_kind=kind,
                    message=msg,
                    suggestion="可去素材中心采集更多新笔记，或直接查看现有机会卡。",
                    suggested_url=f"/xhs-opportunities?lens={self.lens_id}",
                )
                return

            raw_dicts = raw_dicts[: self.max_notes]
            self.registry.set_counter(self.task_id, "notes_total", len(raw_dicts))
            self._stage_progress(
                "M1", note_id="", note_title=f"按 lens 路由到 {len(raw_dicts)} 篇笔记"
            )

            parsed_results = self._parse_all(raw_dicts, comment_index)
            await asyncio.sleep(0)  # 让出一拍，确保 stage_started 事件已 flush
            for parsed_meta in parsed_results:
                self._stage_progress(
                    "M1",
                    note_id=parsed_meta["note_id"],
                    note_title=parsed_meta["title"],
                )
            self._stage_completed(
                "M1",
                summary={"parsed_notes": len(parsed_results)},
            )

            if self._cancelled():
                return self._finish_cancelled()

            # ── M2: 信号提取（VLM 视觉 + LLM 卖点 + LLM 场景） ─────
            self._stage_started("M2", "信号提取", total=len(parsed_results))
            extraction_results: list[dict[str, Any]] = []
            for idx, item in enumerate(parsed_results, start=1):
                if self._cancelled():
                    return self._finish_cancelled()
                t0 = time.perf_counter()
                signals = await asyncio.to_thread(
                    self._extract_signals_for_note, item["parsed"]
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                extraction_results.append({**item, **signals})

                self.registry.bump_counters(
                    self.task_id,
                    notes_done=1,
                    vlm_calls=1 if signals["used_vlm"] else 0,
                    llm_calls=2 if signals["used_llm"] else 0,
                )
                self._emit(
                    "agent_run:item_progress",
                    {
                        "stage_id": "M2",
                        "note_id": item["note_id"],
                        "note_title": item["title"],
                        "ok": True,
                        "latency_ms": latency_ms,
                        "used_vlm": signals["used_vlm"],
                        "used_llm": signals["used_llm"],
                        "visual_count": signals["visual_count"],
                        "selling_count": signals["selling_count"],
                        "scene_count": signals["scene_count"],
                    },
                )
                self.registry.update_milestone(
                    self.task_id, "M2",
                    status="running",
                    progress=idx / max(len(parsed_results), 1),
                )
            self._stage_completed(
                "M2",
                summary={
                    "vlm_calls": self.registry.get(self.task_id).counters["vlm_calls"],
                    "llm_calls": self.registry.get(self.task_id).counters["llm_calls"],
                },
            )

            # ── M3: 跨模态与映射 ────────────────────────────────
            if self._cancelled():
                return self._finish_cancelled()
            self._stage_started("M3", "跨模态与映射", total=len(extraction_results))
            mapping_results = self._cross_modal_and_map(extraction_results)
            await asyncio.sleep(0)
            for r in mapping_results:
                self._stage_progress(
                    "M3", note_id=r["note_id"], note_title=r["title"],
                    extra={
                        "consistency": round(
                            (r["validation"].overall_consistency_score or 0.0), 2
                        ),
                    },
                )
            self._stage_completed(
                "M3",
                summary={
                    "avg_consistency": round(
                        sum(
                            (r["validation"].overall_consistency_score or 0.0)
                            for r in mapping_results
                        ) / max(len(mapping_results), 1),
                        2,
                    )
                },
            )

            # ── M4: 机会卡编译 ─────────────────────────────────
            if self._cancelled():
                return self._finish_cancelled()
            self._stage_started("M4", "机会卡编译", total=len(mapping_results))
            compile_out = self._compile_cards(mapping_results)
            await asyncio.sleep(0)
            cards_total = sum(len(c) for c in compile_out["cards_by_note"].values())
            self.registry.set_counter(self.task_id, "cards_total", cards_total)
            for nid, cards in compile_out["cards_by_note"].items():
                self._emit(
                    "agent_run:item_progress",
                    {
                        "stage_id": "M4",
                        "note_id": nid,
                        "note_title": compile_out["title_by_note"].get(nid, ""),
                        "ok": True,
                        "card_count": len(cards),
                    },
                )
            self._stage_completed("M4", summary={"cards_total": cards_total})

            # ── M5: 类目透视聚合 + 入库 ───────────────────────
            if self._cancelled():
                return self._finish_cancelled()
            self._stage_started("M5", "类目透视聚合与入库", total=1)
            persist_summary = self._persist_and_aggregate(compile_out, mapping_results)
            await asyncio.sleep(0)
            self._stage_completed("M5", summary=persist_summary)

            self._emit(
                "agent_run:done",
                {
                    "cards_total": cards_total,
                    "lens_score": persist_summary.get("lens_score"),
                    "decision": persist_summary.get("decision"),
                    "jump_url": f"/xhs-opportunities?lens={self.lens_id}",
                    "lens_id": self.lens_id,
                    "lens_label": lens_label,
                },
            )
            self.registry.mark_done(
                self.task_id,
                summary={
                    "cards_total": cards_total,
                    "lens_score": persist_summary.get("lens_score"),
                    "decision": persist_summary.get("decision"),
                    "jump_url": f"/xhs-opportunities?lens={self.lens_id}",
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpportunityGenAgent task=%s 执行失败", self.task_id)
            self._emit(
                "agent_run:failed",
                {
                    "error_kind": "unknown",
                    "message": f"生成失败：{exc}",
                    "suggestion": "请稍后重试，或检查 DashScope/采集器配置。",
                    "suggested_url": "",
                },
            )
            self.registry.mark_failed(
                self.task_id,
                error_kind="unknown",
                message=str(exc),
                suggestion="请稍后重试，或检查 DashScope/采集器配置。",
            )

    # ── 阶段事件辅助 ────────────────────────────────────────────

    def _stage_started(self, stage_id: str, label: str, *, total: int) -> None:
        self.registry.update_milestone(self.task_id, stage_id, status="running", progress=0.0)
        self._emit(
            "agent_run:stage_started",
            {"stage_id": stage_id, "label": label, "total_items": total, "milestone": stage_id},
        )

    def _stage_progress(
        self,
        stage_id: str,
        *,
        note_id: str,
        note_title: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "stage_id": stage_id,
            "note_id": note_id,
            "note_title": note_title,
            "ok": True,
        }
        if extra:
            payload.update(extra)
        self._emit("agent_run:item_progress", payload)

    def _stage_completed(self, stage_id: str, *, summary: dict[str, Any]) -> None:
        self.registry.update_milestone(self.task_id, stage_id, status="completed", progress=1.0)
        self._emit(
            "agent_run:stage_completed",
            {"stage_id": stage_id, "summary": summary},
        )

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        evt = ObjectEvent(
            event_type=event_type,
            opportunity_id=self._channel,
            payload={
                "task_id": self.task_id,
                "lens_id": self.lens_id,
                **payload,
            },
        )
        try:
            event_bus.publish_sync(evt)
        except Exception:  # noqa: BLE001
            logger.warning("publish event failed task=%s type=%s", self.task_id, event_type)
        self.registry.append_event(
            self.task_id,
            {"event_type": event_type, "payload": evt.payload},
        )

    def _cancelled(self) -> bool:
        return self.registry.is_cancelled(self.task_id)

    def _finish_cancelled(self) -> None:
        self._emit(
            "agent_run:failed",
            {
                "error_kind": "cancelled",
                "message": "任务已被用户取消。",
                "suggestion": "可在准备好后重新点击「立即生成机会卡」。",
                "suggested_url": "",
            },
        )
        self.registry.mark_cancelled(self.task_id)

    # ── 流水线步骤实现（同步代码，跑在 to_thread 中） ───────────

    @staticmethod
    def _load_lens_raw_dicts(
        jsonl_dirs: Path | list[Path],
        lens_id: str,
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        if isinstance(jsonl_dirs, (str, Path)):
            dirs: list[Path] = [Path(jsonl_dirs)]
        else:
            dirs = [Path(d) for d in jsonl_dirs]

        comment_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
        raw_dicts: list[dict[str, Any]] = []
        seen: set[str] = set()
        seen_dirs: set[Path] = set()

        for jsonl_dir in dirs:
            try:
                resolved = jsonl_dir.resolve()
            except OSError:
                resolved = jsonl_dir
            if resolved in seen_dirs or not jsonl_dir.exists():
                continue
            seen_dirs.add(resolved)

            for cf in sorted(jsonl_dir.glob("search_comments_*.jsonl")):
                for line in cf.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    nid = item.get("note_id")
                    if nid:
                        comment_index[str(nid)].append(item)

            for cf in sorted(jsonl_dir.glob("search_contents_*.jsonl")):
                for line in cf.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    note_id = item.get("note_id") or ""
                    if not note_id or note_id in seen:
                        continue
                    routed = item.get("lens_id") or route_keyword_to_lens_id(
                        item.get("source_keyword") or item.get("keyword")
                    )
                    if routed != lens_id:
                        continue
                    seen.add(note_id)
                    if not item.get("lens_id"):
                        item["lens_id"] = lens_id
                    raw_dicts.append(item)
        return raw_dicts, dict(comment_index)

    @staticmethod
    def _parse_all(
        raw_dicts: list[dict[str, Any]],
        comment_index: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note

        out: list[dict[str, Any]] = []
        for raw in raw_dicts:
            nid = str(raw.get("note_id") or "")
            if not nid:
                continue
            comments = comment_index.get(nid, [])
            try:
                raw_note = parse_raw_note(raw, comments=comments)
                parsed = parse_note(raw_note)
            except Exception:  # noqa: BLE001
                logger.warning("parse failed note=%s", nid, exc_info=True)
                continue
            out.append({
                "note_id": nid,
                "title": parsed.normalized_title[:50],
                "raw": raw,
                "raw_note": raw_note,
                "parsed": parsed,
            })
        return out

    @staticmethod
    def _extract_signals_for_note(parsed: Any) -> dict[str, Any]:
        from apps.intel_hub.extraction.llm_client import is_llm_available, is_vlm_available
        from apps.intel_hub.extraction.scene_extractor import extract_scene_signals
        from apps.intel_hub.extraction.selling_theme_extractor import (
            extract_selling_theme_signals,
        )
        from apps.intel_hub.extraction.visual_extractor import extract_visual_signals

        try:
            visual = extract_visual_signals(parsed)
        except Exception:  # noqa: BLE001
            logger.warning("visual extraction failed", exc_info=True)
            from apps.intel_hub.schemas.xhs_signals import VisualSignals
            visual = VisualSignals(note_id=parsed.note_id)

        try:
            selling = extract_selling_theme_signals(parsed)
        except Exception:  # noqa: BLE001
            logger.warning("selling extraction failed", exc_info=True)
            from apps.intel_hub.schemas.xhs_signals import SellingThemeSignals
            selling = SellingThemeSignals(note_id=parsed.note_id)

        try:
            scene = extract_scene_signals(parsed, visual_signals=visual)
        except Exception:  # noqa: BLE001
            logger.warning("scene extraction failed", exc_info=True)
            from apps.intel_hub.schemas.xhs_signals import SceneSignals
            scene = SceneSignals(note_id=parsed.note_id)

        return {
            "visual": visual,
            "selling": selling,
            "scene": scene,
            "used_vlm": is_vlm_available(),
            "used_llm": is_llm_available(),
            "visual_count": len(getattr(visual, "visual_style_signals", []) or []),
            "selling_count": len(getattr(selling, "selling_point_signals", []) or []),
            "scene_count": len(getattr(scene, "scene_signals", []) or []),
        }

    @staticmethod
    def _cross_modal_and_map(
        extraction_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        from apps.intel_hub.config_loader import load_ontology_mapping
        from apps.intel_hub.extraction.cross_modal_validator import (
            validate_cross_modal_consistency,
        )
        from apps.intel_hub.projector.ontology_projector import project_xhs_signals

        ontology_config = load_ontology_mapping()
        out: list[dict[str, Any]] = []
        for item in extraction_results:
            parsed = item["parsed"]
            try:
                validation = validate_cross_modal_consistency(
                    item["visual"], item["selling"], item["scene"], parsed,
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "cross_modal failed note=%s", item["note_id"], exc_info=True
                )
                from apps.intel_hub.schemas.xhs_validation import CrossModalValidation
                validation = CrossModalValidation(note_id=parsed.note_id)
            try:
                mapping = project_xhs_signals(
                    item["visual"], item["selling"], item["scene"],
                    ontology_config, cross_modal=validation,
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "ontology mapping failed note=%s", item["note_id"], exc_info=True
                )
                from apps.intel_hub.schemas.ontology_mapping_model import XHSOntologyMapping
                mapping = XHSOntologyMapping(note_id=parsed.note_id)
            out.append({**item, "validation": validation, "mapping": mapping})
        return out

    @staticmethod
    def _compile_cards(
        mapping_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from apps.intel_hub.compiler.opportunity_compiler import compile_xhs_opportunities
        from apps.intel_hub.config_loader import load_yaml

        rules_config = load_yaml(resolve_repo_path("config/opportunity_rules.yaml"))
        cards_by_note: dict[str, list[Any]] = {}
        title_by_note: dict[str, str] = {}
        lens_id_by_note: dict[str, str | None] = {}

        for item in mapping_results:
            nid = item["note_id"]
            note_ctx = {
                "like_count": getattr(item["raw_note"], "like_count", 0),
                "collect_count": getattr(item["raw_note"], "collect_count", 0),
                "comment_count": getattr(item["raw_note"], "comment_count", 0),
                "share_count": getattr(item["raw_note"], "share_count", 0),
            }
            try:
                cards = compile_xhs_opportunities(
                    item["mapping"], item["visual"], item["selling"], item["scene"],
                    rules_config,
                    cross_modal=item["validation"], note_context=note_ctx,
                )
            except Exception:  # noqa: BLE001
                logger.warning("compile failed note=%s", nid, exc_info=True)
                cards = []
            cards_by_note[nid] = cards
            title_by_note[nid] = item["title"]
            lens_id_by_note[nid] = item.get("raw", {}).get("lens_id")

        return {
            "cards_by_note": cards_by_note,
            "title_by_note": title_by_note,
            "lens_id_by_note": lens_id_by_note,
            "mapping_results": mapping_results,
        }

    def _persist_and_aggregate(
        self,
        compile_out: dict[str, Any],
        mapping_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from apps.intel_hub.compiler.opportunity_compiler import (
            apply_lens_bundles_to_cards,
        )
        from apps.intel_hub.engine.category_lens_engine import (
            CategoryLensEngine,
            LensEngineInput,
        )
        from apps.intel_hub.extractor import extract_business_signals
        from apps.intel_hub.workflow.xhs_opportunity_pipeline import (
            _build_lens_content_frame,
        )

        lenses = load_category_lenses()
        lens_obj = lenses.get(self.lens_id)

        # 类目透视：汇聚本批 lens 范围内的 NoteContentFrame + BusinessSignalFrame
        lens_inputs: list[LensEngineInput] = []
        if lens_obj is not None:
            for item in mapping_results:
                try:
                    frame = _build_lens_content_frame(item["raw_note"], item["parsed"])
                    bsf = extract_business_signals(frame, lens=lens_obj)
                    lens_inputs.append(
                        LensEngineInput(frame=frame, business_signals=bsf)
                    )
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "lens frame build failed note=%s", item["note_id"], exc_info=True
                    )

        lens_bundles: dict[str, Any] = {}
        if lens_obj is not None and lens_inputs:
            try:
                bundle = CategoryLensEngine(lens_obj).run(lens_inputs)
                lens_bundles[self.lens_id] = bundle
            except Exception:  # noqa: BLE001
                logger.warning("CategoryLensEngine run failed", exc_info=True)

        # 把 bundle 写回 cards 的 lens_* 字段
        if lens_bundles and compile_out["cards_by_note"]:
            try:
                apply_lens_bundles_to_cards(
                    compile_out["cards_by_note"],
                    compile_out["lens_id_by_note"],
                    lens_bundles,
                )
            except Exception:  # noqa: BLE001
                logger.warning("apply_lens_bundles_to_cards failed", exc_info=True)

        # 持久化：JSON + bundle JSON + SQLite
        self.output_dir.mkdir(parents=True, exist_ok=True)
        bundles_dir = self.output_dir / "lens_bundles"
        if lens_bundles:
            bundles_dir.mkdir(parents=True, exist_ok=True)
            for lid, bundle in lens_bundles.items():
                payload = (
                    bundle.model_dump(mode="json")
                    if hasattr(bundle, "model_dump")
                    else bundle
                )
                (bundles_dir / f"{lid}.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        # opportunity_cards.json 是全局合集（多 lens 共用）；
        # Agent 此次只生成本 lens 的 cards，做 merge：读旧 → 去重 → 写新。
        cards_path = self.output_dir / "opportunity_cards.json"
        existing: list[dict[str, Any]] = []
        if cards_path.exists():
            try:
                existing = json.loads(cards_path.read_text(encoding="utf-8")) or []
            except Exception:  # noqa: BLE001
                existing = []

        new_cards: list[dict[str, Any]] = []
        for cards in compile_out["cards_by_note"].values():
            for c in cards:
                new_cards.append(c.model_dump(mode="json"))
        new_ids = {c.get("opportunity_id") for c in new_cards if c.get("opportunity_id")}
        merged = [c for c in existing if c.get("opportunity_id") not in new_ids]
        merged.extend(new_cards)
        cards_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # pipeline_details.json 是详情页 / 内容策划 / 视觉工作台拿原始笔记
        # 上下文（封面、正文、互动数、VLM 信号等）的唯一数据源。Agent 必须
        # 把本批每篇笔记的 entry 按 note_id merge 进去，否则机会卡详情页会
        # 显示「原始笔记数据暂不可用」。结构与
        # ``apps/intel_hub/workflow/xhs_opportunity_pipeline.py`` 输出对齐。
        cards_by_note = compile_out["cards_by_note"]
        new_details: list[dict[str, Any]] = []
        for item in mapping_results:
            nid = item["note_id"]
            parsed = item.get("parsed")
            rn = item.get("raw_note")
            note_ctx: dict[str, Any] = {}
            if rn is not None:
                note_ctx = {
                    "note_id": getattr(rn, "note_id", nid),
                    "note_url": getattr(rn, "note_url", ""),
                    "title": getattr(rn, "title_text", ""),
                    "body": getattr(rn, "body_text", ""),
                    "author_name": getattr(rn, "author_name", ""),
                    "cover_image": getattr(rn, "cover_image", ""),
                    "image_urls": [
                        img.url for img in getattr(rn, "image_list", []) or []
                    ],
                    "tag_list": list(getattr(rn, "tag_list", []) or []),
                    "like_count": getattr(rn, "like_count", 0),
                    "collect_count": getattr(rn, "collect_count", 0),
                    "comment_count": getattr(rn, "comment_count", 0),
                    "share_count": getattr(rn, "share_count", 0),
                    "top_comments": [
                        {
                            "nickname": getattr(c, "nickname", ""),
                            "content": getattr(c, "content", ""),
                            "like_count": getattr(c, "like_count", 0),
                        }
                        for c in (getattr(rn, "top_comments", []) or [])[:5]
                    ],
                }

            def _dump(obj: Any) -> Any:
                if obj is None:
                    return {}
                if hasattr(obj, "model_dump"):
                    try:
                        return obj.model_dump(mode="json")
                    except Exception:  # noqa: BLE001
                        return {}
                return obj

            new_details.append({
                "note_id": nid,
                "title": getattr(parsed, "normalized_title", "") if parsed else "",
                "note_context": note_ctx,
                "visual_signals": _dump(item.get("visual")),
                "selling_theme_signals": _dump(item.get("selling")),
                "scene_signals": _dump(item.get("scene")),
                "cross_modal_validation": _dump(item.get("validation")),
                "ontology_mapping": _dump(item.get("mapping")),
                "opportunity_cards": [
                    c.model_dump(mode="json") for c in cards_by_note.get(nid, [])
                ],
            })

        if new_details:
            details_path = self.output_dir / "pipeline_details.json"
            existing_details: list[dict[str, Any]] = []
            if details_path.exists():
                try:
                    existing_details = (
                        json.loads(details_path.read_text(encoding="utf-8")) or []
                    )
                except Exception:  # noqa: BLE001
                    existing_details = []
            new_detail_ids = {e["note_id"] for e in new_details if e.get("note_id")}
            merged_details = [
                e for e in existing_details if e.get("note_id") not in new_detail_ids
            ]
            merged_details.extend(new_details)
            try:
                details_path.write_text(
                    json.dumps(merged_details, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:  # noqa: BLE001
                logger.warning("write pipeline_details merged failed", exc_info=True)

        # 任务级隔离快照：保留每次跑的本批新卡片，便于审计 / 回放，且不会
        # 被后续增量任务覆写（与全局 cards_path 解耦）。
        runs_dir = self.output_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        run_snapshot_path = runs_dir / f"{self.lens_id}_{self.task_id}.json"
        try:
            run_snapshot_path.write_text(
                json.dumps(new_cards, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            logger.warning("write run snapshot failed", exc_info=True)

        # 入库
        sync_count = 0
        if self.review_store is not None:
            try:
                sync_count = self.review_store.sync_cards_from_json(cards_path)
            except Exception:  # noqa: BLE001
                logger.warning("sync_cards_from_json failed", exc_info=True)

        # 透视摘要
        bundle = lens_bundles.get(self.lens_id)
        lens_score = None
        decision = None
        if bundle is not None:
            try:
                lens_score = round(bundle.evidence_score.total, 2)
                decision = bundle.recommended_action.decision
            except Exception:  # noqa: BLE001
                lens_score = None
                decision = None

        return {
            "cards_persisted": len(new_cards),
            "cards_synced": sync_count,
            "lens_score": lens_score,
            "decision": decision,
            "lens_id": self.lens_id,
        }
