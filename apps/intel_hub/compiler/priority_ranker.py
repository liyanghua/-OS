from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apps.intel_hub.schemas import Signal


def rank_projected_signals(signals: list[Signal], scoring_config: dict[str, Any]) -> list[Signal]:
    weights = scoring_config.get("weights", {})
    topic_impacts = scoring_config.get("topic_impacts", {})
    ranked: list[Signal] = []

    for signal in signals:
        entity_relevance_score = min(1.0, 0.35 + 0.2 * len(signal.entity_refs))
        business_impact_score = _topic_impact(signal.topic_tags, topic_impacts)
        urgency_score = _urgency_score(signal.timestamps.get("published_at"))
        evidence_strength_score = min(1.0, 0.4 + 0.25 * len(signal.evidence_refs) + (0.15 if signal.source_url else 0.0))
        raw_trending_score = _raw_trending_score(signal.metrics, signal.rank)

        business_priority_score = round(
            entity_relevance_score * float(weights.get("entity_relevance_score", 0.2))
            + business_impact_score * float(weights.get("business_impact_score", 0.25))
            + urgency_score * float(weights.get("urgency_score", 0.2))
            + evidence_strength_score * float(weights.get("evidence_strength_score", 0.15))
            + raw_trending_score * float(weights.get("raw_trending_score", 0.2)),
            4,
        )

        ranked.append(
            signal.model_copy(
                update={
                    "business_priority_score": business_priority_score,
                }
            )
        )

    return ranked


def _topic_impact(topic_tags: list[str], topic_impacts: dict[str, Any]) -> float:
    scores = [float(topic_impacts.get(tag, 0.55)) for tag in topic_tags]
    return round(max(scores or [0.55]), 4)


def _urgency_score(published_at: str | None) -> float:
    if not published_at:
        return 0.45
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(UTC) - published.astimezone(UTC)).total_seconds() / 3600
    except ValueError:
        return 0.45

    if age_hours <= 24:
        return 1.0
    if age_hours <= 72:
        return 0.75
    return 0.4


def _raw_trending_score(metrics: dict[str, Any], rank: int | None) -> float:
    trending_score = metrics.get("trending_score")
    if isinstance(trending_score, (int, float)):
        return round(max(0.3, min(1.0, float(trending_score) / 100)), 4)
    if rank is not None:
        return round(max(0.3, min(1.0, 1 - ((rank - 1) * 0.08))), 4)
    return 0.45
