"""模板提取 Agent 消费 API：检索模板、匹配候选、编译主图策划方案。"""

from __future__ import annotations

from apps.template_extraction.agent.plan_compiler import MainImagePlanCompiler
from apps.template_extraction.agent.template_matcher import MatchResult, TemplateMatcher
from apps.template_extraction.agent.template_retriever import TemplateRetriever
from apps.template_extraction.schemas.agent_plan import ImageSlotPlan, MainImagePlan
from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate

__all__ = [
    "ImageSlotPlan",
    "MainImagePlan",
    "MainImagePlanCompiler",
    "MatchResult",
    "TableclothMainImageStrategyTemplate",
    "TemplateMatcher",
    "TemplateRetriever",
    "build_main_image_plan",
]


def build_main_image_plan(
    template_id: str | None = None,
    opportunity_card: dict | None = None,
    product_brief: str = "",
    intent: str = "",
    templates_dir: str | None = None,
) -> tuple[MainImagePlan, list[MatchResult]]:
    """一站式：加载模板库 → 匹配（或使用指定 template_id）→ 编译 MainImagePlan。

    返回 (plan, top_matches)。若指定 template_id 则直接使用该模板，matches 仍为按意图排序的候选列表。
    """
    retriever = TemplateRetriever(templates_dir=templates_dir) if templates_dir else TemplateRetriever()
    templates = retriever.list_templates()
    matcher = TemplateMatcher(templates)
    matches = matcher.match_templates(
        opportunity_card=opportunity_card,
        product_brief=product_brief,
        intent=intent,
        top_k=5,
    )

    tpl: TableclothMainImageStrategyTemplate | None = None
    rationale = ""
    if template_id:
        tpl = retriever.get_template(template_id)
        rationale = f"指定模板: {template_id}"
    if tpl is None and matches:
        tpl = retriever.get_template(matches[0].template_id)
        rationale = matches[0].reason
    if tpl is None and templates:
        tpl = templates[0]
        rationale = rationale or "回退至库内首套模板"

    if tpl is None:
        raise ValueError("模板库为空或无法解析所选 template_id")

    compiler = MainImagePlanCompiler()
    plan = compiler.compile_main_image_plan(
        matched_template=tpl,
        opportunity_card=opportunity_card,
        product_brief=product_brief,
        matcher_rationale=rationale,
    )
    return plan, matches
