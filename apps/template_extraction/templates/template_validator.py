"""模板质量检查。"""

from __future__ import annotations

from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate


def validate_template(template: TableclothMainImageStrategyTemplate) -> list[str]:
    """检查单个模板完整性，返回问题列表（空 = 通过）。"""
    issues: list[str] = []
    if not template.template_name:
        issues.append("template_name 缺失")
    if not template.template_goal:
        issues.append("template_goal 缺失")
    vr = template.visual_rules
    if not (vr.preferred_shots or vr.required_elements):
        issues.append("visual_rules 缺失")
    cr = template.copy_rules
    if not (cr.title_style or cr.cover_copy_style):
        issues.append("copy_rules 缺失")
    sr = template.scene_rules
    if not sr.scene_types and not sr.avoid_scenes:
        issues.append("scene_rules 缺失")
    if not template.risk_rules:
        issues.append("risk_rules 为空")
    if not template.best_for:
        issues.append("best_for 为空")
    if not template.avoid_when:
        issues.append("avoid_when 为空")
    return issues


def validate_template_set(templates: list[TableclothMainImageStrategyTemplate]) -> dict:
    """校验模板集：覆盖度、边界清晰度。"""
    result: dict = {
        "total": len(templates),
        "valid": 0,
        "issues": {},
        "boundary_check": {},
    }

    for tpl in templates:
        issues = validate_template(tpl)
        if not issues:
            result["valid"] += 1
        else:
            result["issues"][tpl.template_id] = issues

    scenario_map: dict[str, list[str]] = {}
    for tpl in templates:
        for s in tpl.fit_scenarios:
            scenario_map.setdefault(s, []).append(tpl.template_id)
    overlaps = {s: ids for s, ids in scenario_map.items() if len(ids) > 1}
    result["boundary_check"]["scenario_overlaps"] = overlaps

    return result
