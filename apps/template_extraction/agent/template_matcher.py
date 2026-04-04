"""模板匹配器：根据机会卡 + 商品简介 + 意图匹配最佳模板。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    template_id: str
    template_name: str
    score: float
    reason: str


class TemplateMatcher:
    def __init__(self, templates: list[TableclothMainImageStrategyTemplate]):
        self._templates = {t.template_id: t for t in templates}

    def match_templates(
        self,
        opportunity_card: dict | None = None,
        product_brief: str = "",
        intent: str = "",
        top_k: int = 3,
    ) -> list[MatchResult]:
        """匹配模板，返回 top_k 候选。

        intent 可选: "种草"/"转化"/"礼赠"/"平价改造"
        """
        scores = []
        for tpl_id, tpl in self._templates.items():
            score = self._score_template(tpl, opportunity_card, product_brief, intent)
            scores.append(
                MatchResult(
                    template_id=tpl_id,
                    template_name=tpl.template_name,
                    score=score,
                    reason=self._explain_score(tpl, opportunity_card, product_brief, intent),
                )
            )
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[:top_k]

    _TEMPLATE_KEYWORDS: dict[str, list[str]] = {
        "scene_seed": ["氛围", "仪式感", "场景", "桌搭", "下午茶", "早餐", "居家", "周末", "餐桌布置", "拍照", "出片", "vlog"],
        "style_anchor": ["风格", "奶油风", "法式", "北欧", "ins", "复古", "中古", "日式", "韩式", "美式", "极简", "田园"],
        "texture_detail": ["质感", "材质", "纹理", "蕾丝", "刺绣", "棉麻", "手感", "细节", "特写", "肌理", "面料", "触感"],
        "affordable_makeover": ["平价", "改造", "百元", "学生", "租房", "焕新", "性价比", "低成本", "出租屋", "便宜", "白菜价", "省钱"],
        "festival_gift": ["节日", "圣诞", "生日", "礼物", "送礼", "纪念日", "情人节", "过年", "新年", "母亲节", "礼盒", "节庆"],
        "set_combo": ["套装", "搭配", "组合", "方案", "件套", "全套", "桌搭方案", "一键", "搭配指南", "配套"],
    }

    def _score_template(
        self,
        tpl: TableclothMainImageStrategyTemplate,
        opp_card: dict | None,
        product_brief: str,
        intent: str,
    ) -> float:
        """综合评分：关键词 + 意图 + 场景 + 风格。"""
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

        tpl_key = tpl.template_id.replace("tpl_00", "").lstrip("0123456789_")
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
            for word in phrase[:4]:
                if word in text:
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

        tpl_key = tpl.template_id.replace("tpl_00", "").lstrip("0123456789_")
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
