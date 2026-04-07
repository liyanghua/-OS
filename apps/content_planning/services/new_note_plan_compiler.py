"""NewNotePlanCompiler：整合 Brief + Strategy + Template 编译完整的新笔记策划。"""

from __future__ import annotations

from apps.content_planning.schemas.note_plan import (
    BodyPlan,
    NewNotePlan,
    TitlePlan,
)
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.schemas.template_match_result import TemplateMatchResult
from apps.template_extraction.agent.plan_compiler import MainImagePlanCompiler
from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate


class NewNotePlanCompiler:
    """从 Brief + Strategy + Template 编译出含标题/正文/图片三维策划的 NewNotePlan。"""

    def __init__(self) -> None:
        self._image_compiler = MainImagePlanCompiler()

    def compile(
        self,
        brief: OpportunityBrief,
        strategy: RewriteStrategy,
        match_result: TemplateMatchResult,
        template: TableclothMainImageStrategyTemplate,
    ) -> NewNotePlan:
        title_plan = self._build_title_plan(strategy, template)
        body_plan = self._build_body_plan(strategy, brief)
        image_plan = self._build_image_plan(brief, strategy, template)

        return NewNotePlan(
            opportunity_id=brief.opportunity_id,
            brief_id=brief.brief_id,
            strategy_id=strategy.strategy_id,
            template_id=template.template_id,
            template_name=template.template_name,
            note_goal=brief.content_goal,
            target_user=brief.target_user,
            target_scene=brief.target_scene,
            core_selling_point=brief.primary_value,
            theme=strategy.positioning_statement,
            tone_of_voice=strategy.tone_of_voice,
            title_plan=title_plan,
            body_plan=body_plan,
            image_plan=image_plan,
            publish_notes=self._build_publish_notes(strategy, template),
        )

    @staticmethod
    def _build_title_plan(
        strategy: RewriteStrategy,
        template: TableclothMainImageStrategyTemplate,
    ) -> TitlePlan:
        title_axes = list(strategy.title_strategy)
        candidates: list[str] = []
        for phrase in template.copy_rules.recommended_phrases[:3]:
            candidates.append(f"[参考] {phrase}")

        do_not_use = list(template.copy_rules.avoid_phrases)
        do_not_use.extend(strategy.avoid_elements[:3])

        return TitlePlan(
            title_axes=title_axes,
            candidate_titles=candidates,
            do_not_use_phrases=list(dict.fromkeys(do_not_use))[:8],
        )

    @staticmethod
    def _build_body_plan(
        strategy: RewriteStrategy,
        brief: OpportunityBrief,
    ) -> BodyPlan:
        return BodyPlan(
            opening_hook=strategy.new_hook,
            body_outline=list(strategy.body_strategy),
            cta_direction="收藏/关注" if brief.content_goal == "种草收藏" else "购买/转化",
            tone_notes=[strategy.tone_of_voice] if strategy.tone_of_voice else [],
        )

    def _build_image_plan(
        self,
        brief: OpportunityBrief,
        strategy: RewriteStrategy,
        template: TableclothMainImageStrategyTemplate,
    ):
        plan = self._image_compiler.compile_main_image_plan(
            matched_template=template,
            opportunity_card={"opportunity_id": brief.opportunity_id},
            product_brief=brief.opportunity_summary[:200],
            matcher_rationale=f"brief-aware match: {strategy.positioning_statement[:60]}",
        )
        plan.opportunity_id = brief.opportunity_id
        plan.brief_id = brief.brief_id
        plan.strategy_id = strategy.strategy_id
        return plan

    @staticmethod
    def _build_publish_notes(
        strategy: RewriteStrategy,
        template: TableclothMainImageStrategyTemplate,
    ) -> list[str]:
        notes: list[str] = []
        if strategy.risk_notes:
            notes.append("风险提示: " + "；".join(strategy.risk_notes[:2]))
        if template.avoid_when:
            notes.append("不适用场景: " + "、".join(template.avoid_when[:3]))
        return notes
