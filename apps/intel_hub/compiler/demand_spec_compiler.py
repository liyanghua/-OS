"""DemandSpecAsset 编译器 — 从信号中提炼需求规格资产。

聚焦 need_refs / material_refs / risk_factor_refs 维度，
编译出可供产品总监消费的需求定义资产。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apps.intel_hub.compiler.dedupe import cluster_signals, stable_card_id
from apps.intel_hub.schemas.cards import DemandSpecAsset
from apps.intel_hub.schemas.enums import TargetRole
from apps.intel_hub.schemas.signal import Signal


def compile_demand_spec_assets(
    signals: list[Signal],
    ontology_mapping: dict[str, Any],
    dedupe_config: dict[str, Any] | None = None,
) -> list[DemandSpecAsset]:
    eligible_topics = set(
        ontology_mapping.get("card_compiler", {}).get("demand_spec_topics", [])
    )
    eligible = [
        s for s in signals
        if eligible_topics.intersection(s.topic_tags)
        and (s.need_refs or s.material_refs)
    ]
    clusters = cluster_signals(eligible, eligible_topics, dedupe_config)
    compiled_at = datetime.now(UTC).isoformat()
    assets: list[DemandSpecAsset] = []

    for cluster in clusters:
        bucket = cluster.signals
        all_needs = sorted({r for s in bucket for r in s.need_refs})
        all_materials = sorted({r for s in bucket for r in s.material_refs})
        all_categories = sorted({r for s in bucket for r in s.entity_refs if r.startswith("category_")})
        all_audiences = sorted({r for s in bucket for r in s.audience_refs})
        all_scenes = sorted({r for s in bucket for r in s.scene_refs})
        all_risks = sorted({r for s in bucket for r in s.risk_factor_refs})

        required_features = all_needs[:5]
        optional_features = all_materials[:3]
        risk_constraints = all_risks[:3]

        demand_name = all_needs[0] if all_needs else cluster.primary_entity

        assets.append(
            DemandSpecAsset(
                id=stable_card_id("demand_spec", cluster.dedupe_key),
                title=f"需求规格: {demand_name}",
                summary=_build_summary(bucket, all_needs, all_materials, all_risks),
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
                target_roles=[
                    TargetRole.PRODUCT_DIRECTOR.value,
                    TargetRole.CEO.value,
                ],
                demand_name=demand_name,
                target_category_refs=all_categories,
                target_audience_refs=all_audiences,
                target_scene_refs=all_scenes,
                required_features=required_features,
                optional_features=optional_features,
                risk_constraints=risk_constraints,
            )
        )
    return assets


def _build_summary(
    bucket: list[Signal],
    need_refs: list[str],
    material_refs: list[str],
    risk_refs: list[str],
) -> str:
    parts: list[str] = []
    if need_refs:
        parts.append(f"核心需求: {', '.join(need_refs[:3])}")
    if material_refs:
        parts.append(f"材质: {', '.join(material_refs[:3])}")
    if risk_refs:
        parts.append(f"风险约束: {', '.join(risk_refs[:3])}")
    parts.append(f"基于 {len(bucket)} 条信号")
    return " | ".join(parts)
