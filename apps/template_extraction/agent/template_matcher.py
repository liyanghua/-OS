"""模板匹配器：根据机会卡 + 商品简介 + 意图匹配最佳模板。

支持两种模式：
1. 旧模式（向后兼容）：opportunity_card dict + product_brief 文本
2. brief-aware 模式：传入 OpportunityBrief 结构化对象时自动使用更精准的打分
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate

if TYPE_CHECKING:
    from apps.content_planning.schemas.opportunity_brief import OpportunityBrief

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    template_id: str
    template_name: str
    score: float
    reason: str


_GOAL_TEMPLATE_AFFINITY: dict[str, list[str]] = {
    "种草收藏": ["scene_seed", "style_anchor"],
    "转化": ["texture_detail", "affordable_makeover", "budget_hero"],
    "展示种草": ["scene_seed", "style_anchor", "texture_detail"],
    "礼赠": ["festival_gift", "occasion_gift"],
}


class TemplateMatcher:
    def __init__(self, templates: list[TableclothMainImageStrategyTemplate]):
        self._templates = {t.template_id: t for t in templates}

    def match_templates(
        self,
        opportunity_card: dict | None = None,
        product_brief: str = "",
        intent: str = "",
        top_k: int = 3,
        *,
        brief: OpportunityBrief | None = None,
    ) -> list[MatchResult]:
        """匹配模板，返回 top_k 候选。

        当 brief 存在时走 brief-aware 精准打分；否则走旧逻辑保持向后兼容。
        """
        scores = []
        for tpl_id, tpl in self._templates.items():
            if brief is not None:
                score = self._score_with_brief(tpl, brief)
                reason = self._explain_brief_score(tpl, brief)
            else:
                score = self._score_template(tpl, opportunity_card, product_brief, intent)
                reason = self._explain_score(tpl, opportunity_card, product_brief, intent)
            scores.append(
                MatchResult(
                    template_id=tpl_id,
                    template_name=tpl.template_name,
                    score=score,
                    reason=reason,
                )
            )
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[:top_k]

    # ── brief-aware 打分 ──

    def _score_with_brief(
        self,
        tpl: TableclothMainImageStrategyTemplate,
        brief: OpportunityBrief,
    ) -> float:
        score = 0.0
        tpl_key = self._extract_tpl_key(tpl)

        if brief.content_goal:
            affinities = _GOAL_TEMPLATE_AFFINITY.get(brief.content_goal, [])
            if any(a in tpl.template_id or a == tpl_key for a in affinities):
                score += 0.30

        scene_hits = sum(1 for s in brief.target_scene if any(s in fs for fs in tpl.fit_scenarios))
        score += min(scene_hits * 0.10, 0.30)

        style_hits = sum(1 for s in brief.visual_style_direction if any(s in fs for fs in tpl.fit_styles))
        score += min(style_hits * 0.08, 0.24)

        if brief.primary_value:
            hooks = " ".join(tpl.hook_mechanism) + " " + " ".join(tpl.best_for)
            if brief.primary_value in hooks:
                score += 0.15

        for hint in brief.template_hints:
            if hint in tpl.template_id or hint == tpl_key:
                score += 0.20
                break

        if brief.avoid_directions:
            avoid_text = " ".join(brief.avoid_directions)
            avoid_when = " ".join(tpl.avoid_when)
            overlap = sum(1 for a in brief.avoid_directions if a in avoid_when)
            score -= overlap * 0.10

        return max(min(score, 1.0), 0.0)

    def _explain_brief_score(
        self,
        tpl: TableclothMainImageStrategyTemplate,
        brief: OpportunityBrief,
    ) -> str:
        reasons = []
        tpl_key = self._extract_tpl_key(tpl)

        if brief.content_goal:
            affinities = _GOAL_TEMPLATE_AFFINITY.get(brief.content_goal, [])
            if any(a in tpl.template_id or a == tpl_key for a in affinities):
                reasons.append(f"目标匹配: {brief.content_goal}")

        matched_scenes = [s for s in brief.target_scene if any(s in fs for fs in tpl.fit_scenarios)]
        if matched_scenes:
            reasons.append(f"场景: {', '.join(matched_scenes[:3])}")

        matched_styles = [s for s in brief.visual_style_direction if any(s in fs for fs in tpl.fit_styles)]
        if matched_styles:
            reasons.append(f"风格: {', '.join(matched_styles[:3])}")

        for hint in brief.template_hints:
            if hint in tpl.template_id or hint == tpl_key:
                reasons.append(f"模板提示命中: {hint}")
                break

        return "; ".join(reasons) if reasons else tpl.template_name

    # ── 旧逻辑（向后兼容） ──

    _TEMPLATE_KEYWORDS: dict[str, list[str]] = {
        "scene_seed": ["氛围", "仪式感", "场景", "桌搭", "下午茶", "早餐", "居家", "周末", "餐桌布置", "拍照", "出片", "vlog"],
        "style_anchor": ["风格", "奶油风", "法式", "北欧", "ins", "复古", "中古", "日式", "韩式", "美式", "极简", "田园"],
        "texture_detail": ["质感", "材质", "纹理", "蕾丝", "刺绣", "棉麻", "手感", "细节", "特写", "肌理", "面料", "触感"],
        "affordable_makeover": ["平价", "改造", "百元", "学生", "租房", "焕新", "性价比", "低成本", "出租屋", "便宜", "白菜价", "省钱"],
        "festival_gift": ["节日", "圣诞", "生日", "礼物", "送礼", "纪念日", "情人节", "过年", "新年", "母亲节", "礼盒", "节庆"],
        "set_combo": ["套装", "搭配", "组合", "方案", "件套", "全套", "桌搭方案", "一键", "搭配指南", "配套"],
    }

    @staticmethod
    def _extract_tpl_key(tpl: TableclothMainImageStrategyTemplate) -> str:
        return tpl.template_id.replace("tpl_00", "").lstrip("0123456789_")

    def _score_template(
        self,
        tpl: TableclothMainImageStrategyTemplate,
        opp_card: dict | None,
        product_brief: str,
        intent: str,
    ) -> float:
        score = 0.0
        text = f"{product_brief} {intent}"

        intent_map = {
            "种草": ["scene_seed", "style_anchor"],
            "转化": ["texture_detail", "affordable_makeover"],
            "礼赠": ["festival_gift"],
            "平价改造": ["affordable_makeover"],
        }
        if intent in intent_map:
            for key in intent_map[intent]:
                if key in tpl.template_id:
                    score += 0.4
                    break

        tpl_key = self._extract_tpl_key(tpl)
        kw_list = self._TEMPLATE_KEYWORDS.get(tpl_key, [])
        kw_hits = sum(1 for kw in kw_list if kw in text)
        if kw_hits >= 3:
            score += 0.35
        elif kw_hits >= 2:
            score += 0.25
        elif kw_hits >= 1:
            score += 0.15

        for scenario in tpl.fit_scenarios:
            if scenario in text:
                score += 0.08

        for style in tpl.fit_styles:
            if style in text:
                score += 0.06

        for phrase in (tpl.copy_rules.recommended_phrases if tpl.copy_rules else []):
            tokens = list(phrase) if len(phrase) <= 6 else [phrase[i:i+2] for i in range(0, len(phrase), 2)]
            for token in tokens[:4]:
                if token in text:
                    score += 0.02
                    break

        if opp_card:
            card_type = str(opp_card.get("opportunity_type", "")).lower()
            if "visual" in card_type and "scene" in tpl.template_id:
                score += 0.2
            if "selling" in card_type and "affordable" in tpl.template_id:
                score += 0.2

        return min(score, 1.0)

    def _explain_score(
        self,
        tpl: TableclothMainImageStrategyTemplate,
        opp_card: dict | None,
        product_brief: str,
        intent: str,
    ) -> str:
        reasons = []
        text = f"{product_brief} {intent}"
        if intent:
            reasons.append(f"意图: {intent}")

        tpl_key = self._extract_tpl_key(tpl)
        kw_list = self._TEMPLATE_KEYWORDS.get(tpl_key, [])
        matched_kws = [kw for kw in kw_list if kw in text]
        if matched_kws:
            reasons.append(f"关键词: {', '.join(matched_kws[:4])}")

        matched_scenarios = [s for s in tpl.fit_scenarios if s in text]
        if matched_scenarios:
            reasons.append(f"场景: {', '.join(matched_scenarios[:3])}")

        matched_styles = [s for s in tpl.fit_styles if s in text]
        if matched_styles:
            reasons.append(f"风格: {', '.join(matched_styles[:3])}")

        return "; ".join(reasons) if reasons else tpl.template_name
