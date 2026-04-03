from __future__ import annotations

from datetime import UTC, datetime

from apps.intel_hub.compiler.dedupe import cluster_signals, stable_card_id
from apps.intel_hub.compiler.opportunity_compiler import _build_title, _suggested_actions
from apps.intel_hub.schemas.cards import RiskCard
from apps.intel_hub.schemas.signal import Signal


def compile_risk_cards(
    signals: list[Signal],
    ontology_mapping: dict[str, object],
    dedupe_config: dict[str, object] | None = None,
) -> list[RiskCard]:
    eligible_topics = set(ontology_mapping.get("card_compiler", {}).get("risk_topics", []))
    clusters = cluster_signals(
        [signal for signal in signals if eligible_topics.intersection(signal.topic_tags)],
        eligible_topics,
        dedupe_config,
    )

    compiled_at = datetime.now(UTC).isoformat()
    cards: list[RiskCard] = []
    for cluster in clusters:
        bucket = cluster.signals
        cards.append(
            RiskCard(
                id=stable_card_id("risk", cluster.dedupe_key),
                title=_build_title(cluster.primary_entity, cluster.primary_topic, "Risk"),
                summary=" / ".join(signal.summary for signal in bucket[:2] if signal.summary),
                source_refs=sorted({ref for signal in bucket for ref in signal.source_refs}),
                entity_refs=sorted({ref for signal in bucket for ref in signal.entity_refs}),
                topic_tags=sorted({tag for signal in bucket for tag in signal.topic_tags}),
                platform_refs=sorted({ref for signal in bucket for ref in signal.platform_refs}),
                timestamps={
                    "compiled_at": compiled_at,
                    "latest_signal_at": max(signal.timestamps.get("published_at", compiled_at) for signal in bucket),
                },
                confidence=round(sum(signal.confidence for signal in bucket) / len(bucket), 3),
                evidence_refs=sorted({ref for signal in bucket for ref in signal.evidence_refs}),
                trigger_signals=cluster.merged_signal_ids,
                dedupe_key=cluster.dedupe_key,
                merged_signal_ids=cluster.merged_signal_ids,
                merged_evidence_refs=cluster.merged_evidence_refs,
                suggested_actions=_suggested_actions(bucket, is_risk=True),
                impact_hint="优先评估平台规则、合规与流量分发变化对当前 watchlist 的影响。",
                business_priority_score=round(
                    sum(signal.business_priority_score for signal in bucket) / len(bucket),
                    4,
                ),
            )
        )
    return cards
