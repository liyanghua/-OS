"""模板匹配器：根据机会卡 + 商品简介 + 意图匹配最佳模板。

支持三种模式：
1. LLM 驱动（优先）：一次 LLM 调用评估全部模板，输出结构化评分
2. brief-aware 规则（LLM 不可用时降级）：关键词子串匹配
3. 旧模式（向后兼容）：opportunity_card dict + product_brief 文本
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from apps.content_planning.services.prompt_registry import load_prompt
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
    matched_dimensions: dict[str, float] | None = None


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

        优先级：LLM 驱动 > brief-aware 规则 > 旧模式关键词匹配。
        """
        if brief is not None:
            llm_results = self._try_llm_match(brief)
            if llm_results:
                llm_results.sort(key=lambda x: x.score, reverse=True)
                return llm_results[:top_k]

        scores = []
        for tpl_id, tpl in self._templates.items():
            if brief is not None:
                score, dimensions = self._score_with_brief(tpl, brief)
                reason = self._explain_brief_score(tpl, brief)
                matched_dims = dimensions
            else:
                score = self._score_template(tpl, opportunity_card, product_brief, intent)
                reason = self._explain_score(tpl, opportunity_card, product_brief, intent)
                matched_dims = None
            scores.append(
                MatchResult(
                    template_id=tpl_id,
                    template_name=tpl.template_name,
                    score=score,
                    reason=reason,
                    matched_dimensions=matched_dims,
                )
            )
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[:top_k]

    # ── LLM 驱动匹配 ──

    def _try_llm_match(self, brief: OpportunityBrief) -> list[MatchResult] | None:
        """一次 LLM 调用评估全部模板。失败时返回 None 触发 fallback。"""
        try:
            from apps.intel_hub.extraction.llm_client import (
                call_text_llm,
                is_llm_available,
                parse_json_response,
            )
        except ImportError:
            return None
        if not is_llm_available():
            return None

        brief_summary = self._build_brief_summary(brief)
        tpl_summaries = self._build_templates_summary()

        prompt_cfg = load_prompt("template_match")
        system = prompt_cfg["system"]
        user = prompt_cfg["user_template"].format(
            brief_summary=brief_summary, templates_summary=tpl_summaries
        )

        try:
            raw = call_text_llm(system, user, temperature=0.2)
            if not raw:
                return None
            data = parse_json_response(raw)
            if isinstance(data, dict) and "results" in data:
                data = data["results"]
            if isinstance(data, dict):
                data = list(data.values()) if all(isinstance(v, dict) for v in data.values()) else None
            if not isinstance(data, list):
                raw_stripped = raw.strip()
                if raw_stripped.startswith("["):
                    try:
                        data = json.loads(raw_stripped)
                    except json.JSONDecodeError:
                        return None
                else:
                    return None

            results = self._parse_llm_scores(data)
            if len(results) >= len(self._templates) // 2:
                logger.info("LLM 模板匹配成功，返回 %d 个评分", len(results))
                return results
            return None
        except Exception:
            logger.debug("LLM 模板匹配失败，降级到规则匹配", exc_info=True)
            return None

    def _build_brief_summary(self, brief: OpportunityBrief) -> str:
        lines = []
        if brief.opportunity_title:
            lines.append(f"- 标题: {brief.opportunity_title}")
        if brief.content_goal:
            lines.append(f"- 内容目标: {brief.content_goal}")
        if brief.target_scene:
            lines.append(f"- 目标场景: {', '.join(brief.target_scene[:5])}")
        if brief.primary_value:
            lines.append(f"- 核心价值: {brief.primary_value}")
        if brief.visual_style_direction:
            lines.append(f"- 视觉风格: {', '.join(brief.visual_style_direction[:4])}")
        if brief.template_hints:
            lines.append(f"- 模板偏好: {', '.join(brief.template_hints[:4])}")
        if brief.avoid_directions:
            lines.append(f"- 规避方向: {', '.join(brief.avoid_directions[:3])}")
        if brief.secondary_values:
            lines.append(f"- 次要卖点: {', '.join(brief.secondary_values[:3])}")
        return "\n".join(lines) if lines else "（无详情）"

    def _build_templates_summary(self) -> str:
        lines = []
        for tpl in self._templates.values():
            parts = [
                f"ID={tpl.template_id}",
                f"名称={tpl.template_name}",
                f"目标={tpl.template_goal[:40]}",
            ]
            if tpl.fit_scenarios:
                parts.append(f"场景={','.join(tpl.fit_scenarios[:3])}")
            if tpl.fit_styles:
                parts.append(f"风格={','.join(tpl.fit_styles[:3])}")
            if tpl.best_for:
                parts.append(f"适用={','.join(tpl.best_for[:3])}")
            if tpl.avoid_when:
                parts.append(f"不适用={','.join(tpl.avoid_when[:2])}")
            lines.append(f"- {' | '.join(parts)}")
        return "\n".join(lines)

    @staticmethod
    def _parse_matched_dimensions(item: dict[str, Any]) -> dict[str, float] | None:
        raw = item.get("matched_dimensions") or item.get("dimension_scores")
        if not isinstance(raw, dict):
            return None
        out: dict[str, float] = {}
        for key in ("scene", "goal", "style", "hook", "avoid"):
            if key not in raw:
                continue
            try:
                v = float(raw[key])
            except (TypeError, ValueError):
                continue
            if v > 1.0 or v < -1.0:
                v = max(-1.0, min(v / 100.0, 1.0))
            else:
                v = max(-1.0, min(v, 1.0))
            out[key] = v
        return out or None

    def _parse_llm_scores(self, data: list[Any]) -> list[MatchResult]:
        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            tid = item.get("template_id", "")
            if tid not in self._templates:
                continue
            try:
                score_raw = item.get("score", 0)
                score = max(0.0, min(float(score_raw) / 100.0, 1.0))
            except (ValueError, TypeError):
                score = 0.0
            reason = str(item.get("reason", self._templates[tid].template_name))
            matched_dims = self._parse_matched_dimensions(item)
            results.append(MatchResult(
                template_id=tid,
                template_name=self._templates[tid].template_name,
                score=score,
                reason=reason,
                matched_dimensions=matched_dims,
            ))
        return results

    # ── brief-aware 打分 ──

    def _score_with_brief(
        self,
        tpl: TableclothMainImageStrategyTemplate,
        brief: OpportunityBrief,
    ) -> tuple[float, dict[str, float]]:
        dimensions: dict[str, float] = {
            "scene": 0.0,
            "goal": 0.0,
            "style": 0.0,
            "hook": 0.0,
            "avoid": 0.0,
        }
        score = 0.0
        tpl_key = self._extract_tpl_key(tpl)

        if brief.content_goal:
            affinities = _GOAL_TEMPLATE_AFFINITY.get(brief.content_goal, [])
            if any(a in tpl.template_id or a == tpl_key for a in affinities):
                dimensions["goal"] += 0.30
                score += 0.30

        scene_hits = sum(1 for s in brief.target_scene if any(s in fs for fs in tpl.fit_scenarios))
        scene_add = min(scene_hits * 0.10, 0.30)
        dimensions["scene"] = scene_add
        score += scene_add

        style_hits = sum(1 for s in brief.visual_style_direction if any(s in fs for fs in tpl.fit_styles))
        style_add = min(style_hits * 0.08, 0.24)
        dimensions["style"] = style_add
        score += style_add

        if brief.primary_value:
            hooks = " ".join(tpl.hook_mechanism) + " " + " ".join(tpl.best_for)
            if brief.primary_value in hooks:
                dimensions["hook"] += 0.15
                score += 0.15

        for hint in brief.template_hints:
            if hint in tpl.template_id or hint == tpl_key:
                dimensions["hook"] += 0.20
                score += 0.20
                break

        if brief.avoid_directions:
            avoid_when = " ".join(tpl.avoid_when)
            overlap = sum(1 for a in brief.avoid_directions if a in avoid_when)
            avoid_penalty = overlap * 0.10
            dimensions["avoid"] -= avoid_penalty
            score -= avoid_penalty

        final = max(min(score, 1.0), 0.0)
        return final, dimensions

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
