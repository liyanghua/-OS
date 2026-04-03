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
                target_roles=_infer_risk_roles(bucket),
                risk_type=_infer_risk_type(bucket),
                severity=_infer_severity(bucket),
                suggested_mitigations=_build_mitigations(bucket),
                business_priority_score=round(
                    sum(signal.business_priority_score for signal in bucket) / len(bucket),
                    4,
                ),
            )
        )
    return cards


def _infer_risk_type(bucket: list[Signal]) -> str | None:
    from apps.intel_hub.schemas.enums import RiskType
    has_visual_risk = any(
        any("visual" in r or "misleading" in r for r in s.risk_factor_refs)
        for s in bucket
    )
    has_product_risk = any(
        any("edge" in r or "size" in r or "clean" in r or "cheap" in r for r in s.risk_factor_refs)
        for s in bucket
    )
    if has_visual_risk:
        return RiskType.VISUAL
    if has_product_risk:
        return RiskType.PRODUCT
    return RiskType.PERCEPTION


def _infer_risk_roles(bucket: list[Signal]) -> list[str]:
    from apps.intel_hub.schemas.enums import TargetRole
    roles: set[str] = {TargetRole.CEO.value}
    if any(s.risk_factor_refs for s in bucket):
        roles.add(TargetRole.PRODUCT_DIRECTOR.value)
    if any(s.visual_pattern_refs or s.style_refs for s in bucket):
        roles.add(TargetRole.VISUAL_DIRECTOR.value)
    if any(s.content_pattern_refs or s.audience_refs for s in bucket):
        roles.add(TargetRole.MARKETING_DIRECTOR.value)
    return sorted(roles)


def _infer_severity(bucket: list[Signal]) -> str:
    avg_score = sum(s.business_priority_score for s in bucket) / max(len(bucket), 1)
    if avg_score >= 0.7:
        return "high"
    if avg_score >= 0.4:
        return "medium"
    return "low"


def _build_mitigations(bucket: list[Signal]) -> list[str]:
    risk_refs = {r for s in bucket for r in s.risk_factor_refs}
    mitigations: list[str] = []
    if any("edge" in r or "curl" in r for r in risk_refs):
        mitigations.append("产品端优化边缘工艺或增加防卷边设计")
    if any("cheap" in r or "texture" in r for r in risk_refs):
        mitigations.append("升级材质或优化包装提升质感认知")
    if any("size" in r for r in risk_refs):
        mitigations.append("完善尺寸选购指南并强化详情页尺寸说明")
    if any("visual" in r or "misleading" in r for r in risk_refs):
        mitigations.append("拍摄规范中增加实物还原度要求")
    if any("clean" in r for r in risk_refs):
        mitigations.append("增加清洁保养说明与使用场景引导")
    if not mitigations:
        mitigations.append("持续监控相关用户反馈并评估影响范围")
    return mitigations
