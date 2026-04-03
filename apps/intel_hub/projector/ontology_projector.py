from __future__ import annotations

from typing import Any

from apps.intel_hub.projector.entity_resolver import resolve_entities
from apps.intel_hub.projector.topic_tagger import tag_topics
from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.ontology_mapping_model import XHSOntologyMapping
from apps.intel_hub.schemas.signal import Signal
from apps.intel_hub.schemas.watchlist import Watchlist
from apps.intel_hub.schemas.xhs_signals import SceneSignals, SellingThemeSignals, VisualSignals


def project_signals(
    signals: list[Signal],
    watchlists: list[Watchlist],
    ontology_mapping: dict[str, Any],
    dedupe_config: dict[str, Any] | None = None,
) -> list[Signal]:
    projected: list[Signal] = []
    platform_mapping = ontology_mapping.get("platform_refs", {})
    scenes_mapping = ontology_mapping.get("scenes", {})
    styles_mapping = ontology_mapping.get("styles", {})
    needs_mapping = ontology_mapping.get("needs", {})
    risk_factors_mapping = ontology_mapping.get("risk_factors", {})
    materials_mapping = ontology_mapping.get("materials", {})
    content_patterns_mapping = ontology_mapping.get("content_patterns", {})
    visual_patterns_mapping = ontology_mapping.get("visual_patterns", {})
    audiences_mapping = ontology_mapping.get("audiences", {})
    max_entities_per_signal = int((dedupe_config or {}).get("max_entities_per_signal", 3))

    for signal in signals:
        resolution = resolve_entities(
            signal,
            watchlists,
            ontology_mapping,
            max_entities_per_signal=max_entities_per_signal,
        )
        matched_watchlists = resolution.matched_watchlists
        topic_tags = tag_topics(signal, matched_watchlists, ontology_mapping)
        entity_refs = set(signal.entity_refs)
        source_refs = set(signal.source_refs)
        platform_refs = set(signal.platform_refs)

        for watchlist in matched_watchlists:
            entity_refs.update(watchlist.entity_refs or [watchlist.id])
            source_refs.update(watchlist.source_refs)

        entity_refs.update(resolution.canonical_entity_refs)

        haystack = " ".join([signal.title, signal.summary, signal.raw_text, signal.keyword or ""]).lower()

        scene_refs = set(signal.scene_refs)
        style_refs = set(signal.style_refs)
        need_refs = set(signal.need_refs)
        risk_factor_refs = set(signal.risk_factor_refs)
        material_refs = set(signal.material_refs)
        content_pattern_refs = set(signal.content_pattern_refs)
        visual_pattern_refs = set(signal.visual_pattern_refs)
        audience_refs = set(signal.audience_refs)

        for ref_id, cfg in scenes_mapping.items():
            if isinstance(cfg, dict) and any(kw.lower() in haystack for kw in cfg.get("keywords", [])):
                scene_refs.add(ref_id)
        for ref_id, cfg in styles_mapping.items():
            if isinstance(cfg, dict) and any(kw.lower() in haystack for kw in cfg.get("keywords", [])):
                style_refs.add(ref_id)
        for ref_id, cfg in needs_mapping.items():
            if isinstance(cfg, dict) and any(kw.lower() in haystack for kw in cfg.get("keywords", [])):
                need_refs.add(ref_id)
        for ref_id, cfg in risk_factors_mapping.items():
            if isinstance(cfg, dict) and any(kw.lower() in haystack for kw in cfg.get("keywords", [])):
                risk_factor_refs.add(ref_id)
        for ref_id, cfg in materials_mapping.items():
            if isinstance(cfg, dict) and any(kw.lower() in haystack for kw in cfg.get("keywords", [])):
                material_refs.add(ref_id)
        for ref_id, cfg in content_patterns_mapping.items():
            if isinstance(cfg, dict) and any(kw.lower() in haystack for kw in cfg.get("keywords", [])):
                content_pattern_refs.add(ref_id)
        for ref_id, cfg in visual_patterns_mapping.items():
            if isinstance(cfg, dict) and any(kw.lower() in haystack for kw in cfg.get("keywords", [])):
                visual_pattern_refs.add(ref_id)
        for ref_id, cfg in audiences_mapping.items():
            if isinstance(cfg, dict) and any(kw.lower() in haystack for kw in cfg.get("keywords", [])):
                audience_refs.add(ref_id)

        for platform_ref, config in platform_mapping.items():
            synonyms = config.get("synonyms", []) if isinstance(config, dict) else []
            if platform_ref in signal.platform_refs:
                platform_refs.add(platform_ref)
            if any(str(synonym).lower() in signal.title.lower() for synonym in synonyms):
                platform_refs.add(platform_ref)
            if signal.source_name and any(str(synonym).lower() in signal.source_name.lower() for synonym in synonyms):
                platform_refs.add(platform_ref)

        if signal.platform_refs:
            platform_refs.update(signal.platform_refs)

        projected.append(
            signal.model_copy(
                update={
                    "entity_refs": sorted(entity_refs),
                    "raw_entity_hits": resolution.raw_entity_hits,
                    "canonical_entity_refs": resolution.canonical_entity_refs,
                    "topic_tags": topic_tags,
                    "source_refs": sorted(source_refs),
                    "platform_refs": sorted(platform_refs),
                    "scene_refs": sorted(scene_refs),
                    "style_refs": sorted(style_refs),
                    "need_refs": sorted(need_refs),
                    "risk_factor_refs": sorted(risk_factor_refs),
                    "material_refs": sorted(material_refs),
                    "content_pattern_refs": sorted(content_pattern_refs),
                    "visual_pattern_refs": sorted(visual_pattern_refs),
                    "audience_refs": sorted(audience_refs),
                }
            )
        )

    return projected


