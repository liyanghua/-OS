from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apps.intel_hub.compiler.dedupe import cluster_signals, stable_card_id
from apps.intel_hub.schemas.cards import OpportunityCard
from apps.intel_hub.schemas.signal import Signal


def compile_opportunity_cards(
    signals: list[Signal],
    ontology_mapping: dict[str, Any],
    dedupe_config: dict[str, Any] | None = None,
) -> list[OpportunityCard]:
    eligible_topics = set(ontology_mapping.get("card_compiler", {}).get("opportunity_topics", []))
    clusters = cluster_signals(
        [signal for signal in signals if eligible_topics.intersection(signal.topic_tags) and "risk" not in signal.topic_tags],
        eligible_topics,
        dedupe_config,
    )
    compiled_at = datetime.now(UTC).isoformat()
    cards: list[OpportunityCard] = []

    for cluster in clusters:
        bucket = cluster.signals
        cards.append(
            OpportunityCard(
                id=stable_card_id("opportunity", cluster.dedupe_key),
                title=_build_title(cluster.primary_entity, cluster.primary_topic, "Opportunity"),
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
                suggested_actions=_suggested_actions(bucket, is_risk=False),
                impact_hint="关注竞品动作与赛道上行信号，优先转化为 watchlist 驱动的机会研判。",
                business_priority_score=round(
                    sum(signal.business_priority_score for signal in bucket) / len(bucket),
                    4,
                ),
            )
        )
    return cards


def _build_title(entity: str, topic: str, label: str) -> str:
    return f"{label}: {entity} / {topic}"


def _suggested_actions(bucket: list[Signal], is_risk: bool) -> list[str]:
    if is_risk:
        return [
            "核查相关平台规则是否已更新到内部 playbook",
            "为受影响的内容策略补充来源标记与例外预警",
        ]
    return [
        "把该信号加入重点 watchlist 并补充竞争假设",
        "输出一页机会评估，确认是否进入产品/架构优先级讨论",
    ]
