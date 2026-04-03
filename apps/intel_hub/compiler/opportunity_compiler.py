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
    cross_modal: Any | None = None,
) -> list[XHSOpportunityCard]:
    """根据三维信号 + 本体映射 + 规则配置 + 跨模态校验生成 XHS 机会卡。"""
    cards: list[XHSOpportunityCard] = []
    note_id = mapping.note_id

    visual_card = _try_visual_opportunity(mapping, visual, rules.get("visual_opportunity", {}), note_id, cross_modal)
    if visual_card:
        cards.append(visual_card)

    selling_card = _try_selling_theme_opportunity(mapping, selling, rules.get("selling_theme_opportunity", {}), note_id, cross_modal)
    if selling_card:
        cards.append(selling_card)

    scene_card = _try_scene_opportunity(mapping, scene, rules.get("scene_opportunity", {}), note_id, cross_modal)
    if scene_card:
        cards.append(scene_card)

    cards = merge_opportunities(cards, rules.get("merge_rules", {}))
    return cards


def merge_opportunities(
    cards: list[XHSOpportunityCard],
    merge_rules: dict[str, Any] | None = None,
) -> list[XHSOpportunityCard]:
    """按 opportunity_type + scene_refs + need_refs 去重，合并 evidence_refs。"""
    if not cards or len(cards) <= 1:
        return cards

    max_cards = (merge_rules or {}).get("max_cards_per_note", 5)
    seen_keys: set[str] = set()
    deduped: list[XHSOpportunityCard] = []

    for card in cards:
        key = f"{card.opportunity_type}|{'_'.join(sorted(card.scene_refs[:3]))}|{'_'.join(sorted(card.need_refs[:3]))}"
        if key in seen_keys:
            for existing in deduped:
                existing_key = f"{existing.opportunity_type}|{'_'.join(sorted(existing.scene_refs[:3]))}|{'_'.join(sorted(existing.need_refs[:3]))}"
                if existing_key == key:
                    existing_ev_ids = {e.evidence_id for e in existing.evidence_refs}
                    for ev in card.evidence_refs:
                        if ev.evidence_id not in existing_ev_ids:
                            existing.evidence_refs.append(ev)
                    existing.source_note_ids = list(set(existing.source_note_ids + card.source_note_ids))
                    break
        else:
            seen_keys.add(key)
            deduped.append(card)

    return deduped[:max_cards]


def _common_card_fields(mapping: XHSOntologyMapping, note_id: str) -> dict[str, Any]:
    return {
        "entity_refs": mapping.category_refs,
        "scene_refs": mapping.scene_refs,
        "style_refs": mapping.style_refs,
        "need_refs": mapping.need_refs,
        "risk_refs": mapping.risk_refs,
        "visual_pattern_refs": mapping.visual_pattern_refs,
        "content_pattern_refs": mapping.content_pattern_refs,
        "value_proposition_refs": mapping.value_proposition_refs,
        "audience_refs": mapping.audience_refs,
        "source_note_ids": [note_id],
    }


def _try_visual_opportunity(
    mapping: XHSOntologyMapping,
    visual: VisualSignals,
    rule: dict[str, Any],
    note_id: str,
    cross_modal: Any | None = None,
) -> XHSOpportunityCard | None:
    trigger = rule.get("trigger", {})
    min_style = trigger.get("min_style_signals", 1)
    min_expr = trigger.get("min_expression_or_feature", 1)
    max_misleading = trigger.get("max_misleading_risk", 2)
    max_risk_score = trigger.get("max_visual_risk_score", 0.5)

    if len(visual.visual_style_signals) < min_style:
        return None
    if len(visual.visual_expression_pattern) + len(visual.visual_feature_highlights) < min_expr:
        return None
    if len(visual.visual_misleading_risk) > max_misleading:
        return None
    if visual.visual_risk_score is not None and visual.visual_risk_score > max_risk_score:
        return None

    conf = rule.get("base_confidence", 0.55)
    boost = rule.get("confidence_boost", {})
    if visual.visual_composition_type:
        conf += boost.get("has_composition", 0.1)
    if visual.visual_color_palette:
        conf += boost.get("has_color_palette", 0.05)
    if visual.visual_texture_signals:
        conf += boost.get("has_texture", 0.05)
    if visual.click_differentiation_score is not None and visual.click_differentiation_score > 0.2:
        conf += boost.get("click_diff_bonus", 0.1)
    conf = min(conf, 0.95)

    styles = ", ".join(visual.visual_style_signals[:3])
    scenes = ", ".join(mapping.scene_refs[:2]) if mapping.scene_refs else ""
    title = f"视觉差异化: {styles}"
    if scenes:
        title += f" × {scenes}"

    summary = f"笔记展现 {styles} 视觉风格"
    if visual.visual_composition_type:
        summary += f"，构图: {', '.join(visual.visual_composition_type[:2])}"
    if visual.visual_differentiation_points:
        summary += f"，差异化: {', '.join(visual.visual_differentiation_points[:2])}"

    next_steps = rule.get("suggested_next_step", ["评估视觉资产复用价值"])
    if isinstance(next_steps, str):
        next_steps = [next_steps]

    return XHSOpportunityCard(
        title=title,
        summary=summary,
        opportunity_type="visual",
        evidence_refs=visual.evidence_refs,
        confidence=round(conf, 3),
        suggested_next_step=next_steps,
        **_common_card_fields(mapping, note_id),
    )


