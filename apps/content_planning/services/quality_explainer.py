"""QualityExplainer: 对比源笔记与生成结果，解释改进点与优化方向。"""

from __future__ import annotations

import json
import logging
from typing import Any

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.schemas.asset_bundle import AssetBundle
from apps.content_planning.schemas.compilation_report import ImprovementItem, QualityExplanation
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy

logger = logging.getLogger(__name__)


class QualityExplainer:
    """LLM 优先、规则兜底的生成质量解释器。"""

    def explain(
        self,
        source_note: dict[str, Any] | None,
        bundle: AssetBundle,
        strategy: RewriteStrategy | None = None,
        brief: OpportunityBrief | None = None,
    ) -> QualityExplanation:
        if llm_router.is_any_available():
            try:
                return self._llm_explain(source_note, bundle, strategy, brief)
            except Exception:
                logger.warning("LLM quality explanation failed, falling back to rules", exc_info=True)
        return self._rule_explain(source_note, bundle, strategy, brief)

    def _llm_explain(
        self,
        source_note: dict[str, Any] | None,
        bundle: AssetBundle,
        strategy: RewriteStrategy | None,
        brief: OpportunityBrief | None,
    ) -> QualityExplanation:
        source_title = (source_note or {}).get("title", "")
        source_body = (source_note or {}).get("body", "")[:500]

        best_title = ""
        if bundle.title_candidates:
            best_title = bundle.title_candidates[0].get("title_text", "") if isinstance(bundle.title_candidates[0], dict) else ""
        body_draft = (bundle.body_draft or "")[:500]

        strategy_summary = ""
        if strategy:
            strategy_summary = f"定位: {strategy.positioning_statement}\n钩子: {strategy.new_hook}\n语气: {strategy.tone_of_voice}"

        system = "你是小红书内容质量分析专家。请对比源笔记与 AI 生成笔记，给出结构化分析。"
        user = f"""## 源笔记
标题: {source_title}
正文: {source_body}

## 生成笔记
标题: {best_title}
正文: {body_draft}

## 策略方向
{strategy_summary}

请以 JSON 返回：
{{
  "improvements": [
    {{"dimension": "维度名", "before_label": "源笔记特征", "after_label": "生成笔记特征", "explanation": "改进说明", "impact": "预期影响"}}
  ],
  "strategy_alignment_score": 0.0-1.0,
  "engagement_factors": ["因素1", "因素2"],
  "suggestions": ["建议1", "建议2"],
  "risks": ["风险1"]
}}

维度包括：钩子吸引力、目标人群精准度、视觉方向、语气一致性、信息密度、CTA 有效性。"""

        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ]
        response = llm_router.chat(messages, temperature=0.3, max_tokens=1500)
        if response.degraded or not response.content.strip():
            raise RuntimeError("llm_degraded")

        text = response.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            end_idx = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
            text = "\n".join(lines[1:end_idx])
        data = json.loads(text)

        improvements = []
        for item in data.get("improvements", []):
            improvements.append(ImprovementItem(
                dimension=item.get("dimension", ""),
                before_label=item.get("before_label", ""),
                after_label=item.get("after_label", ""),
                explanation=item.get("explanation", ""),
                impact=item.get("impact", ""),
            ))

        return QualityExplanation(
            vs_source_improvements=improvements,
            strategy_alignment_score=min(1.0, max(0.0, float(data.get("strategy_alignment_score", 0.7)))),
            predicted_engagement_factors=data.get("engagement_factors", []),
            optimization_suggestions=data.get("suggestions", []),
            risk_flags=data.get("risks", []),
        )

    def _rule_explain(
        self,
        source_note: dict[str, Any] | None,
        bundle: AssetBundle,
        strategy: RewriteStrategy | None,
        brief: OpportunityBrief | None,
    ) -> QualityExplanation:
        improvements: list[ImprovementItem] = []
        suggestions: list[str] = []
        risks: list[str] = []
        engagement_factors: list[str] = []

        source_title = (source_note or {}).get("title", "")
        source_body = (source_note or {}).get("body", "")

        best_title = ""
        if bundle.title_candidates:
            c = bundle.title_candidates[0]
            best_title = c.get("title_text", "") if isinstance(c, dict) else ""

        if best_title and source_title:
            gen_len = len(best_title)
            src_len = len(source_title)
            if gen_len <= 20 and src_len > 20:
                improvements.append(ImprovementItem(
                    dimension="标题精炼度",
                    before_label=f"原标题 {src_len} 字，偏长",
                    after_label=f"优化标题 {gen_len} 字，符合小红书最佳长度",
                    explanation="小红书标题在 8-20 字时点击率最高",
                    impact="预期提升标题点击率",
                ))
            if any(ch in best_title for ch in "｜|！？") and not any(ch in source_title for ch in "｜|！？"):
                improvements.append(ImprovementItem(
                    dimension="钩子吸引力",
                    before_label="标题缺少分隔符/感叹号",
                    after_label="增加了视觉节奏符号",
                    explanation="分隔符和感叹号能增加标题的视觉吸引力和信息层次",
                    impact="预期提升标题停留时间",
                ))
                engagement_factors.append("标题视觉节奏优化")

        body_draft = bundle.body_draft or ""
        if body_draft and source_body:
            if len(body_draft.split("\n")) > len(source_body.split("\n")):
                improvements.append(ImprovementItem(
                    dimension="信息密度",
                    before_label="段落结构松散",
                    after_label="分段更清晰，信息层次更明确",
                    explanation="合理分段有助于手机端阅读",
                    impact="预期提升正文完读率",
                ))
                engagement_factors.append("正文段落结构优化")

        if strategy:
            if strategy.cta_strategy and strategy.cta_strategy in body_draft:
                improvements.append(ImprovementItem(
                    dimension="CTA 有效性",
                    before_label="无明确 CTA" if "收藏" not in source_body and "关注" not in source_body else "CTA 存在",
                    after_label=f"已植入策略 CTA: {strategy.cta_strategy[:20]}",
                    explanation="明确的行动号召可显著提升互动率",
                    impact="预期提升收藏/评论率",
                ))
                engagement_factors.append("策略 CTA 对齐")

            alignment = 0.5
            if strategy.positioning_statement and strategy.positioning_statement[:6] in body_draft:
                alignment += 0.2
            if strategy.tone_of_voice and any(kw in body_draft for kw in strategy.tone_of_voice.split("、")[:3]):
                alignment += 0.2
            if strategy.new_hook and strategy.new_hook[:6] in (best_title + body_draft[:100]):
                alignment += 0.1
        else:
            alignment = 0.6

        if not bundle.title_candidates or len(bundle.title_candidates) < 2:
            suggestions.append("建议生成更多标题候选以便 A/B 测试")
        if body_draft and len(body_draft) < 200:
            suggestions.append("正文偏短，建议补充更多场景描写或产品细节")
        if not bundle.image_execution_briefs:
            suggestions.append("缺少图片执行指令，建议补充封面图和内文图规划")
            risks.append("无图片指导可能导致视觉吸引力不足")

        if body_draft and ("最好" in body_draft or "第一" in body_draft or "绝对" in body_draft):
            risks.append("正文含绝对化用语，可能触发小红书审核")

        return QualityExplanation(
            vs_source_improvements=improvements,
            strategy_alignment_score=min(1.0, alignment),
            predicted_engagement_factors=engagement_factors or ["策划结构化改进", "模板方法论驱动"],
            optimization_suggestions=suggestions,
            risk_flags=risks,
        )
