"""模板质量评估。"""

from __future__ import annotations

from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate


def evaluate_template_completeness(templates: list[TableclothMainImageStrategyTemplate]) -> dict:
    """评估模板完整性。"""
    results: dict[str, dict] = {}
    for tpl in templates:
        score = 0.0
        total = 10
        if tpl.template_name:
            score += 1
        if tpl.template_goal:
            score += 1
        if tpl.fit_scenarios:
            score += 1
        if tpl.visual_rules:
            score += 1
        if tpl.copy_rules:
            score += 1
        if tpl.scene_rules:
            score += 1
        if tpl.risk_rules:
            score += 1
        if tpl.best_for:
            score += 1
        if tpl.avoid_when:
            score += 1
        if tpl.seed_examples:
            score += 1
        results[tpl.template_id] = {"completeness_score": score / total}
    return results


def evaluate_template_boundaries(templates: list[TableclothMainImageStrategyTemplate]) -> dict:
    """评估模板间边界清晰度（适用场景 / 风格在多模板间的重叠）。"""
    scenario_map: dict[str, list[str]] = {}
    for tpl in templates:
        for s in tpl.fit_scenarios:
            scenario_map.setdefault(s, []).append(tpl.template_id)

    overlaps = {s: ids for s, ids in scenario_map.items() if len(ids) > 1}

    style_map: dict[str, list[str]] = {}
    for tpl in templates:
        for st in tpl.fit_styles:
            style_map.setdefault(st, []).append(tpl.template_id)
    style_overlaps = {s: ids for s, ids in style_map.items() if len(ids) > 1}

    return {
        "scenario_overlaps": overlaps,
        "style_overlaps": style_overlaps,
        "scenario_overlap_count": len(overlaps),
        "style_overlap_count": len(style_overlaps),
    }


def evaluate_template_executability(templates: list[TableclothMainImageStrategyTemplate]) -> dict:
    """评估模板可执行性（是否提供足够信息让 Agent 执行）。"""
    results: dict[str, dict] = {}
    for tpl in templates:
        issues: list[str] = []
        vr = tpl.visual_rules
        if vr and not vr.preferred_shots:
            issues.append("无推荐镜头")
        if vr and not vr.required_elements:
            issues.append("无必备元素")
        cr = tpl.copy_rules
        if cr and not cr.title_style:
            issues.append("无标题风格")
        sr = tpl.scene_rules
        if sr and not sr.scene_types:
            issues.append("无场景类型")
        results[tpl.template_id] = {
            "is_executable": len(issues) == 0,
            "issues": issues,
        }
    return results
