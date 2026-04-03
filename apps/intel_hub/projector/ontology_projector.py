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


def project_xhs_signals(
    visual: VisualSignals,
    selling: SellingThemeSignals,
    scene: SceneSignals,
    ontology_config: dict[str, Any],
) -> XHSOntologyMapping:
    """将三维提取结果映射到 canonical ontology refs。

    从 ontology_mapping.yaml 配置中查找 alias -> canonical ref，
    汇总所有 evidence_refs。
    """
    note_id = visual.note_id or selling.note_id or scene.note_id

    scenes_cfg = ontology_config.get("scenes", {})
    styles_cfg = ontology_config.get("styles", {})
    needs_cfg = ontology_config.get("needs", {})
    risk_cfg = ontology_config.get("risk_factors", {})
    visual_cfg = ontology_config.get("visual_patterns", {})
    content_cfg = ontology_config.get("content_patterns", {})
    audiences_cfg = ontology_config.get("audiences", {})
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

    scene_refs = _match_signals_to_refs(scene.scene_signals, scenes_cfg)
    style_refs = _match_signals_to_refs(visual.visual_style_signals, styles_cfg)
    need_refs = _match_signals_to_refs(selling.selling_point_signals, needs_cfg)
    risk_refs = _match_signals_to_refs(
        selling.selling_point_challenges + visual.visual_misleading_risk,
        risk_cfg,
    )
    visual_pattern_refs = _match_signals_to_refs(
        visual.visual_composition_type + visual.visual_expression_pattern,
        visual_cfg,
    )
    content_pattern_refs = _match_signals_to_refs(selling.selling_theme_refs, content_cfg)
    audience_refs = _match_signals_to_refs(scene.audience_signals, audiences_cfg)

    value_proposition_refs: list[str] = []
    if need_refs and style_refs:
        for n in need_refs[:2]:
            for s in style_refs[:2]:
                value_proposition_refs.append(f"{n}+{s}")

    all_evidence: list[XHSEvidenceRef] = []
    all_evidence.extend(visual.evidence_refs)
    all_evidence.extend(selling.evidence_refs)
    all_evidence.extend(scene.evidence_refs)

    return XHSOntologyMapping(
        note_id=note_id,
        category_refs=category_refs,
        scene_refs=scene_refs,
        style_refs=style_refs,
        need_refs=need_refs,
        risk_refs=risk_refs,
        audience_refs=audience_refs,
        visual_pattern_refs=visual_pattern_refs,
        content_pattern_refs=content_pattern_refs,
        value_proposition_refs=value_proposition_refs,
        evidence_refs=all_evidence,
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
