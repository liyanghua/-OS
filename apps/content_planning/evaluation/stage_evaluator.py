"""阶段评估器：每个管线环节的质量评估（LLM + 规则双轨）。"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.schemas.evaluation import DimensionScore, StageEvaluation

logger = logging.getLogger(__name__)

_EVAL_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "prompts" / "evaluation.yaml"
_eval_config: dict[str, Any] | None = None


def _load_eval_config() -> dict[str, Any]:
    global _eval_config
    if _eval_config is not None:
        return _eval_config
    if not _EVAL_CONFIG_PATH.exists():
        logger.warning("evaluation.yaml not found at %s", _EVAL_CONFIG_PATH)
        _eval_config = {}
        return _eval_config
    with open(_EVAL_CONFIG_PATH, encoding="utf-8") as f:
        _eval_config = yaml.safe_load(f) or {}
    return _eval_config


def _get_stage_config(stage: str) -> dict[str, Any]:
    cfg = _load_eval_config()
    return cfg.get("evaluation", {}).get(stage, {})


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BaseStageEvaluator(ABC):
    """评估器基类——子类实现 stage / rule-based fallback / 上下文组装。"""

    stage: str = ""

    @abstractmethod
    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        """组装 LLM user prompt，子类必须实现。"""
        ...

    @abstractmethod
    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        """纯规则评分 fallback，子类必须实现。"""
        ...

    def evaluate(self, opportunity_id: str, context: dict[str, Any]) -> StageEvaluation:
        """执行评估：优先 LLM，失败回退规则。"""
        stage_cfg = _get_stage_config(self.stage)
        dim_cfgs: list[dict[str, Any]] = stage_cfg.get("dimensions", [])

        evaluation = StageEvaluation(opportunity_id=opportunity_id, stage=self.stage)  # type: ignore[arg-type]

        if llm_router.is_any_available():
            try:
                evaluation = self._llm_evaluate(opportunity_id, context, stage_cfg, dim_cfgs)
                evaluation.evaluator = "llm_judge"
                evaluation.compute_overall()
                return evaluation
            except Exception:
                logger.warning("LLM evaluation failed for %s/%s, falling back to rules",
                               self.stage, opportunity_id, exc_info=True)

        evaluation.dimensions = self._rule_based_scores(opportunity_id, context)
        evaluation.evaluator = "rule"
        evaluation.compute_overall()
        return evaluation

    # ---- LLM 评估 ----------------------------------------------------------

    def _llm_evaluate(
        self,
        opportunity_id: str,
        context: dict[str, Any],
        stage_cfg: dict[str, Any],
        dim_cfgs: list[dict[str, Any]],
    ) -> StageEvaluation:
        system_prompt = stage_cfg.get("system", "你是内容质量评审专家。")
        user_prompt = self._build_user_prompt(opportunity_id, context)

        dim_names = [d["name"] for d in dim_cfgs]
        output_hint = (
            "请以 JSON 返回评估结果，格式：\n"
            '{"scores": {"<dimension>": 0.0-1.0, ...}, '
            '"explanations": {"<dimension>": "简短说明", ...}}\n'
            f"维度列表：{dim_names}"
        )
        full_user = f"{user_prompt}\n\n{output_hint}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=full_user),
        ]
        result = llm_router.chat_json(messages, temperature=0.2, max_tokens=1500)

        scores_raw: dict[str, float] = result.get("scores", {})
        explanations: dict[str, str] = result.get("explanations", {})

        dim_map = {d["name"]: d for d in dim_cfgs}
        dimensions: list[DimensionScore] = []
        for name, cfg in dim_map.items():
            dimensions.append(DimensionScore(
                name=name,
                name_zh=cfg.get("name_zh", name),
                score=_clamp(scores_raw.get(name, 0.0)),
                weight=cfg.get("weight", 1.0),
                explanation=explanations.get(name, ""),
            ))

        resp = llm_router.chat(messages, temperature=0.2, max_tokens=1500)
        model_used = resp.model

        return StageEvaluation(
            opportunity_id=opportunity_id,
            stage=self.stage,  # type: ignore[arg-type]
            dimensions=dimensions,
            model_used=model_used,
        )


# ---------------------------------------------------------------------------
# CardEvaluator
# ---------------------------------------------------------------------------

class CardEvaluator(BaseStageEvaluator):
    """机会卡质量评估。"""

    stage = "card"

    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        card = context.get("card", {})
        parts = [
            "## 机会卡信息",
            f"- opportunity_id: {opportunity_id}",
            f"- 标题: {card.get('title', '')}",
            f"- 描述: {card.get('description', card.get('summary', ''))}",
            f"- 置信度: {card.get('confidence', 'N/A')}",
            f"- 强度评分: {card.get('strength_score', 'N/A')}",
            f"- 信号来源: {card.get('signals', card.get('source_signals', []))}",
            f"- 证据: {card.get('evidence', card.get('evidence_notes', []))}",
        ]
        return "\n".join(parts)

    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        card = context.get("card", {})
        confidence = _safe_float(card.get("confidence", 0))
        strength = _safe_float(card.get("strength_score", 0))
        signals = card.get("signals", card.get("source_signals", []))
        evidence = card.get("evidence", card.get("evidence_notes", []))

        signal_score = min(len(signals) / 5, 1.0) if isinstance(signals, list) else 0.3
        evidence_score = min(len(evidence) / 3, 1.0) if isinstance(evidence, list) else 0.3

        return [
            DimensionScore(name="signal_completeness", name_zh="信号完整度",
                           score=signal_score, weight=0.25,
                           explanation=f"检测到 {len(signals) if isinstance(signals, list) else '?'} 个信号源"),
            DimensionScore(name="actionability", name_zh="可执行性",
                           score=_clamp(strength), weight=0.25,
                           explanation=f"基于 strength_score={strength:.2f}"),
            DimensionScore(name="evidence_sufficiency", name_zh="证据充分度",
                           score=evidence_score, weight=0.25,
                           explanation=f"检测到 {len(evidence) if isinstance(evidence, list) else '?'} 条证据"),
            DimensionScore(name="insight_depth", name_zh="洞察深度",
                           score=_clamp(confidence), weight=0.25,
                           explanation=f"基于 confidence={confidence:.2f}，LLM 不可用时使用规则近似"),
        ]


# ---------------------------------------------------------------------------
# BriefEvaluator
# ---------------------------------------------------------------------------

class BriefEvaluator(BaseStageEvaluator):
    """Brief 质量评估。"""

    stage = "brief"

    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        card = context.get("card", {})
        brief = context.get("brief", {})
        if hasattr(brief, "model_dump"):
            brief = brief.model_dump()
        parts = [
            "## 机会卡摘要",
            f"- 标题: {card.get('title', '')}",
            f"- 描述: {card.get('description', card.get('summary', ''))}",
            "",
            "## OpportunityBrief 内容",
            json.dumps(brief, ensure_ascii=False, default=str)[:3000],
        ]
        return "\n".join(parts)

    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        brief = context.get("brief", {})
        if hasattr(brief, "model_dump"):
            brief = brief.model_dump()

        target_user = brief.get("target_user", [])
        target_scene = brief.get("target_scene", [])
        has_goal = bool(brief.get("content_goal"))
        has_competitive = bool(brief.get("competitive_angle"))
        field_count = sum(1 for v in brief.values() if v)
        depth = min(field_count / 15, 1.0)

        return [
            DimensionScore(name="planning_depth", name_zh="策划深度",
                           score=depth, weight=0.25,
                           explanation=f"Brief 已填写 {field_count} 个字段"),
            DimensionScore(name="user_targeting", name_zh="用户画像精度",
                           score=min(len(target_user) / 3, 1.0) if isinstance(target_user, list) else 0.3,
                           weight=0.20,
                           explanation=f"目标用户 {len(target_user) if isinstance(target_user, list) else 0} 项"),
            DimensionScore(name="scene_matching", name_zh="场景匹配度",
                           score=min(len(target_scene) / 3, 1.0) if isinstance(target_scene, list) else 0.3,
                           weight=0.20,
                           explanation=f"目标场景 {len(target_scene) if isinstance(target_scene, list) else 0} 项"),
            DimensionScore(name="competitive_differentiation", name_zh="竞争差异化",
                           score=0.7 if has_competitive else 0.2, weight=0.20,
                           explanation="competitive_angle 已填写" if has_competitive else "competitive_angle 为空"),
            DimensionScore(name="executability", name_zh="可执行性",
                           score=0.7 if has_goal else 0.3, weight=0.15,
                           explanation="content_goal 已填写" if has_goal else "content_goal 为空"),
        ]


# ---------------------------------------------------------------------------
# MatchEvaluator
# ---------------------------------------------------------------------------

class MatchEvaluator(BaseStageEvaluator):
    """模板匹配质量评估。"""

    stage = "match"

    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        brief = context.get("brief", {})
        if hasattr(brief, "model_dump"):
            brief = brief.model_dump()
        match_result = context.get("match_result", {})
        if hasattr(match_result, "model_dump"):
            match_result = match_result.model_dump()

        parts = [
            "## Brief 摘要",
            f"- 目标场景: {brief.get('target_scene', [])}",
            f"- 目标用户: {brief.get('target_user', [])}",
            "",
            "## 模板匹配结果",
            json.dumps(match_result, ensure_ascii=False, default=str)[:3000],
        ]
        return "\n".join(parts)

    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        match_result = context.get("match_result", {})
        if hasattr(match_result, "model_dump"):
            match_result = match_result.model_dump()

        top_entries = match_result.get("entries", match_result.get("matches", []))
        if not isinstance(top_entries, list):
            top_entries = []

        top1_score = top_entries[0].get("score", 0) if top_entries else 0
        top3_scores = [e.get("score", 0) for e in top_entries[:3]]
        gap = (top3_scores[0] - top3_scores[-1]) if len(top3_scores) >= 2 else 0

        return [
            DimensionScore(name="style_consistency", name_zh="风格一致性",
                           score=_clamp(top1_score), weight=0.30,
                           explanation=f"Top-1 匹配分={top1_score:.2f}"),
            DimensionScore(name="scene_fitness", name_zh="场景适配度",
                           score=_clamp(top1_score * 0.9), weight=0.30,
                           explanation="基于匹配分近似"),
            DimensionScore(name="hook_usability", name_zh="钩子可用性",
                           score=0.5 if top_entries else 0.0, weight=0.20,
                           explanation="规则模式下固定中等分"),
            DimensionScore(name="top_diversity", name_zh="候选多样性",
                           score=_clamp(1.0 - gap) if gap < 0.5 else 0.5, weight=0.20,
                           explanation=f"Top1-Top3 分差={gap:.2f}"),
        ]


# ---------------------------------------------------------------------------
# StrategyEvaluator
# ---------------------------------------------------------------------------

class StrategyEvaluator(BaseStageEvaluator):
    """策略质量评估。"""

    stage = "strategy"

    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        brief = context.get("brief", {})
        if hasattr(brief, "model_dump"):
            brief = brief.model_dump()
        strategy = context.get("strategy", {})
        if hasattr(strategy, "model_dump"):
            strategy = strategy.model_dump()

        parts = [
            "## Brief 摘要",
            json.dumps(brief, ensure_ascii=False, default=str)[:1500],
            "",
            "## 改写策略",
            json.dumps(strategy, ensure_ascii=False, default=str)[:2000],
        ]
        return "\n".join(parts)

    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        strategy = context.get("strategy", {})
        if hasattr(strategy, "model_dump"):
            strategy = strategy.model_dump()

        has_hook = bool(strategy.get("new_hook"))
        has_positioning = bool(strategy.get("positioning_statement"))
        has_title_strat = bool(strategy.get("title_strategy"))
        has_body_strat = bool(strategy.get("body_strategy"))
        filled = sum([has_hook, has_positioning, has_title_strat, has_body_strat])

        return [
            DimensionScore(name="differentiation", name_zh="差异化程度",
                           score=0.6 if has_hook else 0.2, weight=0.30,
                           explanation="new_hook 已填写" if has_hook else "new_hook 为空"),
            DimensionScore(name="executability", name_zh="可执行性",
                           score=min(filled / 4, 1.0), weight=0.25,
                           explanation=f"策略 {filled}/4 核心字段已填写"),
            DimensionScore(name="brief_alignment", name_zh="Brief对齐度",
                           score=0.5, weight=0.25,
                           explanation="规则模式下固定中等分"),
            DimensionScore(name="creativity", name_zh="创意新颖度",
                           score=0.4, weight=0.20,
                           explanation="规则模式下固定中等分"),
        ]


# ---------------------------------------------------------------------------
# ContentEvaluator
# ---------------------------------------------------------------------------

class ContentEvaluator(BaseStageEvaluator):
    """内容质量评估。"""

    stage = "content"

    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        strategy = context.get("strategy", {})
        if hasattr(strategy, "model_dump"):
            strategy = strategy.model_dump()
        titles = context.get("titles", {})
        if hasattr(titles, "model_dump"):
            titles = titles.model_dump()
        body = context.get("body", {})
        if hasattr(body, "model_dump"):
            body = body.model_dump()
        image_briefs = context.get("image_briefs", {})
        if hasattr(image_briefs, "model_dump"):
            image_briefs = image_briefs.model_dump()

        parts = [
            "## 改写策略",
            json.dumps(strategy, ensure_ascii=False, default=str)[:1000],
            "",
            "## 标题候选",
            json.dumps(titles, ensure_ascii=False, default=str)[:800],
            "",
            "## 正文",
            json.dumps(body, ensure_ascii=False, default=str)[:1500],
            "",
            "## 图片 Brief",
            json.dumps(image_briefs, ensure_ascii=False, default=str)[:800],
        ]
        return "\n".join(parts)

    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        titles = context.get("titles", {})
        if hasattr(titles, "model_dump"):
            titles = titles.model_dump()
        body = context.get("body", {})
        if hasattr(body, "model_dump"):
            body = body.model_dump()
        image_briefs = context.get("image_briefs", {})
        if hasattr(image_briefs, "model_dump"):
            image_briefs = image_briefs.model_dump()

        title_candidates = titles.get("candidates", titles.get("titles", []))
        has_titles = bool(title_candidates)
        body_text = body.get("body", body.get("text", ""))
        has_body = bool(body_text)
        slots = image_briefs.get("slots", image_briefs.get("images", []))
        has_images = bool(slots)

        return [
            DimensionScore(name="title_appeal", name_zh="标题吸引力",
                           score=0.6 if has_titles else 0.0, weight=0.25,
                           explanation=f"生成 {len(title_candidates) if isinstance(title_candidates, list) else 0} 个标题候选"),
            DimensionScore(name="body_structure", name_zh="正文结构性",
                           score=min(len(str(body_text)) / 500, 1.0) if has_body else 0.0,
                           weight=0.30,
                           explanation=f"正文长度 {len(str(body_text))} 字符"),
            DimensionScore(name="image_brief_quality", name_zh="图片Brief可执行度",
                           score=0.6 if has_images else 0.0, weight=0.25,
                           explanation=f"图片 Brief {len(slots) if isinstance(slots, list) else 0} 个 slot"),
            DimensionScore(name="overall_coherence", name_zh="整体一致性",
                           score=0.5 if (has_titles and has_body) else 0.2, weight=0.20,
                           explanation="标题 + 正文均已生成" if (has_titles and has_body) else "产出不完整"),
        ]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

STAGE_EVALUATORS: dict[str, BaseStageEvaluator] = {
    "card": CardEvaluator(),
    "brief": BriefEvaluator(),
    "match": MatchEvaluator(),
    "strategy": StrategyEvaluator(),
    "content": ContentEvaluator(),
}


def evaluate_stage(stage: str, opportunity_id: str, context: dict[str, Any]) -> StageEvaluation:
    """便捷入口：按 stage 名称调用对应评估器。"""
    evaluator = STAGE_EVALUATORS.get(stage)
    if evaluator is None:
        logger.warning("Unknown stage %r, returning empty evaluation", stage)
        return StageEvaluation(opportunity_id=opportunity_id, stage=stage)  # type: ignore[arg-type]
    return evaluator.evaluate(opportunity_id, context)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default
