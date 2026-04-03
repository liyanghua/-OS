"""Intel Hub V2 四层编译链流水线入口。

把小红书笔记从"内容样本"编译成"经营决策资产"。

四层编译链：
  Layer 1 — 内容解析（NoteContentFrame）
  Layer 2 — 经营信号抽取（BusinessSignalFrame）
  Layer 3 — 本体映射（多维 refs: scene / style / need / risk / material / ...）
  Layer 4 — 决策资产编译（Opportunity / Risk / Insight / VisualPattern / DemandSpec）

阶段顺序：
1. ``collect_raw_signals`` — 合并 TrendRadar、MediaCrawler、xhs 旧路径、raw_lake
2. ``parse + extract`` — Layer 1+2 笔记内容解析 + 经营信号抽取
3. ``normalize_raw_signals`` — 去重、稳定 ID、Signal + EvidenceRef
4. ``project_signals`` — Layer 3 本体投影（多维 refs）
5. ``rank_projected_signals`` — 业务优先级分
6. ``compile_*`` — Layer 4 决策资产编译（5 类卡片）
7. ``Repository.save_*`` — 持久化

详细说明见 ``docs/PLAN_V2_COMPILATION_CHAIN.md``。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from apps.intel_hub.compiler.demand_spec_compiler import compile_demand_spec_assets
from apps.intel_hub.compiler.insight_compiler import compile_insight_cards
from apps.intel_hub.compiler.opportunity_compiler import compile_opportunity_cards
from apps.intel_hub.compiler.priority_ranker import rank_projected_signals
from apps.intel_hub.compiler.risk_compiler import compile_risk_cards
from apps.intel_hub.compiler.visual_pattern_compiler import compile_visual_pattern_assets
from apps.intel_hub.config_loader import (
    load_dedupe_config,
    load_ontology_mapping,
    load_runtime_settings,
    load_scoring_config,
    load_watchlists,
)
from apps.intel_hub.extractor import (
    analyze_note_images,
    extract_business_signals,
    is_vision_available,
    parse_note_content,
)
from apps.intel_hub.ingest.source_router import collect_raw_signals
from apps.intel_hub.normalize.normalizer import normalize_raw_signals
from apps.intel_hub.projector.ontology_projector import project_signals
from apps.intel_hub.storage.repository import Repository
from apps.intel_hub.workflow.pipeline_stage_log import (
    log_stage_cluster,
    log_stage_collect,
    log_stage_extract,
    log_stage_normalize,
    log_stage_persist,
    log_stage_project,
    log_stage_rank,
)


@dataclass(slots=True)
class PipelineResult:
    raw_count: int
    signal_count: int
    opportunity_count: int
    risk_count: int
    insight_count: int = 0
    visual_pattern_count: int = 0
    demand_spec_count: int = 0
    extraction_count: int = 0
    storage_path: Path = field(default_factory=lambda: Path("."))


def run_pipeline(
    runtime_config_path: str | Path | None = None,
    *,
    enable_vision: bool = False,
) -> PipelineResult:
    settings = load_runtime_settings(runtime_config_path)

    logger = logging.getLogger(__name__)

    vision_on = enable_vision and is_vision_available()
    if enable_vision and not vision_on:
        logger.warning("vision requested but DASHSCOPE_API_KEY not set or dashscope not installed — skipping")

    # 1) 多源 raw dict（含小红书 mediacrawler_sources）
    raw_records = collect_raw_signals(settings)
    log_stage_collect(raw_records)

    # 2) Layer 1+2: 内容解析 + 经营信号抽取 + (可选)视觉分析
    extraction_count = 0
    vision_count = 0
    for raw in raw_records:
        frame = parse_note_content(raw)
        if frame is not None:
            bsf = extract_business_signals(frame)

            if vision_on and frame.image_list:
                visual_signals = analyze_note_images(frame)
                if visual_signals:
                    for k, v in visual_signals.items():
                        if hasattr(bsf, k) and isinstance(v, list):
                            existing = getattr(bsf, k)
                            merged = list(dict.fromkeys(existing + v))
                            setattr(bsf, k, merged)
                    vision_count += 1

            raw["_content_frame"] = frame.model_dump()
            raw["_business_signals"] = bsf.model_dump()
            extraction_count += 1
    log_stage_extract(len(raw_records), extraction_count, vision_count=vision_count)

    # 3) 归一化为 Signal + EvidenceRef（去重、confidence、时间）
    signals, evidence_refs = normalize_raw_signals(raw_records)
    log_stage_normalize(raw_records, signals, evidence_refs)

    watchlists = load_watchlists()
    dedupe_config = load_dedupe_config()
    ontology_mapping = load_ontology_mapping()

    # 4) Layer 3: 本体投影（多维 refs）
    projected_signals = project_signals(signals, watchlists, ontology_mapping, dedupe_config)
    log_stage_project(projected_signals)

    # 5) 业务优先级分
    ranked_signals = rank_projected_signals(projected_signals, load_scoring_config())
    log_stage_rank(ranked_signals)

    # 6) Layer 4: 决策资产编译（5 类卡片）
    opportunity_cards = compile_opportunity_cards(ranked_signals, ontology_mapping, dedupe_config)
    risk_cards = compile_risk_cards(ranked_signals, ontology_mapping, dedupe_config)
    insight_cards = compile_insight_cards(ranked_signals, ontology_mapping, dedupe_config)
    visual_pattern_assets = compile_visual_pattern_assets(ranked_signals, ontology_mapping, dedupe_config)
    demand_spec_assets = compile_demand_spec_assets(ranked_signals, ontology_mapping, dedupe_config)
    log_stage_cluster(
        ranked_signals, ontology_mapping,
        len(opportunity_cards), len(risk_cards),
        len(insight_cards), len(visual_pattern_assets), len(demand_spec_assets),
    )

    # 7) 持久化
    repository = Repository(settings.resolved_storage_path())
    repository.save_watchlists(watchlists)
    repository.save_signals(ranked_signals)
    repository.save_evidence_refs(evidence_refs)
    repository.save_opportunity_cards(opportunity_cards)
    repository.save_risk_cards(risk_cards)
    repository.save_insight_cards(insight_cards)
    repository.save_visual_pattern_assets(visual_pattern_assets)
    repository.save_demand_spec_assets(demand_spec_assets)
    _write_raw_snapshot(settings.resolved_raw_snapshot_dir(), raw_records)
    log_stage_persist(settings.resolved_storage_path(), str(settings.resolved_raw_snapshot_dir()))

    return PipelineResult(
        raw_count=len(raw_records),
        signal_count=len(ranked_signals),
        opportunity_count=len(opportunity_cards),
        risk_count=len(risk_cards),
        insight_count=len(insight_cards),
        visual_pattern_count=len(visual_pattern_assets),
        demand_spec_count=len(demand_spec_assets),
        extraction_count=extraction_count,
        storage_path=settings.resolved_storage_path(),
    )


def _write_raw_snapshot(raw_snapshot_dir: Path, raw_records: list[dict[str, object]]) -> None:
    raw_snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = raw_snapshot_dir / "latest_raw_signals.jsonl"
    snapshot_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in raw_records),
        encoding="utf-8",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Intel Hub V2 pipeline")
    parser.add_argument("--enable-vision", action="store_true", help="启用千问 VL 视觉分析")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s | %(message)s",
    )
    result = run_pipeline(enable_vision=args.enable_vision)
    print(
        json.dumps(
            {
                "raw_count": result.raw_count,
                "signal_count": result.signal_count,
                "extraction_count": result.extraction_count,
                "opportunity_count": result.opportunity_count,
                "risk_count": result.risk_count,
                "insight_count": result.insight_count,
                "visual_pattern_count": result.visual_pattern_count,
                "demand_spec_count": result.demand_spec_count,
                "storage_path": str(result.storage_path),
            },
            ensure_ascii=False,
        )
    )
