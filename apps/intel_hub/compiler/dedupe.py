from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from apps.intel_hub.projector.canonicalizer import normalize_lookup_text
from apps.intel_hub.schemas.signal import Signal


TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


@dataclass(slots=True)
class DedupeCluster:
    primary_entity: str
    primary_topic: str
    window_bucket: int
    dedupe_key: str
    signals: list[Signal]
    merged_signal_ids: list[str]
    merged_evidence_refs: list[str]


def cluster_signals(
    signals: list[Signal],
    eligible_topics: set[str],
    dedupe_config: dict[str, object] | None = None,
) -> list[DedupeCluster]:
    config = dedupe_config or {}
    merge_window_hours = int(config.get("merge_window_hours", 72))
    title_token_overlap_threshold = float(config.get("title_token_overlap_threshold", 0.6))
    minimum_evidence_count = int(config.get("minimum_evidence_count", 1))
    max_cards = int(config.get("max_cards_per_entity_topic_window", 3))

    pregrouped: dict[tuple[str, str, int], list[Signal]] = defaultdict(list)
    for signal in signals:
        primary_entity = (signal.canonical_entity_refs or signal.entity_refs or ["market"])[0]
        primary_topic = next((tag for tag in signal.topic_tags if tag in eligible_topics), signal.topic_tags[0] if signal.topic_tags else "general")
        window_bucket = _window_bucket(signal.timestamps.get("published_at"), merge_window_hours)
        pregrouped[(primary_entity, primary_topic, window_bucket)].append(signal)

    clusters: list[DedupeCluster] = []
    for (primary_entity, primary_topic, window_bucket), bucket in pregrouped.items():
        local_clusters: list[list[Signal]] = []
        for signal in sorted(bucket, key=lambda item: (_sort_timestamp(item.timestamps.get("published_at")), item.id)):
            placed = False
            for cluster in local_clusters:
                if _should_merge(signal, cluster, title_token_overlap_threshold):
                    cluster.append(signal)
                    placed = True
                    break
            if not placed:
                local_clusters.append([signal])

        ranked_clusters = sorted(
            local_clusters,
            key=lambda cluster: (
                len({evidence_id for signal in cluster for evidence_id in signal.evidence_refs}),
                round(sum(signal.business_priority_score for signal in cluster) / len(cluster), 4),
            ),
            reverse=True,
        )

        for cluster in ranked_clusters[:max_cards]:
            merged_evidence_refs = sorted({ref for signal in cluster for ref in signal.evidence_refs})
            if len(merged_evidence_refs) < minimum_evidence_count:
                continue
            dedupe_key = _build_dedupe_key(primary_entity, primary_topic, window_bucket, cluster)
            merged_signal_ids = [signal.id for signal in sorted(cluster, key=lambda item: (_sort_timestamp(item.timestamps.get("published_at")), item.id))]
            clusters.append(
                DedupeCluster(
                    primary_entity=primary_entity,
                    primary_topic=primary_topic,
                    window_bucket=window_bucket,
                    dedupe_key=dedupe_key,
                    signals=cluster,
                    merged_signal_ids=merged_signal_ids,
                    merged_evidence_refs=merged_evidence_refs,
                )
            )
    return clusters


def stable_card_id(prefix: str, dedupe_key: str) -> str:
    return f"{prefix}_{hashlib.sha1(dedupe_key.encode('utf-8')).hexdigest()[:12]}"


def _should_merge(signal: Signal, cluster: list[Signal], threshold: float) -> bool:
    candidate_tokens = _title_tokens(signal.title)
    if not candidate_tokens:
        return False
    representative_tokens = _title_tokens(cluster[0].title)
    overlap = _token_overlap(candidate_tokens, representative_tokens)
    return overlap >= threshold or normalize_lookup_text(signal.title) == normalize_lookup_text(cluster[0].title)


def _title_tokens(title: str) -> set[str]:
    normalized = normalize_lookup_text(title)
    return {token for token in TOKEN_RE.findall(normalized) if len(token) >= 2}


def _token_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = left & right
    return len(intersection) / min(len(left), len(right))


def _build_dedupe_key(primary_entity: str, primary_topic: str, window_bucket: int, cluster: list[Signal]) -> str:
    token_pool = sorted({token for signal in cluster for token in _title_tokens(signal.title)})
    title_signature = "-".join(token_pool[:6]) or "untitled"
    return f"{primary_entity}|{primary_topic}|{window_bucket}|{title_signature}"


def _window_bucket(published_at: str | None, merge_window_hours: int) -> int:
    if not published_at:
        return 0
    parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00")).astimezone(UTC)
    return int(parsed.timestamp() // (merge_window_hours * 3600))


def _sort_timestamp(value: str | None) -> str:
    return value or ""