# ── XHS 三维信号专用本体映射 ──────────────────────────────

# VP 映射：need -> canonical value proposition ref
_VP_MAP: dict[str, str] = {
    "need_photogenic": "vp_photogenic",
    "need_premium_feel": "vp_premium_feel",
    "need_easy_clean": "vp_easy_clean",
    "need_affordable": "vp_affordable_upgrade",
    "need_affordable_upgrade": "vp_affordable_upgrade",
    "need_waterproof": "vp_easy_clean",
}


def map_styles(
    visual: VisualSignals,
    scene: SceneSignals,
    config: dict[str, Any],
) -> list[str]:
    styles_cfg = config.get("styles", {})
    signal_values = visual.visual_style_signals + [
        s for s in scene.scene_signals if any(
            kw in s.lower() for kw in ("风", "ins", "北欧", "法式", "复古", "日系", "原木", "极简")
        )
    ]
    return _match_signals_to_refs(signal_values, styles_cfg)


def map_scenes(
    scene: SceneSignals,
    visual: VisualSignals,
    config: dict[str, Any],
) -> list[str]:
    scenes_cfg = config.get("scenes", {})
    signal_values = scene.scene_signals + scene.inferred_scene_signals
    if visual.visual_scene_signals:
        signal_values = signal_values + [
            s.replace("场景", "") for s in visual.visual_scene_signals
        ]
    return _match_signals_to_refs(signal_values, scenes_cfg)


def map_needs(
    selling: SellingThemeSignals,
    scene: SceneSignals,
    config: dict[str, Any],
) -> list[str]:
    needs_cfg = config.get("needs", {})
    signal_values = selling.selling_point_signals + scene.scene_goal_signals
    return _match_signals_to_refs(signal_values, needs_cfg)


def map_risks(
    selling: SellingThemeSignals,
    visual: VisualSignals,
    cross_modal: Any | None,
    config: dict[str, Any],
) -> list[str]:
    risk_cfg = config.get("risk_factors", {})
    signal_values = selling.selling_point_challenges + visual.visual_misleading_risk
    refs = _match_signals_to_refs(signal_values, risk_cfg)

    if cross_modal is not None:
        unsupported = getattr(cross_modal, "unsupported_claims", [])
        if unsupported and "risk_claim_unverified" not in refs:
            refs.append("risk_claim_unverified")

    return refs


def map_visual_patterns(
    visual: VisualSignals,
    config: dict[str, Any],
) -> list[str]:
    visual_cfg = config.get("visual_patterns", {})
    signal_values = (
        visual.visual_composition_type
        + visual.visual_expression_pattern
        + visual.visual_feature_highlights
    )
    return _match_signals_to_refs(signal_values, visual_cfg)


def map_content_patterns(
    selling: SellingThemeSignals,
    scene: SceneSignals,
    config: dict[str, Any],
) -> list[str]:
    content_cfg = config.get("content_patterns", {})
    signal_values = selling.selling_theme_refs
    return _match_signals_to_refs(signal_values, content_cfg)


