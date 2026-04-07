"""RewriteStrategyGenerator：从 Brief + 模板匹配结果生成改写策略。"""

from __future__ import annotations

from typing import Any

from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.schemas.template_match_result import TemplateMatchResult
from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate


_TONE_MAP: dict[str, str] = {
    "种草收藏": "分享感、真实感、生活化表达",
    "转化": "利益点突出、紧迫感、性价比话术",
    "展示种草": "美学表达、种草收藏感",
    "礼赠": "仪式感、温暖祝福、情感共鸣",
}

_SEQ_CN: dict[str, str] = {
    "hook_click": "首图吸睛",
    "cover_hook": "封面吸引",
    "style_expand": "风格延展",
    "texture_expand": "质感细节",
    "usage_expand": "使用场景",
    "guide_expand": "引导转化",
}


class RewriteStrategyGenerator:
    """规则优先的改写策略生成器，预留 LLM 增强接口。"""

    def generate(
        self,
        brief: OpportunityBrief,
        match_result: TemplateMatchResult,
        template: TableclothMainImageStrategyTemplate,
        *,
        llm_client: Any | None = None,
    ) -> RewriteStrategy:
        strategy = self._rule_based_generate(brief, match_result, template)
        if llm_client is not None:
            strategy = self._llm_enhance(strategy, brief, template, llm_client)
        return strategy

    def _rule_based_generate(
        self,
        brief: OpportunityBrief,
        match_result: TemplateMatchResult,
        tpl: TableclothMainImageStrategyTemplate,
    ) -> RewriteStrategy:
        positioning = self._build_positioning(brief, tpl)
        new_hook = self._build_hook(brief, tpl)
        tone = _TONE_MAP.get(brief.content_goal or "", "自然真实")

        keep = list(tpl.visual_rules.required_elements)
        replace = self._identify_replace_elements(brief, tpl)
        enhance = self._identify_enhance_elements(brief, tpl)
        avoid = list(tpl.copy_rules.avoid_phrases) + brief.avoid_directions

        title_strategy = self._build_title_strategy(brief, tpl)
        body_strategy = self._build_body_strategy(brief, tpl)
        image_strategy = self._build_image_strategy(tpl)

        diff_axis = []
        if brief.primary_value:
            diff_axis.append(brief.primary_value)
        diff_axis.extend(brief.visual_style_direction[:2])

        risk_notes = list(tpl.risk_rules[:3])
        if brief.avoid_directions:
            risk_notes.append("用户提示规避: " + "、".join(brief.avoid_directions[:3]))

        return RewriteStrategy(
            opportunity_id=brief.opportunity_id,
            brief_id=brief.brief_id,
            template_id=tpl.template_id,
            positioning_statement=positioning,
            new_hook=new_hook,
            new_angle=brief.core_motive or "",
            tone_of_voice=tone,
            keep_elements=keep,
            replace_elements=replace,
            enhance_elements=enhance,
            avoid_elements=list(dict.fromkeys(avoid))[:8],
            title_strategy=title_strategy,
            body_strategy=body_strategy,
            image_strategy=image_strategy,
            differentiation_axis=diff_axis[:4],
            risk_notes=risk_notes,
        )

    @staticmethod
    def _build_positioning(brief: OpportunityBrief, tpl: TableclothMainImageStrategyTemplate) -> str:
        motive = brief.core_motive or brief.opportunity_summary[:40]
        goal = tpl.template_goal
        return f"以「{motive}」为核心卖点，围绕「{goal}」模板策略构建内容表达"

    @staticmethod
    def _build_hook(brief: OpportunityBrief, tpl: TableclothMainImageStrategyTemplate) -> str:
        hooks = tpl.hook_mechanism[:2]
        value = brief.primary_value or ""
        if hooks and value:
            return f"{hooks[0]}——聚焦「{value}」"
        if hooks:
            return hooks[0]
        return value or "场景代入 + 利益点前置"

    @staticmethod
    def _identify_replace_elements(brief: OpportunityBrief, tpl: TableclothMainImageStrategyTemplate) -> list[str]:
        replaces: list[str] = []
        if brief.avoid_directions:
            for avoid in brief.avoid_directions:
                replaces.append(f"替换: {avoid}")
        return replaces[:5]

    @staticmethod
    def _identify_enhance_elements(brief: OpportunityBrief, tpl: TableclothMainImageStrategyTemplate) -> list[str]:
        enhances: list[str] = []
        if brief.visual_style_direction:
            enhances.append(f"强化风格方向: {'、'.join(brief.visual_style_direction[:3])}")
        if brief.target_scene:
            enhances.append(f"场景融合: {'、'.join(brief.target_scene[:3])}")
        return enhances[:5]

    @staticmethod
    def _build_title_strategy(brief: OpportunityBrief, tpl: TableclothMainImageStrategyTemplate) -> list[str]:
        strategies: list[str] = []
        styles = tpl.copy_rules.title_style[:3]
        if styles:
            strategies.append(f"标题风格参考: {'、'.join(styles)}")
        if brief.primary_value:
            strategies.append(f"核心利益点前置: {brief.primary_value}")
        if brief.target_scene:
            strategies.append(f"场景化标题: 融入{'、'.join(brief.target_scene[:2])}")
        if not strategies:
            strategies.append("突出场景 + 利益点")
        return strategies[:4]

    @staticmethod
    def _build_body_strategy(brief: OpportunityBrief, tpl: TableclothMainImageStrategyTemplate) -> list[str]:
        strategies: list[str] = []
        if brief.content_goal:
            strategies.append(f"正文围绕{brief.content_goal}目标展开")
        if brief.target_scene:
            strategies.append(f"开头用场景代入: {'、'.join(brief.target_scene[:2])}")
        if brief.secondary_values:
            strategies.append(f"中段补充次要价值: {'、'.join(brief.secondary_values[:3])}")
        strategies.append("结尾引导行动（收藏/购买/关注）")
        return strategies[:4]

    @staticmethod
    def _build_image_strategy(tpl: TableclothMainImageStrategyTemplate) -> list[str]:
        strategies: list[str] = []
        seq = tpl.image_sequence_pattern[:5]
        if seq:
            readable = [_SEQ_CN.get(r, r) for r in seq]
            strategies.append(f"图组顺序: {'→'.join(readable)}")
        if tpl.visual_rules.preferred_shots:
            strategies.append(f"优选景别: {'、'.join(tpl.visual_rules.preferred_shots[:3])}")
        if tpl.visual_rules.color_direction:
            strategies.append(f"色彩方向: {'、'.join(tpl.visual_rules.color_direction[:3])}")
        return strategies[:4]

    @staticmethod
    def _llm_enhance(
        strategy: RewriteStrategy,
        brief: OpportunityBrief,
        tpl: TableclothMainImageStrategyTemplate,
        llm_client: Any,
    ) -> RewriteStrategy:
        """预留接口：用 LLM 润色 / 补强策略。目前直接返回原策略。"""
        return strategy
