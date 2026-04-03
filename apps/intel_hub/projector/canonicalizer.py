from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.intel_hub.schemas.watchlist import Watchlist


PUNCTUATION_RE = re.compile(r"[\-_/|,:;()\[\]{}]+")
SPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class CanonicalizationResult:
    canonical_entity_refs: list[str]
    raw_entity_hits: list[str]
    matched_watchlist_ids: list[str]


def normalize_lookup_text(text: str) -> str:
    lowered = text.lower().strip()
    lowered = PUNCTUATION_RE.sub(" ", lowered)
    return SPACE_RE.sub(" ", lowered).strip()


def canonicalize_entities(
    text: str,
    watchlists: list[Watchlist],
    ontology_mapping: dict[str, object],
    *,
    max_entities_per_signal: int = 3,
) -> CanonicalizationResult:
    normalized_text = normalize_lookup_text(text)
    entity_catalog = _build_entity_catalog(watchlists, ontology_mapping)

    if not normalized_text or not entity_catalog:
        return CanonicalizationResult([], [], [])

    matches: list[dict[str, object]] = []
    raw_hits: list[str] = []

    for canonical_id, config in entity_catalog.items():
        aliases = config.get("aliases", [])
        matched_aliases = [alias for alias in aliases if alias and alias in normalized_text]
        if not matched_aliases:
            continue
        raw_hits.extend(matched_aliases)
        matches.append(
            {
                "canonical_id": canonical_id,
                "entity_type": config.get("entity_type", "generic"),
                "watchlist_ids": config.get("watchlist_ids", []),
                "priority": config.get("priority", 0.5),
                "match_score": max(len(alias) for alias in matched_aliases),
            }
        )

    ranked_matches = sorted(
        matches,
        key=lambda item: (
            float(item["match_score"]),
            float(item["priority"]),
            str(item["canonical_id"]),
        ),
        reverse=True,
    )

    selected: list[str] = []
    selected_watchlists: list[str] = []
    seen_types: set[str] = set()
    for match in ranked_matches:
        entity_type = str(match["entity_type"])
        if entity_type in seen_types:
            continue
        selected.append(str(match["canonical_id"]))
        seen_types.add(entity_type)
        for watchlist_id in match["watchlist_ids"]:
            if watchlist_id not in selected_watchlists:
                selected_watchlists.append(str(watchlist_id))
        if len(selected) >= max_entities_per_signal:
            break

    deduped_raw_hits = list(OrderedDict.fromkeys(raw_hits))
    return CanonicalizationResult(selected, deduped_raw_hits, selected_watchlists)


def _build_entity_catalog(watchlists: list[Watchlist], ontology_mapping: dict[str, object]) -> dict[str, dict[str, object]]:
    ontology_entities = ontology_mapping.get("entities", {})
    watchlists_by_id = {watchlist.id: watchlist for watchlist in watchlists}
    catalog: dict[str, dict[str, object]] = {}

    if isinstance(ontology_entities, dict):
        for canonical_id, config in ontology_entities.items():
            if not isinstance(config, dict):
                continue
            watchlist_ids = [str(item) for item in config.get("watchlist_ids", [])]
            aliases = [str(alias) for alias in config.get("aliases", [])]
            for watchlist_id in watchlist_ids:
                watchlist = watchlists_by_id.get(watchlist_id)
                if watchlist is None:
                    continue
                aliases.extend([watchlist.title, *watchlist.keywords, *watchlist.aliases])
            catalog[str(canonical_id)] = {
                "entity_type": str(config.get("entity_type", "generic")),
                "watchlist_ids": watchlist_ids,
                "aliases": _normalize_aliases(aliases),
                "priority": max(
                    [float(watchlists_by_id[watchlist_id].priority) for watchlist_id in watchlist_ids if watchlist_id in watchlists_by_id]
                    or [0.5]
                ),
            }

    for watchlist in watchlists:
        canonical_id = watchlist.entity_refs[0] if watchlist.entity_refs else watchlist.id
        catalog.setdefault(
            canonical_id,
            {
                "entity_type": str(watchlist.watchlist_type),
                "watchlist_ids": [watchlist.id],
                "aliases": _normalize_aliases([watchlist.title, *watchlist.keywords, *watchlist.aliases]),
                "priority": float(watchlist.priority),
            },
        )

    return catalog


def _normalize_aliases(aliases: list[str]) -> list[str]:
    normalized = [normalize_lookup_text(alias) for alias in aliases if normalize_lookup_text(alias)]
    return list(OrderedDict.fromkeys(normalized))
