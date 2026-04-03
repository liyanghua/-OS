from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from apps.intel_hub.compiler.opportunity_compiler import compile_opportunity_cards
from apps.intel_hub.compiler.priority_ranker import rank_projected_signals
from apps.intel_hub.compiler.risk_compiler import compile_risk_cards
from apps.intel_hub.config_loader import (
    load_dedupe_config,
    load_ontology_mapping,
    load_runtime_settings,
    load_scoring_config,
    load_watchlists,
)
from apps.intel_hub.ingest.source_router import collect_raw_signals
from apps.intel_hub.normalize.normalizer import normalize_raw_signals
from apps.intel_hub.projector.ontology_projector import project_signals
from apps.intel_hub.storage.repository import Repository


@dataclass(slots=True)
class PipelineResult:
    raw_count: int
    signal_count: int
    opportunity_count: int
    risk_count: int
    storage_path: Path


def run_pipeline(runtime_config_path: str | Path | None = None) -> PipelineResult:
    settings = load_runtime_settings(runtime_config_path)
    raw_records = collect_raw_signals(settings)

    signals, evidence_refs = normalize_raw_signals(raw_records)
    watchlists = load_watchlists()
    dedupe_config = load_dedupe_config()
    projected_signals = project_signals(signals, watchlists, load_ontology_mapping(), dedupe_config)
    ranked_signals = rank_projected_signals(projected_signals, load_scoring_config())
    ontology_mapping = load_ontology_mapping()
    opportunity_cards = compile_opportunity_cards(ranked_signals, ontology_mapping, dedupe_config)
    risk_cards = compile_risk_cards(ranked_signals, ontology_mapping, dedupe_config)

    repository = Repository(settings.resolved_storage_path())
    repository.save_watchlists(watchlists)
    repository.save_signals(ranked_signals)
    repository.save_evidence_refs(evidence_refs)
    repository.save_opportunity_cards(opportunity_cards)
    repository.save_risk_cards(risk_cards)
    _write_raw_snapshot(settings.resolved_raw_snapshot_dir(), raw_records)

    return PipelineResult(
        raw_count=len(raw_records),
        signal_count=len(ranked_signals),
        opportunity_count=len(opportunity_cards),
        risk_count=len(risk_cards),
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
    result = run_pipeline()
    print(
        json.dumps(
            {
                "raw_count": result.raw_count,
                "signal_count": result.signal_count,
                "opportunity_count": result.opportunity_count,
                "risk_count": result.risk_count,
                "storage_path": str(result.storage_path),
            },
            ensure_ascii=False,
        )
    )
