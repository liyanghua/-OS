from __future__ import annotations

from dataclasses import dataclass

from apps.intel_hub.projector.canonicalizer import canonicalize_entities
from apps.intel_hub.schemas.signal import Signal
from apps.intel_hub.schemas.watchlist import Watchlist


@dataclass(slots=True)
class EntityResolution:
    matched_watchlists: list[Watchlist]
    raw_entity_hits: list[str]
    canonical_entity_refs: list[str]


def resolve_entities(
    signal: Signal,
    watchlists: list[Watchlist],
    ontology_mapping: dict[str, object],
    *,
    max_entities_per_signal: int = 3,
) -> EntityResolution:
    haystack = " ".join(
        [
            signal.title,
            signal.summary,
            signal.raw_text,
            signal.keyword or "",
            signal.source_name or "",
        ]
    )
    canonicalization = canonicalize_entities(
        haystack,
        watchlists,
        ontology_mapping,
        max_entities_per_signal=max_entities_per_signal,
    )
    matched_watchlists = [watchlist for watchlist in watchlists if watchlist.id in canonicalization.matched_watchlist_ids]

    return EntityResolution(
        matched_watchlists=matched_watchlists,
        raw_entity_hits=canonicalization.raw_entity_hits,
        canonical_entity_refs=canonicalization.canonical_entity_refs,
    )
