from __future__ import annotations

from typing import Any

from apps.intel_hub.projector.entity_resolver import resolve_entities
from apps.intel_hub.projector.topic_tagger import tag_topics
from apps.intel_hub.schemas.signal import Signal
from apps.intel_hub.schemas.watchlist import Watchlist


def project_signals(
    signals: list[Signal],
    watchlists: list[Watchlist],
    ontology_mapping: dict[str, Any],
    dedupe_config: dict[str, Any] | None = None,
) -> list[Signal]:
    projected: list[Signal] = []
    platform_mapping = ontology_mapping.get("platform_refs", {})
    max_entities_per_signal = int((dedupe_config or {}).get("max_entities_per_signal", 3))

    for signal in signals:
        resolution = resolve_entities(
            signal,
            watchlists,
            ontology_mapping,
            max_entities_per_signal=max_entities_per_signal,
        )
        matched_watchlists = resolution.matched_watchlists
        topic_tags = tag_topics(signal, matched_watchlists, ontology_mapping)
        entity_refs = set(signal.entity_refs)
        source_refs = set(signal.source_refs)
        platform_refs = set(signal.platform_refs)

        for watchlist in matched_watchlists:
            entity_refs.update(watchlist.entity_refs or [watchlist.id])
            source_refs.update(watchlist.source_refs)

        entity_refs.update(resolution.canonical_entity_refs)

        for platform_ref, config in platform_mapping.items():
            synonyms = config.get("synonyms", []) if isinstance(config, dict) else []
            if platform_ref in signal.platform_refs:
                platform_refs.add(platform_ref)
            if any(str(synonym).lower() in signal.title.lower() for synonym in synonyms):
                platform_refs.add(platform_ref)
            if signal.source_name and any(str(synonym).lower() in signal.source_name.lower() for synonym in synonyms):
                platform_refs.add(platform_ref)

        if signal.platform_refs:
            platform_refs.update(signal.platform_refs)

        projected.append(
            signal.model_copy(
                update={
                    "entity_refs": sorted(entity_refs),
                    "raw_entity_hits": resolution.raw_entity_hits,
                    "canonical_entity_refs": resolution.canonical_entity_refs,
                    "topic_tags": topic_tags,
                    "source_refs": sorted(source_refs),
                    "platform_refs": sorted(platform_refs),
                }
            )
        )

    return projected
