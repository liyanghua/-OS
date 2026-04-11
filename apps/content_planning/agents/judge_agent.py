"""Judge Agent: Evaluates asset quality, plan consistency, and variant comparison.

Powers the Asset Workspace with quality scoring, risk identification,
and side-by-side variant comparison (VariantSet).
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.schemas.action_spec import ActionSpec

logger = logging.getLogger(__name__)


class JudgeDimension(BaseModel):
    """Single evaluation dimension."""
    name: str = ""
    name_zh: str = ""
    score: float = 0.0
    comment: str = ""


class VariantScore(BaseModel):
    """Score for a single variant in a VariantSet."""
    variant_id: str = ""
    variant_label: str = ""
    total_score: float = 0.0
    dimensions: list[JudgeDimension] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class JudgeResult(BaseModel):
    """Full judge evaluation result."""
    overall_score: float = 0.0
    plan_consistency: float = 0.0
    risk_level: str = "low"  # low | medium | high
    risks: list[str] = Field(default_factory=list)
    dimensions: list[JudgeDimension] = Field(default_factory=list)
    recommendation: str = ""
    actions: list[ActionSpec] = Field(default_factory=list)


class VariantSetComparison(BaseModel):
    """Side-by-side variant comparison result."""
    variants: list[VariantScore] = Field(default_factory=list)
    recommended_variant_id: str = ""
    recommendation_reason: str = ""
    comparison_summary: str = ""


class JudgeAgent:
    """Evaluate asset quality and compare variants."""

    def evaluate(
        self,
        asset_bundle: Any,
        plan: Any = None,
        strategy: Any = None,
        opportunity_id: str = "",
    ) -> JudgeResult:
        """Evaluate asset bundle quality against plan and strategy."""
        result = JudgeResult()

        if asset_bundle is None:
            result.overall_score = 0.0
            result.risk_level = "high"
            result.risks.append("资产包为空")
            result.actions.append(ActionSpec(
                action_type="regenerate", target_object="asset",
                label="组装资产包",
                api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
                priority=10,
            ))
            return result

        # Basic structural checks
        titles = getattr(asset_bundle, "title_candidates", None)
        body = getattr(asset_bundle, "body_draft", None)

        if not titles:
            result.risks.append("缺少标题候选")
            result.dimensions.append(JudgeDimension(name="titles", name_zh="标题", score=0.0, comment="无标题"))
        else:
            count = len(titles) if isinstance(titles, list) else 1
            result.dimensions.append(JudgeDimension(
                name="titles", name_zh="标题", score=min(count / 3.0, 1.0),
                comment=f"{count} 个候选",
            ))

        if not body:
            result.risks.append("缺少正文草稿")
            result.dimensions.append(JudgeDimension(name="body", name_zh="正文", score=0.0, comment="无正文"))
        else:
            body_len = len(str(body))
            result.dimensions.append(JudgeDimension(
                name="body", name_zh="正文", score=min(body_len / 500.0, 1.0),
                comment=f"长度 {body_len}",
            ))

        # Plan consistency
        if plan is not None:
            result.plan_consistency = 0.7  # Default moderate
        else:
            result.plan_consistency = 0.3
            result.risks.append("无法校验与计划的一致性（计划未提供）")

        # LLM deep evaluation
        if llm_router.is_any_available() and (titles or body):
            llm_eval = self._llm_evaluate(asset_bundle, plan, strategy)
            if llm_eval:
                result.overall_score = llm_eval.get("score", 0.5)
                result.recommendation = llm_eval.get("recommendation", "")
                llm_risks = llm_eval.get("risks", [])
                if isinstance(llm_risks, list):
                    result.risks.extend(str(r) for r in llm_risks)
        else:
            dim_scores = [d.score for d in result.dimensions] if result.dimensions else [0.5]
            result.overall_score = sum(dim_scores) / len(dim_scores)

        result.risk_level = "high" if len(result.risks) >= 3 else "medium" if result.risks else "low"

        if result.overall_score < 0.5:
            result.actions.append(ActionSpec(
                action_type="regenerate", target_object="asset",
                label="重新生成资产包",
                api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
                priority=8,
            ))
        result.actions.append(ActionSpec(
            action_type="export", target_object="asset",
            label="导出资产包",
            api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
            payload={"action": "export"},
            priority=3,
        ))

        return result

    def compare_variants(
        self,
        variants: list[dict[str, Any]],
        plan: Any = None,
    ) -> VariantSetComparison:
        """Compare multiple asset variants side-by-side."""
        result = VariantSetComparison()
        if not variants:
            return result

        for i, v in enumerate(variants):
            vid = v.get("variant_id", f"v{i}")
            vs = VariantScore(
                variant_id=vid,
                variant_label=v.get("label", f"变体 {i + 1}"),
            )
            titles = v.get("titles", [])
            body = v.get("body", "")
            title_score = min(len(titles) / 3.0, 1.0) if titles else 0.0
            body_score = min(len(str(body)) / 500.0, 1.0) if body else 0.0
            vs.total_score = (title_score + body_score) / 2.0
            vs.dimensions = [
                JudgeDimension(name="titles", name_zh="标题", score=title_score),
                JudgeDimension(name="body", name_zh="正文", score=body_score),
            ]
            result.variants.append(vs)

        if result.variants:
            best = max(result.variants, key=lambda v: v.total_score)
            result.recommended_variant_id = best.variant_id
            result.recommendation_reason = f"{best.variant_label} 综合评分最高 ({best.total_score:.2f})"
            scores_text = ", ".join(f"{v.variant_label}={v.total_score:.2f}" for v in result.variants)
            result.comparison_summary = f"变体对比：{scores_text}"

        return result

    def _llm_evaluate(self, asset_bundle: Any, plan: Any, strategy: Any) -> dict[str, Any] | None:
        try:
            asset_text = str(asset_bundle)[:1500]
            plan_text = str(plan)[:500] if plan else "无"
            strategy_text = str(strategy)[:500] if strategy else "无"

            resp = llm_router.chat_json(
                [
                    LLMMessage(
                        role="system",
                        content=(
                            "你是内容质量评审专家。评估资产包质量。返回 JSON："
                            '{"score":0.0-1.0,"recommendation":"...","risks":["..."]}'
                        ),
                    ),
                    LLMMessage(
                        role="user",
                        content=f"资产包：{asset_text}\n计划：{plan_text}\n策略：{strategy_text}",
                    ),
                ],
                temperature=0.2,
                max_tokens=600,
            )
            return resp if isinstance(resp, dict) else None
        except Exception:
            logger.debug("LLM evaluation failed", exc_info=True)
            return None
