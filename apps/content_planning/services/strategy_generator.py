"""RewriteStrategyGenerator：从 Brief + 模板匹配结果生成改写策略。

架构：LLM 生成全部字段 → 规则校验 + 兜底。LLM 不可用时整体降级到规则生成。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.services.prompt_registry import load_prompt
from apps.content_planning.schemas.template_match_result import TemplateMatchResult
from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate

logger = logging.getLogger(__name__)

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

_STR_FIELDS = (
    "positioning_statement", "new_hook", "new_angle", "tone_of_voice",
    "hook_strategy", "cta_strategy", "rationale",
)
_LIST_FIELDS = (
    "scene_emphasis", "keep_elements", "replace_elements", "enhance_elements",
    "avoid_elements", "title_strategy", "body_strategy", "image_strategy",
    "differentiation_axis", "risk_notes",
)


class RewriteStrategyGenerator:
    """LLM 优先 + 规则兜底的改写策略生成器。"""

    def generate(
        self,
        brief: OpportunityBrief,
        match_result: TemplateMatchResult,
        template: TableclothMainImageStrategyTemplate,
        *,
        llm_client: Any | None = None,
    ) -> RewriteStrategy:
        rule_strategy = self._rule_based_generate(brief, match_result, template)

        llm_strategy = self._try_llm_generate(brief, match_result, template, rule_strategy)
        if llm_strategy is not None:
            return llm_strategy

        return rule_strategy

    # ── LLM 主导生成 ──

    def _try_llm_generate(
        self,
        brief: OpportunityBrief,
        match_result: TemplateMatchResult,
        tpl: TableclothMainImageStrategyTemplate,
        fallback: RewriteStrategy,
    ) -> RewriteStrategy | None:
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

        constraints = self._build_constraints(brief, match_result, tpl)
        schema_hint = self._build_output_schema()

        prompt_cfg = load_prompt("strategy")
        system = prompt_cfg["system"]
        user = prompt_cfg["user_template"].format(constraints=constraints, schema_hint=schema_hint)

        try:
            raw = call_text_llm(system, user, temperature=0.4, max_tokens=3000)
            if not raw:
                return None
            data = parse_json_response(raw)
            if not data or not isinstance(data, dict):
                return None

            strategy = self._merge_llm_with_fallback(data, fallback, brief, tpl)
            logger.info("LLM 策略生成成功")
            return strategy
        except Exception:
            logger.debug("LLM 策略生成失败，降级到规则生成", exc_info=True)
            return None

    def _build_constraints(
        self,
        brief: OpportunityBrief,
        match_result: TemplateMatchResult,
        tpl: TableclothMainImageStrategyTemplate,
    ) -> str:
        lines: list[str] = []
        lines.append("### Brief 信息")
        if brief.opportunity_title:
            lines.append(f"- 机会标题: {brief.opportunity_title}")
        if brief.content_goal:
            lines.append(f"- 内容目标: {brief.content_goal}")
        if brief.primary_value:
            lines.append(f"- 核心价值: {brief.primary_value}")
        if brief.secondary_values:
            lines.append(f"- 次要卖点: {', '.join(brief.secondary_values[:4])}")
        if brief.target_scene:
            lines.append(f"- 目标场景: {', '.join(brief.target_scene[:4])}")
        if brief.visual_style_direction:
            lines.append(f"- 视觉风格: {', '.join(brief.visual_style_direction[:4])}")
        if brief.core_motive:
            lines.append(f"- 核心动机: {brief.core_motive}")
        if brief.avoid_directions:
            lines.append(f"- 规避方向: {', '.join(brief.avoid_directions[:4])}")
        if brief.why_worth_doing:
            lines.append(f"- 为什么值得做: {brief.why_worth_doing}")
        if brief.competitive_angle:
            lines.append(f"- 差异化切入: {brief.competitive_angle}")

        lines.append(f"\n### 选中模板: {tpl.template_name}")
        lines.append(f"- 模板目标: {tpl.template_goal}")
        if tpl.hook_mechanism:
            lines.append(f"- 钩子机制: {', '.join(tpl.hook_mechanism[:3])}")
        if tpl.copy_rules.title_style:
            lines.append(f"- 标题风格: {', '.join(tpl.copy_rules.title_style[:3])}")
        if tpl.copy_rules.avoid_phrases:
            lines.append(f"- 禁用话术: {', '.join(tpl.copy_rules.avoid_phrases[:4])}")
        if tpl.visual_rules.preferred_shots:
            lines.append(f"- 推荐景别: {', '.join(tpl.visual_rules.preferred_shots[:3])}")
        if tpl.visual_rules.color_direction:
            lines.append(f"- 色彩方向: {', '.join(tpl.visual_rules.color_direction[:3])}")
        seq = tpl.image_sequence_pattern[:5]
        if seq:
            readable = [_SEQ_CN.get(r, r) for r in seq]
            lines.append(f"- 图组顺序: {'→'.join(readable)}")
        if tpl.risk_rules:
            lines.append(f"- 风险提醒: {'; '.join(tpl.risk_rules[:3])}")
        if tpl.best_for:
            lines.append(f"- 最适用: {', '.join(tpl.best_for[:3])}")

        primary = match_result.primary_template
        lines.append(f"\n### 匹配信息")
        lines.append(f"- 匹配分: {primary.score:.2f}")
        if primary.reason:
            lines.append(f"- 匹配理由: {primary.reason}")
        if primary.matched_dimensions:
            dim_parts = [
                f"{k}: {v:.2f}"
                for k, v in sorted(
                    primary.matched_dimensions.items(),
                    key=lambda kv: (-abs(kv[1]), kv[0]),
                )
            ]
            lines.append(f"- 各维度得分: {'; '.join(dim_parts)}")
        secondary = match_result.secondary_templates[:3]
        if secondary:
            cand_bits = []
            for t in secondary:
                bit = f"{t.template_name}（{t.score:.2f}）"
                if t.matched_dimensions:
                    top_dim = max(t.matched_dimensions.items(), key=lambda kv: abs(kv[1]))[0]
                    bit += f"·{top_dim}"
                cand_bits.append(bit)
            lines.append(f"- 备选候选: {' | '.join(cand_bits)}")

        return "\n".join(lines)

    @staticmethod
    def _build_output_schema() -> str:
        return json.dumps({
            "positioning_statement": "一句话内容定位",
            "new_hook": "钩子句式",
            "new_angle": "切入角度",
            "tone_of_voice": "语气口吻",
            "hook_strategy": "钩子策略描述",
            "cta_strategy": "行动号召策略",
            "scene_emphasis": ["场景1", "场景2"],
            "rationale": "策略选择依据",
            "keep_elements": ["保留元素1"],
            "replace_elements": ["替换元素1"],
            "enhance_elements": ["强化元素1"],
            "avoid_elements": ["避免元素1"],
            "title_strategy": ["标题策略1", "标题策略2"],
            "body_strategy": ["正文策略1", "正文策略2"],
            "image_strategy": ["图片策略1", "图片策略2"],
            "differentiation_axis": ["差异化主轴1"],
            "risk_notes": ["风险备注1"],
        }, ensure_ascii=False, indent=2)

    def _merge_llm_with_fallback(
        self,
        data: dict[str, Any],
        fallback: RewriteStrategy,
        brief: OpportunityBrief,
        tpl: TableclothMainImageStrategyTemplate,
    ) -> RewriteStrategy:
        """将 LLM 输出与规则兜底合并：LLM 有效字段优先，缺失字段用 fallback 填充。"""
        merged: dict[str, Any] = {
            "opportunity_id": brief.opportunity_id,
            "brief_id": brief.brief_id,
            "template_id": tpl.template_id,
            "strategy_status": "generated",
        }

        for field in _STR_FIELDS:
            llm_val = data.get(field)
            if isinstance(llm_val, str) and llm_val.strip():
                merged[field] = llm_val.strip()
            else:
                merged[field] = getattr(fallback, field)

        for field in _LIST_FIELDS:
            llm_val = data.get(field)
            if isinstance(llm_val, list) and llm_val:
                merged[field] = [str(v) for v in llm_val if v]
            else:
                merged[field] = getattr(fallback, field)

        # Build comparison note if LLM produced meaningful differences（字符串 + 列表字段）
        diffs: list[str] = []
        for field in _STR_FIELDS:
            if merged.get(field) != getattr(fallback, field) and merged.get(field):
                diffs.append(field)
        for field in _LIST_FIELDS:
            if merged.get(field) != getattr(fallback, field):
                diffs.append(field)
        if diffs:
            merged["comparison_note"] = f"LLM 优化了 {len(diffs)} 个字段：{'、'.join(diffs[:5])}"
        merged["editable_blocks"] = list(_STR_FIELDS) + list(_LIST_FIELDS)

        return RewriteStrategy(**merged)

    # ── 规则兜底层（保留完整，作为 fallback） ──

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

        hook_strategy = self._build_hook_strategy(brief, tpl)
        cta_strategy = self._build_cta_strategy(brief, tpl)
        scene_emphasis = list(brief.target_scene[:4])
        rationale = self._build_rationale(brief, match_result, tpl)

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
            strategy_status="generated",
            positioning_statement=positioning,
            new_hook=new_hook,
            new_angle=brief.core_motive or "",
            tone_of_voice=tone,
            hook_strategy=hook_strategy,
            cta_strategy=cta_strategy,
            scene_emphasis=scene_emphasis,
            rationale=rationale,
            keep_elements=keep,
            replace_elements=replace,
            enhance_elements=enhance,
            avoid_elements=list(dict.fromkeys(avoid))[:8],
            title_strategy=title_strategy,
            body_strategy=body_strategy,
            image_strategy=image_strategy,
            differentiation_axis=diff_axis[:4],
            risk_notes=risk_notes,
            strategy_version=1,
            editable_blocks=list(_STR_FIELDS) + list(_LIST_FIELDS),
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
    def _build_hook_strategy(brief: OpportunityBrief, tpl: TableclothMainImageStrategyTemplate) -> str:
        hooks = tpl.hook_mechanism[:2]
        scenes = brief.target_scene[:2]
        parts = []
        if hooks:
            parts.append(f"钩子机制: {'、'.join(hooks)}")
        if scenes:
            parts.append(f"场景代入: {'、'.join(scenes)}")
        if brief.primary_value:
            parts.append(f"利益前置: {brief.primary_value}")
        return "；".join(parts) if parts else "场景代入 + 利益点前置"

    @staticmethod
    def _build_cta_strategy(brief: OpportunityBrief, tpl: TableclothMainImageStrategyTemplate) -> str:
        goal = brief.content_goal or ""
        if "转化" in goal:
            return "引导购买（限时优惠/链接/同款搜索词）"
        if "种草" in goal:
            return "引导收藏 + 关注（「收藏备用」「关注看更多」）"
        return "收藏 + 关注 + 评论互动"

    @staticmethod
    def _build_rationale(
        brief: OpportunityBrief,
        match_result: TemplateMatchResult,
        tpl: TableclothMainImageStrategyTemplate,
    ) -> str:
        primary = match_result.primary_template
        parts = [
            f"选择模板「{tpl.template_name}」",
            f"匹配分 {primary.score:.2f}",
        ]
        if primary.reason:
            parts.append(primary.reason)
        if brief.content_goal:
            parts.append(f"内容目标: {brief.content_goal}")
        return "。".join(parts)
