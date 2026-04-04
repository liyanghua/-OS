"""Agent 侧模板检索、匹配与主图方案编译单测。"""

from __future__ import annotations

import json
from pathlib import Path

from apps.template_extraction.agent.plan_compiler import MainImagePlanCompiler
from apps.template_extraction.agent.template_matcher import TemplateMatcher
from apps.template_extraction.agent.template_retriever import TemplateRetriever
from apps.template_extraction.schemas.template import ClusterFeatures
from apps.template_extraction.templates.template_compiler import _cfg_to_template, load_template_defaults


def _tpl(template_key: str):
    defaults = load_template_defaults()
    cfg = defaults["templates"][template_key]
    return _cfg_to_template(template_key, cfg, ClusterFeatures(), [])


def test_template_retriever_loads_templates(tmp_path: Path) -> None:
    """TemplateRetriever 从目录加载 index.json 与各模板 JSON。"""
    t1 = _tpl("tpl_001_scene_seed")
    t2 = _tpl("tpl_005_festival_gift")
    tmp_path.mkdir(parents=True, exist_ok=True)
    index = [
        {"template_id": t1.template_id, "template_name": t1.template_name, "version": t1.template_version},
        {"template_id": t2.template_id, "template_name": t2.template_name, "version": t2.template_version},
    ]
    (tmp_path / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    (tmp_path / f"{t1.template_id}.json").write_text(
        json.dumps(t1.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / f"{t2.template_id}.json").write_text(
        json.dumps(t2.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )

    retriever = TemplateRetriever(templates_dir=str(tmp_path))
    ids = sorted(retriever.get_template_ids())
    assert ids == sorted([t1.template_id, t2.template_id])
    assert len(retriever.list_templates()) == 2


def test_template_matcher_ranked_results() -> None:
    """match_templates 返回按分数降序的 MatchResult 列表。"""
    templates = [
        _tpl("tpl_001_scene_seed"),
        _tpl("tpl_003_texture_detail"),
        _tpl("tpl_004_affordable_makeover"),
        _tpl("tpl_005_festival_gift"),
    ]
    matcher = TemplateMatcher(templates)
    ranked = matcher.match_templates(product_brief="早餐 下午茶", intent="种草", top_k=3)
    assert len(ranked) == 3
    scores = [r.score for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0].score >= ranked[-1].score


def test_main_image_plan_compiler_five_slots() -> None:
    """MainImagePlanCompiler 生成含 5 个槽位的 MainImagePlan。"""
    tpl = _tpl("tpl_001_scene_seed")
    compiler = MainImagePlanCompiler()
    plan = compiler.compile_main_image_plan(
        tpl,
        opportunity_card={"opportunity_id": "opp_1", "opportunity_type": "visual_scene"},
        product_brief="奶油风桌布测试",
        matcher_rationale="单元测试",
    )
    assert plan.template_id == tpl.template_id
    assert len(plan.image_slots) == 5
    indices = [s.slot_index for s in plan.image_slots]
    assert indices == [1, 2, 3, 4, 5]
    for slot in plan.image_slots:
        assert slot.role
        assert slot.intent
        assert slot.visual_brief


def test_match_templates_different_intents() -> None:
    """不同经营意图下，Top1 模板可随启发式变化。"""
    templates = [
        _tpl("tpl_001_scene_seed"),
        _tpl("tpl_004_affordable_makeover"),
        _tpl("tpl_005_festival_gift"),
    ]
    matcher = TemplateMatcher(templates)

    top_种草 = matcher.match_templates(intent="种草", top_k=1)[0].template_id
    top_转化 = matcher.match_templates(intent="转化", top_k=1)[0].template_id
    top_礼赠 = matcher.match_templates(intent="礼赠", top_k=1)[0].template_id

    assert top_种草 == "tpl_001_scene_seed"
    assert top_转化 in ("tpl_003_texture_detail", "tpl_004_affordable_makeover")
    assert top_礼赠 == "tpl_005_festival_gift"
