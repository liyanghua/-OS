"""InsightCard 编译器 — 将跨篇信号聚合为高价值洞察卡。

编译逻辑：
- 按 audience / scene / style 维度聚类
- 融合多篇笔记的 need_refs / risk_factor_refs 形成洞察
- 标记 target_roles
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apps.intel_hub.compiler.dedupe import cluster_signals, stable_card_id
from apps.intel_hub.schemas.cards import InsightCard
from apps.intel_hub.schemas.enums import InsightType, TargetRole
from apps.intel_hub.schemas.signal import Signal


def compile_insight_cards(
    signals: list[Signal],
    ontology_mapping: dict[str, Any],
    dedupe_config: dict[str, Any] | None = None,
) -> list[InsightCard]:
    eligible_topics = set(
        ontology_mapping.get("card_compiler", {}).get("insight_topics", [])
    )
    eligible = [
        s for s in signals
        if eligible_topics.intersection(s.topic_tags)
        and (s.audience_refs or s.scene_refs or s.style_refs)
    ]
    clusters = cluster_signals(eligible, eligible_topics, dedupe_config)
    compiled_at = datetime.now(UTC).isoformat()
    cards: list[InsightCard] = []

    for cluster in clusters:
        bucket = cluster.signals
        insight_type = _infer_insight_type(bucket)
        target_roles = _infer_target_roles(insight_type)

        linked_opps: list[str] = []
        linked_risks: list[str] = []
        for s in bucket:
            if s.need_refs or s.value_proposition_refs:
                linked_opps.extend(s.need_refs)
            if s.risk_factor_refs:
                linked_risks.extend(s.risk_factor_refs)

        cards.append(
            InsightCard(
                id=stable_card_id("insight", cluster.dedupe_key),
                title=_build_title(cluster.primary_entity, insight_type),
                summary=_build_summary(bucket, insight_type),
                source_refs=sorted({r for s in bucket for r in s.source_refs}),
                entity_refs=sorted({r for s in bucket for r in s.entity_refs}),
                topic_tags=sorted({t for s in bucket for t in s.topic_tags}),
                platform_refs=sorted({r for s in bucket for r in s.platform_refs}),
                timestamps={
                    "compiled_at": compiled_at,
                    "latest_signal_at": max(
                        s.timestamps.get("published_at", compiled_at) for s in bucket
                    ),
                },
                confidence=round(sum(s.confidence for s in bucket) / len(bucket), 3),
                evidence_refs=sorted({r for s in bucket for r in s.evidence_refs}),
                trigger_signals=cluster.merged_signal_ids,
                dedupe_key=cluster.dedupe_key,
                merged_signal_ids=cluster.merged_signal_ids,
                merged_evidence_refs=cluster.merged_evidence_refs,
                business_priority_score=round(
                    sum(s.business_priority_score for s in bucket) / len(bucket), 4
                ),
                target_roles=[r.value for r in target_roles],
                insight_type=insight_type,
                linked_opportunities=sorted(set(linked_opps)),
                linked_risks=sorted(set(linked_risks)),
            )
        )
    return cards


def _infer_insight_type(bucket: list[Signal]) -> InsightType:
    audience_count = sum(1 for s in bucket if s.audience_refs)
    scene_count = sum(1 for s in bucket if s.scene_refs)
    style_count = sum(1 for s in bucket if s.style_refs)

    scores = {
        InsightType.AUDIENCE: audience_count,
        InsightType.SCENE: scene_count,
        InsightType.STYLE: style_count,
    }
    return max(scores, key=scores.get)


def _infer_target_roles(insight_type: InsightType) -> list[TargetRole]:
    mapping = {
        InsightType.AUDIENCE: [TargetRole.CEO, TargetRole.MARKETING_DIRECTOR, TargetRole.PRODUCT_DIRECTOR],
        InsightType.SCENE: [TargetRole.CEO, TargetRole.PRODUCT_DIRECTOR],
        InsightType.STYLE: [TargetRole.VISUAL_DIRECTOR, TargetRole.MARKETING_DIRECTOR],
        InsightType.EXPRESSION: [TargetRole.MARKETING_DIRECTOR, TargetRole.VISUAL_DIRECTOR],
        InsightType.CONVERSION: [TargetRole.CEO, TargetRole.MARKETING_DIRECTOR],
    }
    return mapping.get(insight_type, [TargetRole.CEO])


def _build_title(entity: str, insight_type: InsightType) -> str:
    type_labels = {
        InsightType.AUDIENCE: "人群洞察",
        InsightType.SCENE: "场景洞察",
        InsightType.STYLE: "风格洞察",
        InsightType.EXPRESSION: "表达洞察",
        InsightType.CONVERSION: "转化洞察",
    }
    label = type_labels.get(insight_type, "洞察")
    return f"{label}: {entity}"


def _build_summary(bucket: list[Signal], insight_type: InsightType) -> str:
    all_scenes = sorted({r for s in bucket for r in s.scene_refs})
    all_audiences = sorted({r for s in bucket for r in s.audience_refs})
    all_needs = sorted({r for s in bucket for r in s.need_refs})
    all_risks = sorted({r for s in bucket for r in s.risk_factor_refs})

    parts: list[str] = []
    if all_audiences:
        parts.append(f"人群: {', '.join(all_audiences[:3])}")
    if all_scenes:
        parts.append(f"场景: {', '.join(all_scenes[:3])}")
    if all_needs:
        parts.append(f"需求: {', '.join(all_needs[:3])}")
    if all_risks:
        parts.append(f"风险: {', '.join(all_risks[:3])}")
    parts.append(f"基于 {len(bucket)} 条信号")
    return " | ".join(parts)
