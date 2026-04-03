"""VisualPatternAsset 编译器 — 从信号中提炼视觉模式资产。

聚焦 visual_pattern_refs 和 style_refs 维度，
编译出可供视觉总监消费的视觉表达模式资产。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apps.intel_hub.compiler.dedupe import cluster_signals, stable_card_id
from apps.intel_hub.schemas.cards import VisualPatternAsset
from apps.intel_hub.schemas.enums import TargetRole
from apps.intel_hub.schemas.signal import Signal


def compile_visual_pattern_assets(
    signals: list[Signal],
    ontology_mapping: dict[str, Any],
    dedupe_config: dict[str, Any] | None = None,
) -> list[VisualPatternAsset]:
    eligible_topics = set(
        ontology_mapping.get("card_compiler", {}).get("visual_pattern_topics", [])
    )
    eligible = [
        s for s in signals
        if eligible_topics.intersection(s.topic_tags)
        and (s.visual_pattern_refs or s.style_refs)
    ]
    clusters = cluster_signals(eligible, eligible_topics, dedupe_config)
    compiled_at = datetime.now(UTC).isoformat()
    assets: list[VisualPatternAsset] = []

    for cluster in clusters:
        bucket = cluster.signals
        all_visual = sorted({r for s in bucket for r in s.visual_pattern_refs})
        all_scene = sorted({r for s in bucket for r in s.scene_refs})
        all_style = sorted({r for s in bucket for r in s.style_refs})
        all_risks = sorted({r for s in bucket for r in s.risk_factor_refs})

        pattern_name = all_visual[0] if all_visual else (all_style[0] if all_style else cluster.primary_entity)

        avg_engagement = 0.0
        engagement_count = 0
        for s in bucket:
            eng = s.metrics.get("engagement", 0)
            if isinstance(eng, (int, float)) and eng > 0:
                avg_engagement += float(eng)
                engagement_count += 1
        if engagement_count > 0:
            avg_engagement /= engagement_count

        click_potential = min(1.0, avg_engagement / 2000) if avg_engagement > 0 else 0.0

        assets.append(
            VisualPatternAsset(
                id=stable_card_id("visual_pattern", cluster.dedupe_key),
                title=f"视觉模式: {pattern_name}",
                summary=_build_summary(bucket, all_visual, all_style, all_scene),
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
                    TargetRole.VISUAL_DIRECTOR.value,
                    TargetRole.MARKETING_DIRECTOR.value,
                ],
                pattern_name=pattern_name,
                description=f"基于 {len(bucket)} 条信号提炼的视觉表达模式",
                applicable_scene_refs=all_scene,
                applicable_style_refs=all_style,
                supporting_note_ids=[s.raw_payload.get("note_id", s.id) for s in bucket if s.raw_payload],
                click_potential=round(click_potential, 3),
                misuse_risks=[r for r in all_risks if "visual" in r or "misleading" in r],
            )
        )
    return assets


def _build_summary(
    bucket: list[Signal],
    visual_refs: list[str],
    style_refs: list[str],
    scene_refs: list[str],
) -> str:
    parts: list[str] = []
    if visual_refs:
        parts.append(f"视觉模式: {', '.join(visual_refs[:3])}")
    if style_refs:
        parts.append(f"风格: {', '.join(style_refs[:3])}")
    if scene_refs:
        parts.append(f"场景: {', '.join(scene_refs[:3])}")
    parts.append(f"基于 {len(bucket)} 条信号")
    return " | ".join(parts)
