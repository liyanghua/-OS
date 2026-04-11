"""ExpertScorer: 对机会卡进行 8 维专家评分，输出 ExpertScorecard。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from apps.content_planning.schemas.expert_scorecard import (
    ExpertScorecard,
    ScorecardDimension,
)
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "scorecard_weights.yaml"


def _load_config() -> dict[str, Any]:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class ExpertScorer:
    """规则优先的 8 维评分器。LLM 可用时可升级。"""

    def __init__(self) -> None:
        self._cfg = _load_config()
        self._dim_cfg: dict[str, dict] = self._cfg.get("dimensions", {})
        self._conf_cfg: dict[str, float] = self._cfg.get("confidence_components", {})

    def score(
        self,
        card: XHSOpportunityCard,
        note_context: dict[str, Any] | None = None,
    ) -> ExpertScorecard:
        ctx = note_context or {}
        dims = self._score_all_dimensions(card, ctx)

        scorecard = ExpertScorecard(
            card_id=card.opportunity_id,
            opportunity_id=card.opportunity_id,
            dimensions=dims,
        )
        scorecard.sync_dimension_scores()
        scorecard.compute_total_score()
        scorecard.compute_recommendation()

        scorecard.confidence = self._compute_confidence(card, ctx)
        scorecard.score_reasons = self._build_score_reasons(scorecard)
        scorecard.blocking_risks = self._build_blocking_risks(scorecard)
        scorecard.upgrade_advice = self._build_upgrade_advice(scorecard)

        return scorecard

    def _score_all_dimensions(
        self, card: XHSOpportunityCard, ctx: dict[str, Any]
    ) -> list[ScorecardDimension]:
        dim_funcs: dict[str, Any] = {
            "demand_strength": self._score_demand_strength,
            "differentiation": self._score_differentiation,
            "commerce_fit": self._score_commerce_fit,
            "scalability": self._score_scalability,
            "reusability": self._score_reusability,
            "visual_potential": self._score_visual_potential,
            "video_potential": self._score_video_potential,
            "risk_score": self._score_risk,
        }
        dims: list[ScorecardDimension] = []
        for name, func in dim_funcs.items():
            cfg = self._dim_cfg.get(name, {})
            score_val, evidence, explanation = func(card, ctx)
            dims.append(ScorecardDimension(
                name=name,
                label=cfg.get("label", name),
                score=_clamp(score_val),
                weight=cfg.get("weight", 0.1),
                inverse=cfg.get("inverse", False),
                evidence_sources=evidence,
                explanation=explanation,
            ))
        return dims

    # ── 各维度计算 ──────────────────────────────────────

    @staticmethod
    def _score_demand_strength(
        card: XHSOpportunityCard, ctx: dict[str, Any]
    ) -> tuple[float, list[str], str]:
        evidence: list[str] = []
        collect = ctx.get("collect_count", 0) or 0
        like = ctx.get("like_count", 0) or 0
        comment = ctx.get("comment_count", 0) or 0

        collect_ratio = collect / max(like, 1) if like > 0 else 0
        collect_score = min(collect_ratio / 0.8, 1.0)
        evidence.append(f"collect_ratio={collect_ratio:.2f}")

        comment_intent = 0.0
        if comment >= 20:
            comment_intent = min(comment / 50, 1.0)
            evidence.append(f"comment_count={comment}")

        deep_interaction = 0.0
        total = like + collect + comment
        if total > 0:
            deep_interaction = min((collect + comment) / max(total, 1), 1.0)
            evidence.append(f"deep_ratio={deep_interaction:.2f}")

        timeliness = 0.5
        if card.why_now:
            timeliness = 0.8
            evidence.append("has_why_now")

        score = collect_score * 0.35 + comment_intent * 0.35 + deep_interaction * 0.20 + timeliness * 0.10
        return score, evidence, f"收藏率{collect_score:.2f}*0.35+评论{comment_intent:.2f}*0.35+深度{deep_interaction:.2f}*0.20+时效{timeliness:.2f}*0.10"

    @staticmethod
    def _score_differentiation(
        card: XHSOpportunityCard, ctx: dict[str, Any]
    ) -> tuple[float, list[str], str]:
        evidence: list[str] = []
        score = 0.3

        strength = card.opportunity_strength_score or 0
        if strength > 0:
            score = _clamp(strength * 0.7)
            evidence.append(f"strength_score={strength:.2f}")

        if card.content_angle:
            score = min(score + 0.2, 1.0)
            evidence.append("has_content_angle")

        if len(card.benchmark_refs) > 0:
            bench_penalty = min(len(card.benchmark_refs) * 0.05, 0.15)
            score = max(score - bench_penalty, 0.1)
            evidence.append(f"benchmarks={len(card.benchmark_refs)}")

        return score, evidence, "综合竞争差异度"

    @staticmethod
    def _score_commerce_fit(
        card: XHSOpportunityCard, ctx: dict[str, Any]
    ) -> tuple[float, list[str], str]:
        evidence: list[str] = []
        score = 0.2

        if card.selling_points:
            score += min(len(card.selling_points) * 0.15, 0.4)
            evidence.append(f"selling_points={len(card.selling_points)}")

        if card.entity_refs:
            score += min(len(card.entity_refs) * 0.1, 0.3)
            evidence.append(f"entity_refs={len(card.entity_refs)}")

        if ctx.get("commerce_mapping") or ctx.get("goods_tags"):
            score = min(score + 0.2, 1.0)
            evidence.append("has_commerce_data")

        return _clamp(score), evidence, "商品承接适配度"

    @staticmethod
    def _score_scalability(
        card: XHSOpportunityCard, ctx: dict[str, Any]
    ) -> tuple[float, list[str], str]:
        evidence: list[str] = []
        score = 0.4

        if card.scene_refs:
            scene_boost = min(len(card.scene_refs) * 0.1, 0.3)
            score += scene_boost
            evidence.append(f"scenes={len(card.scene_refs)}")

        if card.audience_refs:
            audience_boost = min(len(card.audience_refs) * 0.1, 0.2)
            score += audience_boost
            evidence.append(f"audiences={len(card.audience_refs)}")

        return _clamp(score), evidence, "可规模化评估"

    @staticmethod
    def _score_reusability(
        card: XHSOpportunityCard, ctx: dict[str, Any]
    ) -> tuple[float, list[str], str]:
        evidence: list[str] = []
        score = 0.3

        if card.format_suggestion:
            score += 0.2
            evidence.append("has_format_suggestion")

        if card.style_refs:
            score += min(len(card.style_refs) * 0.1, 0.3)
            evidence.append(f"style_refs={len(card.style_refs)}")

        return _clamp(score), evidence, "模板可复用度"

    @staticmethod
    def _score_visual_potential(
        card: XHSOpportunityCard, ctx: dict[str, Any]
    ) -> tuple[float, list[str], str]:
        evidence: list[str] = []
        score = 0.3

        if card.visual_pattern_refs:
            score += min(len(card.visual_pattern_refs) * 0.15, 0.4)
            evidence.append(f"visual_patterns={len(card.visual_pattern_refs)}")

        if card.style_refs:
            score += min(len(card.style_refs) * 0.1, 0.2)
            evidence.append(f"style_refs={len(card.style_refs)}")

        note_type = ctx.get("type", ctx.get("note_type", ""))
        if note_type in ("video", "image"):
            score = min(score + 0.1, 1.0)
            evidence.append(f"note_type={note_type}")

        return _clamp(score), evidence, "视觉潜力评估"

    @staticmethod
    def _score_video_potential(
        card: XHSOpportunityCard, ctx: dict[str, Any]
    ) -> tuple[float, list[str], str]:
        evidence: list[str] = []
        score = 0.2

        note_type = ctx.get("type", ctx.get("note_type", ""))
        if note_type == "video":
            score = 0.7
            evidence.append("source_is_video")

        if card.format_suggestion and "视频" in card.format_suggestion:
            score = min(score + 0.2, 1.0)
            evidence.append("format_suggests_video")

        return _clamp(score), evidence, "视频潜力评估"

    @staticmethod
    def _score_risk(
        card: XHSOpportunityCard, ctx: dict[str, Any]
    ) -> tuple[float, list[str], str]:
        """Risk: 0 = 无风险, 1 = 高风险。inverse=true 时自动反转。"""
        evidence: list[str] = []
        risk = 0.1

        if card.risk_refs:
            risk += min(len(card.risk_refs) * 0.15, 0.5)
            evidence.append(f"risk_refs={len(card.risk_refs)}")

        confidence = card.confidence or 0.5
        if confidence < 0.3:
            risk += 0.2
            evidence.append(f"low_confidence={confidence:.2f}")

        return _clamp(risk), evidence, "风险水平（越高越差）"

    # ── confidence 计算 ─────────────────────────────────

    def _compute_confidence(self, card: XHSOpportunityCard, ctx: dict[str, Any]) -> float:
        fc = self._conf_cfg.get("field_completeness", 0.30)
        cs = self._conf_cfg.get("comment_sample_size", 0.25)
        bc = self._conf_cfg.get("benchmark_count", 0.25)
        cd = self._conf_cfg.get("commerce_data", 0.20)

        core_fields = [card.title, card.summary, card.audience, card.scene, card.hook]
        field_fill = sum(1 for f in core_fields if f) / max(len(core_fields), 1)

        comment_count = ctx.get("comment_count", 0) or 0
        comment_fill = min(comment_count / 20, 1.0)

        bench_fill = min(len(card.benchmark_refs) / 3, 1.0)

        has_commerce = 1.0 if (card.selling_points or ctx.get("commerce_mapping")) else 0.0

        return _clamp(field_fill * fc + comment_fill * cs + bench_fill * bc + has_commerce * cd)

    # ── 推荐理由 ───────────────────────────────────────

    @staticmethod
    def _build_score_reasons(sc: ExpertScorecard) -> list[str]:
        reasons: list[str] = []
        for dim in sc.dimensions:
            if dim.score >= 0.7 and not dim.inverse:
                reasons.append(f"{dim.label}突出 ({dim.score:.2f})")
        if sc.total_score >= 0.7:
            reasons.append("综合评分高，建议启动")
        return reasons[:5]

    @staticmethod
    def _build_blocking_risks(sc: ExpertScorecard) -> list[str]:
        risks: list[str] = []
        for dim in sc.dimensions:
            if dim.name == "risk_score" and dim.score > 0.6:
                risks.append(f"风险维度较高 ({dim.score:.2f}): {dim.explanation}")
            elif dim.score < 0.3 and not dim.inverse:
                risks.append(f"{dim.label}偏弱 ({dim.score:.2f})")
        return risks[:5]

    @staticmethod
    def _build_upgrade_advice(sc: ExpertScorecard) -> list[str]:
        advice: list[str] = []
        for dim in sc.dimensions:
            if dim.inverse:
                continue
            if dim.score < 0.5:
                advice.append(f"提升 {dim.label}：补充 {', '.join(dim.evidence_sources[:2]) or '更多数据'}")
        if sc.confidence < 0.5:
            advice.append("数据完整度不足，建议补充评论/benchmark/商品数据")
        return advice[:5]
