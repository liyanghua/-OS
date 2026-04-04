"""模板编译与校验单测。"""

from __future__ import annotations

from apps.template_extraction.schemas.cluster_sample import ClusterSample
from apps.template_extraction.schemas.template import (
    ClusterFeatures,
    CopyRules,
    SceneRules,
    TableclothMainImageStrategyTemplate,
    VisualRules,
)
from apps.template_extraction.templates.template_compiler import (
    _cfg_to_template,
    compile_templates,
    load_template_defaults,
)
from apps.template_extraction.templates.template_validator import validate_template, validate_template_set


def test_load_template_defaults_reads_yaml() -> None:
    """load_template_defaults 能解析 YAML 并包含 templates 根键。"""
    data = load_template_defaults()
    assert isinstance(data, dict)
    assert "templates" in data
    tpls = data["templates"]
    assert "tpl_001_scene_seed" in tpls
    assert tpls["tpl_001_scene_seed"].get("template_name")


def _complete_template_from_defaults() -> TableclothMainImageStrategyTemplate:
    defaults = load_template_defaults()
    cfg = defaults["templates"]["tpl_001_scene_seed"]
    return _cfg_to_template(
        "tpl_001_scene_seed",
        cfg,
        ClusterFeatures(
            dominant_task_labels=["scene_seed"],
            dominant_visual_labels=["shot_topdown"],
            dominant_semantic_labels=["mood_photo_friendly"],
        ),
        ["seed_1", "seed_2"],
    )


def test_validate_template_complete_passes() -> None:
    """完整模板校验应无问题。"""
    tpl = _complete_template_from_defaults()
    issues = validate_template(tpl)
    assert issues == []


def test_validate_template_incomplete_reports_issues() -> None:
    """缺失名称/目标/规则时 validate_template 应返回非空问题列表。"""
    base = _complete_template_from_defaults()
    bad = base.model_copy(
        update={
            "template_name": "",
            "template_goal": "",
            "visual_rules": VisualRules(),
            "copy_rules": CopyRules(),
            "scene_rules": SceneRules(),
            "risk_rules": [],
            "best_for": [],
            "avoid_when": [],
        }
    )
    issues = validate_template(bad)
    assert len(issues) >= 3


def test_validate_template_set_boundary_overlaps() -> None:
    """validate_template_set 统计有效模板数并检测场景重叠。"""
    a = _complete_template_from_defaults()
    b = a.model_copy(
        update={
            "template_id": "tpl_099_overlap",
            "template_name": "重叠场景测试模板",
        }
    )
    result = validate_template_set([a, b])
    assert result["total"] == 2
    assert result["valid"] == 2
    overlaps = result["boundary_check"]["scenario_overlaps"]
    assert isinstance(overlaps, dict)
    assert len(overlaps) >= 1


def test_compile_templates_produces_valid_templates() -> None:
    """compile_templates 输出可校验的 TableclothMainImageStrategyTemplate 列表。"""
    samples = [
        ClusterSample(note_id="a1", strategy_cluster_id="0", cover_cluster_id="0"),
        ClusterSample(note_id="a2", strategy_cluster_id="0", cover_cluster_id="1"),
        ClusterSample(note_id="b1", strategy_cluster_id="1", cover_cluster_id="2"),
    ]
    cluster_to_template = {
        0: "tpl_001_scene_seed",
        1: "tpl_002_style_anchor",
    }
    compiled = compile_templates(samples, cluster_to_template)
    assert len(compiled) == 2
    for tpl in compiled:
        assert isinstance(tpl, TableclothMainImageStrategyTemplate)
        assert tpl.template_id in ("tpl_001_scene_seed", "tpl_002_style_anchor")
        assert validate_template(tpl) == []