def _try_selling_theme_opportunity(
    mapping: XHSOntologyMapping,
    selling: SellingThemeSignals,
    rule: dict[str, Any],
    note_id: str,
    cross_modal: Any | None = None,
) -> XHSOpportunityCard | None:
    trigger = rule.get("trigger", {})
    min_sp = trigger.get("min_selling_points", 1)
    require_validated = trigger.get("require_validated_or_purchase_intent", True)
    max_challenges = trigger.get("max_challenges", 3)
    max_unsupported_ratio = trigger.get("max_unsupported_ratio", 0.7)

    all_sp = selling.selling_point_signals or (selling.primary_selling_points + selling.secondary_selling_points)
    if len(all_sp) < min_sp:
        return None
    if require_validated and not selling.validated_selling_points and not selling.purchase_intent_signals:
        return None
    if len(selling.selling_point_challenges) > max_challenges:
        return None

    if cross_modal is not None and all_sp:
        unsupported = getattr(cross_modal, "unsupported_claims", [])
        if len(unsupported) / max(len(all_sp), 1) > max_unsupported_ratio:
            return None

    conf = rule.get("base_confidence", 0.5)
    boost = rule.get("confidence_boost", {})
    if selling.validated_selling_points:
        conf += boost.get("has_validated", 0.15)
    if selling.purchase_intent_signals:
        conf += boost.get("has_purchase_intent", 0.1)
    if selling.selling_theme_refs:
        conf += boost.get("has_theme_ref", 0.05)

    if cross_modal is not None:
        unsupported = getattr(cross_modal, "unsupported_claims", [])
        challenged = getattr(cross_modal, "challenged_claims", [])
        if not unsupported and not challenged:
            conf += boost.get("low_unsupported_bonus", 0.05)

    conf = min(conf, 0.95)

    op_types = rule.get("opportunity_types", {})
    if selling.purchase_intent_signals:
        op_type = op_types.get("with_purchase_intent", "demand")
    elif selling.selling_theme_refs:
        op_type = op_types.get("with_theme_ref", "content")
    else:
        op_type = op_types.get("selling_points_only", "product")

    validated_str = ", ".join(selling.validated_selling_points[:3]) if selling.validated_selling_points else ""
    sp_str = ", ".join(all_sp[:3])

    title = f"卖点主题: {sp_str}"
    if validated_str:
        total = len(all_sp)
        validated_n = len(selling.validated_selling_points)
        title += f" (评论验证 {validated_n}/{total})"

    summary = f"核心卖点: {sp_str}"
    if selling.validated_selling_points:
        summary += f"；已验证: {validated_str}"
    if selling.purchase_intent_signals:
        summary += f"；购买意向: {', '.join(selling.purchase_intent_signals[:2])}"
    if selling.selling_point_challenges:
        summary += f"；质疑: {', '.join(selling.selling_point_challenges[:2])}"

    next_steps = rule.get("suggested_next_step", ["验证卖点市场渗透率"])
    if isinstance(next_steps, str):
        next_steps = [next_steps]

    return XHSOpportunityCard(
        title=title,
        summary=summary,
        opportunity_type=op_type,
        evidence_refs=selling.evidence_refs,
        confidence=round(conf, 3),
        suggested_next_step=next_steps,
        **_common_card_fields(mapping, note_id),
    )


def _try_scene_opportunity(
    mapping: XHSOntologyMapping,
    scene: SceneSignals,
    rule: dict[str, Any],
    note_id: str,
    cross_modal: Any | None = None,
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

    if cross_modal is not None:
        alignment = getattr(cross_modal, "scene_alignment", {})
        aligned_count = sum(1 for v in alignment.values() if v is True)
        if aligned_count > 0:
            conf += boost.get("scene_alignment_bonus", 0.1)

    conf = min(conf, 0.95)

    sc_str = ", ".join(scene.scene_signals[:3])
    goal_str = ", ".join(scene.scene_goal_signals[:2])
    combo_sample = scene.scene_style_value_combos[0] if scene.scene_style_value_combos else ""

    title = f"场景机会: {combo_sample}" if combo_sample else f"场景机会: {sc_str}"
    summary = f"场景: {sc_str}，目标: {goal_str}"
    if scene.audience_signals:
        summary += f"，受众: {', '.join(scene.audience_signals[:2])}"
    if scene.scene_constraints:
        summary += f"，约束: {', '.join(scene.scene_constraints[:2])}"

    next_steps = rule.get("suggested_next_step", ["评估细分赛道竞品覆盖度"])
    if isinstance(next_steps, str):
        next_steps = [next_steps]

    return XHSOpportunityCard(
        title=title,
        summary=summary,
        opportunity_type="scene",
        evidence_refs=scene.evidence_refs,
        confidence=round(conf, 3),
        suggested_next_step=next_steps,
        **_common_card_fields(mapping, note_id),
    )
