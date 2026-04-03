from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from apps.intel_hub.compiler.dedupe import cluster_signals, stable_card_id
from apps.intel_hub.schemas.cards import OpportunityCard
from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.ontology_mapping_model import XHSOntologyMapping
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
from apps.intel_hub.schemas.signal import Signal
from apps.intel_hub.schemas.xhs_signals import SceneSignals, SellingThemeSignals, VisualSignals

logger = logging.getLogger(__name__)


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
                target_roles=_infer_opportunity_roles(bucket),
                opportunity_type=_infer_opportunity_type(bucket),
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


def _infer_opportunity_type(bucket: list[Signal]) -> str | None:
    from apps.intel_hub.schemas.enums import OpportunityType
    has_style = any(s.style_refs for s in bucket)
    has_need = any(s.need_refs for s in bucket)
    has_visual = any(s.visual_pattern_refs for s in bucket)
    has_content = any(s.content_pattern_refs for s in bucket)
    if has_need:
        return OpportunityType.DEMAND
    if has_style:
        return OpportunityType.TREND
    if has_visual:
        return OpportunityType.VISUAL
    if has_content:
        return OpportunityType.CONTENT
    return OpportunityType.PRODUCT


def _infer_opportunity_roles(bucket: list[Signal]) -> list[str]:
    from apps.intel_hub.schemas.enums import TargetRole
    roles: set[str] = {TargetRole.CEO.value}
    if any(s.need_refs or s.material_refs for s in bucket):
        roles.add(TargetRole.PRODUCT_DIRECTOR.value)
    if any(s.content_pattern_refs or s.audience_refs for s in bucket):
        roles.add(TargetRole.MARKETING_DIRECTOR.value)
    if any(s.visual_pattern_refs or s.style_refs for s in bucket):
        roles.add(TargetRole.VISUAL_DIRECTOR.value)
    return sorted(roles)


# ── XHS 三维结构化专用编译器 ──────────────────────────────


def compile_xhs_opportunities(
    mapping: XHSOntologyMapping,
    visual: VisualSignals,
    selling: SellingThemeSignals,
    scene: SceneSignals,
    rules: dict[str, Any],
) -> list[XHSOpportunityCard]:
    """根据三维信号 + 本体映射 + 规则配置生成 XHS 机会卡。"""
    cards: list[XHSOpportunityCard] = []
    note_id = mapping.note_id

    visual_card = _try_visual_opportunity(mapping, visual, rules.get("visual_opportunity", {}), note_id)
    if visual_card:
        cards.append(visual_card)

    selling_card = _try_selling_theme_opportunity(mapping, selling, rules.get("selling_theme_opportunity", {}), note_id)
    if selling_card:
        cards.append(selling_card)

    scene_card = _try_scene_opportunity(mapping, scene, rules.get("scene_opportunity", {}), note_id)
    if scene_card:
        cards.append(scene_card)

    return cards


def _try_visual_opportunity(
    mapping: XHSOntologyMapping,
    visual: VisualSignals,
    rule: dict[str, Any],
    note_id: str,
) -> XHSOpportunityCard | None:
    trigger = rule.get("trigger", {})
    min_style = trigger.get("min_style_signals", 1)
    min_expr = trigger.get("min_expression_or_feature", 1)
    max_misleading = trigger.get("max_misleading_risk", 2)

    if len(visual.visual_style_signals) < min_style:
        return None
    if len(visual.visual_expression_pattern) + len(visual.visual_feature_highlights) < min_expr:
        return None
    if len(visual.visual_misleading_risk) > max_misleading:
        return None

    conf = rule.get("base_confidence", 0.55)
    boost = rule.get("confidence_boost", {})
    if visual.visual_composition_type:
        conf += boost.get("has_composition", 0.1)
    if visual.visual_color_palette:
        conf += boost.get("has_color_palette", 0.05)
    if visual.visual_texture_signals:
        conf += boost.get("has_texture", 0.05)
    conf = min(conf, 0.95)

    styles = ", ".join(visual.visual_style_signals[:3])
    expressions = ", ".join(visual.visual_expression_pattern[:2])
    title = f"视觉差异化机会: {styles}"
    summary = f"笔记展现 {styles} 视觉风格"
    if expressions:
        summary += f"，表达模式: {expressions}"
    if visual.visual_composition_type:
        summary += f"，构图: {', '.join(visual.visual_composition_type[:2])}"

    return XHSOpportunityCard(
        title=title,
        summary=summary,
        opportunity_type="visual",
        entity_refs=mapping.category_refs,
        scene_refs=mapping.scene_refs,
        style_refs=mapping.style_refs,
        need_refs=mapping.need_refs,
        risk_refs=mapping.risk_refs,
        visual_pattern_refs=mapping.visual_pattern_refs,
        evidence_refs=visual.evidence_refs,
        confidence=round(conf, 3),
        suggested_next_step=rule.get("suggested_next_step", "评估视觉资产复用价值"),
        source_note_ids=[note_id],
    )