def map_value_propositions(
    selling: SellingThemeSignals,
    visual: VisualSignals,
    scene: SceneSignals,
    config: dict[str, Any],
) -> list[str]:
    needs_cfg = config.get("needs", {})
    styles_cfg = config.get("styles", {})

    need_refs = _match_signals_to_refs(selling.selling_point_signals, needs_cfg)
    style_refs = _match_signals_to_refs(visual.visual_style_signals, styles_cfg)

    vps: list[str] = []
    for n in need_refs:
        vp = _VP_MAP.get(n)
        if vp and vp not in vps:
            vps.append(vp)

    if need_refs and style_refs:
        for n in need_refs[:2]:
            for s in style_refs[:2]:
                combo = f"{n}+{s}"
                if combo not in vps:
                    vps.append(combo)

    return vps


def map_audiences(
    scene: SceneSignals,
    config: dict[str, Any],
) -> list[str]:
    audiences_cfg = config.get("audiences", {})
    return _match_signals_to_refs(scene.audience_signals, audiences_cfg)


def build_source_signal_summary(
    visual: VisualSignals,
    selling: SellingThemeSignals,
    scene: SceneSignals,
) -> str:
    parts: list[str] = []
    if visual.visual_style_signals:
        parts.append(f"风格: {', '.join(visual.visual_style_signals[:3])}")
    if selling.selling_point_signals:
        parts.append(f"卖点: {', '.join(selling.selling_point_signals[:3])}")
    if scene.scene_signals:
        parts.append(f"场景: {', '.join(scene.scene_signals[:3])}")
    if selling.validated_selling_points:
        parts.append(f"已验证: {', '.join(selling.validated_selling_points[:2])}")
    return " | ".join(parts) if parts else ""


def build_evidence_refs(
    visual: VisualSignals,
    selling: SellingThemeSignals,
    scene: SceneSignals,
) -> list[XHSEvidenceRef]:
    evidence: list[XHSEvidenceRef] = []
    evidence.extend(visual.evidence_refs)
    evidence.extend(selling.evidence_refs)
    evidence.extend(scene.evidence_refs)
    return evidence


def project_xhs_signals(
    visual: VisualSignals,
    selling: SellingThemeSignals,
    scene: SceneSignals,
    ontology_config: dict[str, Any],
    cross_modal: Any | None = None,
) -> XHSOntologyMapping:
    """将三维提取结果映射到 canonical ontology refs。

    从 ontology_mapping.yaml 配置中查找 alias -> canonical ref，
    汇总所有 evidence_refs。cross_modal 用于增补 risk 映射。
    """
    note_id = visual.note_id or selling.note_id or scene.note_id

    entities_cfg = ontology_config.get("entities", {})
    category_refs: list[str] = []
    for eid, ecfg in entities_cfg.items():
        if not isinstance(ecfg, dict):
            continue
        if ecfg.get("entity_type") != "category":
            continue
        aliases = [a.lower() for a in ecfg.get("aliases", [])]
        haystack = " ".join(
            scene.scene_signals + selling.selling_point_signals
            + visual.visual_style_signals
        ).lower()
        if any(a in haystack for a in aliases):
            category_refs.append(eid)

    return XHSOntologyMapping(
        note_id=note_id,
        category_refs=category_refs,
        scene_refs=map_scenes(scene, visual, ontology_config),
        style_refs=map_styles(visual, scene, ontology_config),
        need_refs=map_needs(selling, scene, ontology_config),
        risk_refs=map_risks(selling, visual, cross_modal, ontology_config),
        audience_refs=map_audiences(scene, ontology_config),
        visual_pattern_refs=map_visual_patterns(visual, ontology_config),
        content_pattern_refs=map_content_patterns(selling, scene, ontology_config),
        value_proposition_refs=map_value_propositions(selling, visual, scene, ontology_config),
        source_signal_summary=build_source_signal_summary(visual, selling, scene),
        evidence_refs=build_evidence_refs(visual, selling, scene),
    )


def _match_signals_to_refs(
    signal_values: list[str],
    ontology_section: dict[str, Any],
) -> list[str]:
    """将提取器产出的信号值（如"出租屋"）映射到 canonical ref（如"scene_rental_room"）。"""
    refs: list[str] = []
    for ref_id, cfg in ontology_section.items():
        if not isinstance(cfg, dict):
            continue
        keywords = [k.lower() for k in cfg.get("keywords", [])]
        for sv in signal_values:
            if sv.lower() in keywords or any(kw in sv.lower() for kw in keywords):
                if ref_id not in refs:
                    refs.append(ref_id)
                break
    return refs