def _try_selling_theme_opportunity(
    mapping: XHSOntologyMapping,
    selling: SellingThemeSignals,
    rule: dict[str, Any],
    note_id: str,
) -> XHSOpportunityCard | None:
    trigger = rule.get("trigger", {})
    min_sp = trigger.get("min_selling_points", 1)
    require_validated = trigger.get("require_validated_or_purchase_intent", True)
    max_challenges = trigger.get("max_challenges", 3)

    if len(selling.selling_point_signals) < min_sp:
        return None
    if require_validated and not selling.validated_selling_points and not selling.purchase_intent_signals:
        return None
    if len(selling.selling_point_challenges) > max_challenges:
        return None

    conf = rule.get("base_confidence", 0.5)
    boost = rule.get("confidence_boost", {})
    if selling.validated_selling_points:
        conf += boost.get("has_validated", 0.15)
    if selling.purchase_intent_signals:
        conf += boost.get("has_purchase_intent", 0.1)
    if selling.selling_theme_refs:
        conf += boost.get("has_theme_ref", 0.05)
    conf = min(conf, 0.95)

    op_types = rule.get("opportunity_types", {})
    if selling.purchase_intent_signals:
        op_type = op_types.get("with_purchase_intent", "demand")
    elif selling.selling_theme_refs:
        op_type = op_types.get("with_theme_ref", "content")
    else:
        op_type = op_types.get("selling_points_only", "product")

    sp_str = ", ".join(selling.selling_point_signals[:3])
    title = f"卖点机会: {sp_str}"
    summary = f"卖点: {sp_str}"
    if selling.validated_selling_points:
        summary += f"（评论验证: {', '.join(selling.validated_selling_points[:2])}）"
    if selling.purchase_intent_signals:
        summary += f"；购买意向: {', '.join(selling.purchase_intent_signals[:2])}"

    return XHSOpportunityCard(
        title=title,
        summary=summary,
        opportunity_type=op_type,
        entity_refs=mapping.category_refs,
        scene_refs=mapping.scene_refs,
        style_refs=mapping.style_refs,
        need_refs=mapping.need_refs,
        risk_refs=mapping.risk_refs,
        visual_pattern_refs=mapping.visual_pattern_refs,
        evidence_refs=selling.evidence_refs,
        confidence=round(conf, 3),
        suggested_next_step=rule.get("suggested_next_step", "验证卖点市场渗透率"),
        source_note_ids=[note_id],
    )


def _try_scene_opportunity(
    mapping: XHSOntologyMapping,
    scene: SceneSignals,
    rule: dict[str, Any],
    note_id: str,
) -> XHSOpportunityCard | None:
    trigger = rule.get("trigger", {})
    min_scenes = trigger.get("min_scenes", 1)
    min_goals = trigger.get("min_goals", 1)
    min_combos = trigger.get("min_combos", 1)

    if len(scene.scene_signals) < min_scenes:
        return None
    if len(scene.scene_goal_signals) < min_goals:
        return None
    if len(scene.scene_style_value_combos) < min_combos:
        return None

    conf = rule.get("base_confidence", 0.5)
    boost = rule.get("confidence_boost", {})
    if scene.audience_signals:
        conf += boost.get("has_audience", 0.1)
    if scene.scene_constraints:
        conf += boost.get("has_constraints", 0.05)
    combo_bonus = boost.get("combo_count_bonus_per", 0.02)
    conf += min(len(scene.scene_style_value_combos), 5) * combo_bonus
    conf = min(conf, 0.95)

    sc_str = ", ".join(scene.scene_signals[:3])
    goal_str = ", ".join(scene.scene_goal_signals[:2])
    title = f"场景机会: {sc_str}"
    summary = f"场景: {sc_str}，目标: {goal_str}"
    if scene.scene_style_value_combos:
        summary += f"；组合: {', '.join(scene.scene_style_value_combos[:3])}"

    return XHSOpportunityCard(
        title=title,
        summary=summary,
        opportunity_type="scene",
        entity_refs=mapping.category_refs,
        scene_refs=mapping.scene_refs,
        style_refs=mapping.style_refs,
        need_refs=mapping.need_refs,
        risk_refs=mapping.risk_refs,
        visual_pattern_refs=mapping.visual_pattern_refs,
        evidence_refs=scene.evidence_refs,
        confidence=round(conf, 3),
        suggested_next_step=rule.get("suggested_next_step", "评估细分赛道竞品覆盖度"),
        source_note_ids=[note_id],
    )
