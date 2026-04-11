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


def _rubric_version(stage: str) -> str:
    if stage == "strategy":
        return "strategy_v2"
    if stage == "plan":
        return "plan_v1"
    if stage == "asset":
        return "asset_v1"
    return ""


def _parse_llm_json_payload(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end_idx = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        text = "\n".join(lines[1:end_idx])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


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
                if evaluation.evaluator == "llm_judge":
                    evaluation.rubric_version = _rubric_version(self.stage)
                    evaluation.compute_overall()
                    return evaluation
            except Exception:
                logger.warning("LLM evaluation failed for %s/%s, falling back to rules",
                               self.stage, opportunity_id, exc_info=True)

        evaluation.dimensions = self._rule_based_scores(opportunity_id, context)
        evaluation.evaluator = "rule"
        evaluation.rubric_version = _rubric_version(self.stage)
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
        response = llm_router.chat(messages, temperature=0.2, max_tokens=1500)
        if response.degraded or not response.content.strip():
            raise RuntimeError(f"llm_degraded:{response.degraded_reason or 'empty'}")
        result = _parse_llm_json_payload(response.content)
        if not result:
            raise RuntimeError("llm_invalid_json")

        scores_raw: dict[str, float] = result.get("scores", {})
        explanations: dict[str, str] = result.get("explanations", {})
        if not isinstance(scores_raw, dict) or not scores_raw:
            raise RuntimeError("llm_missing_scores")
        if not isinstance(explanations, dict):
            explanations = {}

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

        return StageEvaluation(
            opportunity_id=opportunity_id,
            stage=self.stage,  # type: ignore[arg-type]
            dimensions=dimensions,
            model_used=response.model,
            evaluator="llm_judge",
            rubric_version=_rubric_version(self.stage),
        )


# ---------------------------------------------------------------------------
# IngestEvaluator (V6)
# ---------------------------------------------------------------------------

class IngestEvaluator(BaseStageEvaluator):
    """原始笔记数据完整度评估——决定是否可以生成机会卡。"""

    stage = "ingest"

    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        note = context.get("parsed_note", {})
        if hasattr(note, "model_dump"):
            note = note.model_dump()
        parts = [
            "## 原始笔记信息",
            f"- opportunity_id: {opportunity_id}",
            f"- title: {note.get('title', '')}",
            f"- desc: {str(note.get('desc', note.get('description', '')))[:500]}",
            f"- comments_count: {note.get('comments_count', note.get('comment_count', 0))}",
            f"- liked_count: {note.get('liked_count', 0)}",
            f"- collected_count: {note.get('collected_count', 0)}",
            f"- note_type: {note.get('type', note.get('note_type', 'unknown'))}",
        ]
        return "\n".join(parts)

    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        note = context.get("parsed_note", {})
        if hasattr(note, "model_dump"):
            note = note.model_dump()
        pipeline = context.get("pipeline_details", {})

        core_fields = ["title", "desc", "liked_count", "collected_count", "type"]
        filled = sum(1 for f in core_fields if note.get(f) or note.get(f.replace("desc", "description")))
        field_ratio = filled / max(len(core_fields), 1)

        comment_count = _safe_float(note.get("comments_count", note.get("comment_count", 0)))
        comment_score = min(comment_count / 20, 1.0)

        has_ocr = bool(note.get("image_list") or note.get("ocr_text") or pipeline.get("ocr"))
        has_commerce = bool(
            note.get("goods_tags") or note.get("tag_list")
            or pipeline.get("commerce_mapping")
        )
        benchmark_list = context.get("benchmarks", [])
        bench_score = min(len(benchmark_list) / 3, 1.0) if isinstance(benchmark_list, list) else 0.0

        return [
            DimensionScore(name="field_completeness", name_zh="字段完整度",
                           score=_clamp(field_ratio), weight=0.30,
                           explanation=f"核心字段填充 {filled}/{len(core_fields)}"),
            DimensionScore(name="comment_coverage", name_zh="评论信号覆盖度",
                           score=_clamp(comment_score), weight=0.25,
                           explanation=f"评论数 {int(comment_count)}，>=20 满分"),
            DimensionScore(name="commerce_data", name_zh="商品承接信息",
                           score=0.7 if has_commerce else 0.1, weight=0.20,
                           explanation="检测到商品标签" if has_commerce else "缺少商品映射"),
            DimensionScore(name="benchmark_coverage", name_zh="同类样本覆盖度",
                           score=_clamp(bench_score), weight=0.25,
                           explanation=f"匹配到 {len(benchmark_list) if isinstance(benchmark_list, list) else 0} 个 benchmark"),
        ]


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
            # V6 扩展维度
            DimensionScore(name="audience_clarity", name_zh="人群清晰度",
                           score=0.7 if len(str(card.get("audience", ""))) > 10 else 0.2,
                           weight=0.15,
                           explanation="audience 字段充分" if len(str(card.get("audience", ""))) > 10 else "audience 为空或过短"),
            DimensionScore(name="scene_specificity", name_zh="场景具体性",
                           score=0.7 if len(str(card.get("scene", ""))) > 10 else 0.2,
                           weight=0.15,
                           explanation="scene 字段充分" if len(str(card.get("scene", ""))) > 10 else "scene 为空或过短"),
            DimensionScore(name="hook_strength", name_zh="钩子强度",
                           score=0.7 if len(str(card.get("hook", ""))) > 5 else 0.2,
                           weight=0.15,
                           explanation="hook 字段有效" if len(str(card.get("hook", ""))) > 5 else "hook 为空或过短"),
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
            # V6 扩展维度
            DimensionScore(name="claim_evidence_alignment", name_zh="主张-证据对齐度",
                           score=0.7 if (brief.get("core_claim") and brief.get("proof_points")) else 0.2,
                           weight=0.15,
                           explanation="core_claim + proof_points 齐全" if (brief.get("core_claim") and brief.get("proof_points")) else "缺少 claim 或 proof_points"),
            DimensionScore(name="visual_readiness", name_zh="视觉准备度",
                           score=min(sum([
                               bool(brief.get("visual_direction")),
                               bool(brief.get("cover_direction")),
                               bool(brief.get("image_plan")),
                           ]) / 3, 1.0),
                           weight=0.15,
                           explanation="visual_direction/cover_direction/image_plan 填充情况"),
            DimensionScore(name="production_completeness", name_zh="生产完整度",
                           score=min(sum(1 for k in [
                               "title_directions", "opening_hook", "content_structure",
                               "cta", "tone", "visual_direction", "cover_direction"
                           ] if brief.get(k)) / 7, 1.0),
                           weight=0.15,
                           explanation="V6 production-ready 字段填充率"),
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

        has_positioning = bool(strategy.get("positioning_statement"))
        has_new_angle = bool(strategy.get("new_angle"))
        has_title = bool(strategy.get("title_strategy"))
        has_body = bool(strategy.get("body_strategy"))
        has_image = bool(strategy.get("image_strategy"))
        has_cta = bool(strategy.get("cta_strategy"))
        has_risk = bool(strategy.get("risk_notes"))
        filled = sum([has_positioning, has_new_angle, has_title, has_body, has_image, has_cta])

        return [
            DimensionScore(
                name="strategic_coherence",
                name_zh="策略一致性",
                score=min(sum([has_positioning, has_new_angle, has_cta]) / 3, 1.0),
                weight=0.24,
                explanation="定位、新角度、CTA 越完整，一致性越高",
            ),
            DimensionScore(
                name="differentiation",
                name_zh="差异化程度",
                score=0.8 if has_new_angle else 0.3,
                weight=0.22,
                explanation="new_angle 已填写" if has_new_angle else "new_angle 为空",
            ),
            DimensionScore(
                name="platform_nativeness",
                name_zh="平台原生度",
                score=min(sum([has_title, has_body, has_image]) / 3, 1.0),
                weight=0.18,
                explanation="标题/正文/图片策略越完整，越接近平台原生表达",
            ),
            DimensionScore(
                name="conversion_relevance",
                name_zh="转化相关性",
                score=min(sum([has_cta, has_title, has_body]) / 3, 1.0),
                weight=0.18,
                explanation="CTA 与文案执行策略越完整，转化相关性越高",
            ),
            DimensionScore(
                name="brand_guardrail_fit",
                name_zh="品牌守护栏适配",
                score=0.75 if has_risk else 0.45,
                weight=0.18,
                explanation="risk_notes 已填写" if has_risk else "risk_notes 为空，规则模式保守给分",
            ),
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
# AssetEvaluator
# ---------------------------------------------------------------------------

class AssetEvaluator(BaseStageEvaluator):
    """AssetBundle 质量评估。"""

    stage = "asset"

    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        strategy = context.get("strategy", {})
        if hasattr(strategy, "model_dump"):
            strategy = strategy.model_dump()
        asset_bundle = context.get("asset_bundle", {})
        if hasattr(asset_bundle, "model_dump"):
            asset_bundle = asset_bundle.model_dump()

        parts = [
            "## Strategy 摘要",
            json.dumps(strategy, ensure_ascii=False, default=str)[:1200],
            "",
            "## AssetBundle",
            json.dumps(asset_bundle, ensure_ascii=False, default=str)[:2600],
        ]
        return "\n".join(parts)

    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        asset_bundle = context.get("asset_bundle", {})
        if hasattr(asset_bundle, "model_dump"):
            asset_bundle = asset_bundle.model_dump()

        title_candidates = asset_bundle.get("title_candidates") or []
        body_outline = asset_bundle.get("body_outline") or []
        body_draft = asset_bundle.get("body_draft") or ""
        image_execution_briefs = asset_bundle.get("image_execution_briefs") or []
        export_status = asset_bundle.get("export_status") or "draft"
        approval_status = asset_bundle.get("approval_status") or "pending_review"

        title_score = min(
            sum(
                [
                    bool(title_candidates),
                    any(bool(item.get("axis")) for item in title_candidates if isinstance(item, dict)),
                    any(bool(item.get("rationale")) for item in title_candidates if isinstance(item, dict)),
                ]
            ) / 3,
            1.0,
        )
        body_score = min(
            sum([bool(body_outline), bool(body_draft), len(str(body_draft)) >= 80]) / 3,
            1.0,
        )
        visual_score = min(
            sum(
                [
                    bool(image_execution_briefs),
                    any(bool(item.get("subject")) for item in image_execution_briefs if isinstance(item, dict)),
                    any(bool(item.get("composition")) for item in image_execution_briefs if isinstance(item, dict)),
                ]
            ) / 3,
            1.0,
        )
        brand_score = min(
            sum(
                [
                    approval_status in {"pending_review", "approved"},
                    bool(title_candidates) and bool(body_draft),
                    export_status in {"ready", "exported"},
                ]
            ) / 3,
            1.0,
        )
        readiness_score = min(
            sum(
                [
                    bool(title_candidates),
                    bool(body_draft),
                    bool(image_execution_briefs),
                    export_status in {"ready", "exported"},
                    approval_status != "rejected",
                ]
            ) / 5,
            1.0,
        )

        return [
            DimensionScore(
                name="headline_quality",
                name_zh="标题质量",
                score=title_score,
                weight=0.20,
                explanation="标题候选越完整、角度与 rationale 越明确，标题质量越高",
            ),
            DimensionScore(
                name="body_persuasiveness",
                name_zh="正文说服力",
                score=body_score,
                weight=0.20,
                explanation="正文提纲和正文草稿越完整，越具备说服力",
            ),
            DimensionScore(
                name="visual_instruction_specificity",
                name_zh="视觉指令具体度",
                score=visual_score,
                weight=0.20,
                explanation="图位 brief 越具体，越利于设计/拍摄执行",
            ),
            DimensionScore(
                name="brand_compliance",
                name_zh="品牌合规度",
                score=brand_score,
                weight=0.20,
                explanation="审批状态、导出状态与资产完整性共同反映品牌合规度",
            ),
            DimensionScore(
                name="production_readiness",
                name_zh="生产就绪度",
                score=readiness_score,
                weight=0.20,
                explanation="标题、正文、图位和导出准备越完整，越接近 production-ready",
            ),
        ]


# ---------------------------------------------------------------------------
# PlanEvaluator
# ---------------------------------------------------------------------------

class PlanEvaluator(BaseStageEvaluator):
    """NotePlan 质量评估。"""

    stage = "plan"

    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        brief = context.get("brief", {})
        if hasattr(brief, "model_dump"):
            brief = brief.model_dump()
        strategy = context.get("strategy", {})
        if hasattr(strategy, "model_dump"):
            strategy = strategy.model_dump()
        plan = context.get("plan", {})
        if hasattr(plan, "model_dump"):
            plan = plan.model_dump()

        parts = [
            "## Brief 摘要",
            json.dumps(brief, ensure_ascii=False, default=str)[:1200],
            "",
            "## Strategy 摘要",
            json.dumps(strategy, ensure_ascii=False, default=str)[:1400],
            "",
            "## NotePlan",
            json.dumps(plan, ensure_ascii=False, default=str)[:2200],
        ]
        return "\n".join(parts)

    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        plan = context.get("plan", {})
        if hasattr(plan, "model_dump"):
            plan = plan.model_dump()

        title_plan = plan.get("title_plan") or {}
        body_plan = plan.get("body_plan") or {}
        image_plan = plan.get("image_plan") or {}

        title_axes = title_plan.get("title_axes") or []
        candidate_titles = title_plan.get("candidate_titles") or []
        body_outline = body_plan.get("body_outline") or []
        tone_notes = body_plan.get("tone_notes") or []
        image_slots = image_plan.get("image_slots") or []
        publish_notes = plan.get("publish_notes") or []

        structure_score = min(
            sum(
                [
                    bool(plan.get("note_goal")),
                    bool(plan.get("core_selling_point")),
                    bool(title_axes or candidate_titles),
                    bool(body_outline),
                    bool(image_slots),
                ]
            )
            / 5,
            1.0,
        )
        title_body_score = min(
            sum([bool(candidate_titles), bool(body_plan.get("opening_hook")), bool(body_outline), bool(body_plan.get("cta_direction"))]) / 4,
            1.0,
        )
        image_alignment_score = min(
            sum([bool(image_slots), bool(image_plan.get("global_notes")), bool(image_plan.get("priority_axis"))]) / 3,
            1.0,
        )
        readiness_score = min(
            sum(
                [
                    bool(plan.get("theme")),
                    bool(plan.get("tone_of_voice")),
                    bool(candidate_titles),
                    bool(body_outline),
                    bool(image_slots),
                ]
            )
            / 5,
            1.0,
        )
        handoff_score = min(
            sum([bool(publish_notes), bool(tone_notes), bool(image_plan.get("global_notes"))]) / 3,
            1.0,
        )

        return [
            DimensionScore(
                name="structural_completeness",
                name_zh="结构完整性",
                score=structure_score,
                weight=0.22,
                explanation="标题/正文/图位结构越完整，Plan 越可执行",
            ),
            DimensionScore(
                name="title_body_alignment",
                name_zh="标题正文对齐",
                score=title_body_score,
                weight=0.20,
                explanation="标题组、开篇钩子、正文提纲与 CTA 越一致，分数越高",
            ),
            DimensionScore(
                name="image_slot_alignment",
                name_zh="图位对齐",
                score=image_alignment_score,
                weight=0.20,
                explanation="图位数量、全局视觉说明和优先轴越完整，图位对齐越高",
            ),
            DimensionScore(
                name="execution_readiness",
                name_zh="执行就绪度",
                score=readiness_score,
                weight=0.20,
                explanation="主题、语气和三路执行结构越完整，越适合进入生成",
            ),
            DimensionScore(
                name="human_handoff_readiness",
                name_zh="交接就绪度",
                score=handoff_score,
                weight=0.18,
                explanation="发布备注、语气说明和图片全局说明越完整，越利于人工接手",
            ),
        ]


# ---------------------------------------------------------------------------
# ScorecardEvaluator (V6)
# ---------------------------------------------------------------------------

class ScorecardEvaluator(BaseStageEvaluator):
    """ExpertScorecard 内部一致性评估。"""

    stage = "scorecard"

    def _build_user_prompt(self, opportunity_id: str, context: dict[str, Any]) -> str:
        scorecard = context.get("scorecard", {})
        if hasattr(scorecard, "model_dump"):
            scorecard = scorecard.model_dump()
        parts = [
            "## ExpertScorecard",
            f"- opportunity_id: {opportunity_id}",
            json.dumps(scorecard, ensure_ascii=False, default=str)[:3000],
        ]
        return "\n".join(parts)

    def _rule_based_scores(self, opportunity_id: str, context: dict[str, Any]) -> list[DimensionScore]:
        scorecard = context.get("scorecard", {})
        if hasattr(scorecard, "model_dump"):
            scorecard = scorecard.model_dump()

        dims = scorecard.get("dimensions", [])

        # evidence_backing: 每个维度是否有 evidence
        evidence_count = sum(1 for d in dims if d.get("evidence_sources"))
        evidence_ratio = evidence_count / max(len(dims), 1)

        # score_consistency: 总分不应被单一弱维度误导
        scores = [d.get("score", 0) for d in dims]
        if scores:
            mean_s = sum(scores) / len(scores)
            max_dev = max(abs(s - mean_s) for s in scores)
            consistency = _clamp(1.0 - max_dev)
        else:
            consistency = 0.0

        # recommendation_risk_alignment
        rec = scorecard.get("recommendation", "observe")
        risk = _safe_float(scorecard.get("risk_score", 0))
        if rec == "initiate" and risk > 0.6:
            rec_risk = 0.3
        elif rec == "ignore" and risk < 0.3:
            rec_risk = 0.4
        else:
            rec_risk = 0.8

        # confidence_data_match
        confidence = _safe_float(scorecard.get("confidence", 0))
        data_fill = evidence_ratio
        conf_match = _clamp(1.0 - abs(confidence - data_fill))

        return [
            DimensionScore(name="evidence_backing", name_zh="证据支撑度",
                           score=_clamp(evidence_ratio), weight=0.30,
                           explanation=f"{evidence_count}/{len(dims)} 个维度有证据"),
            DimensionScore(name="score_consistency", name_zh="评分一致性",
                           score=consistency, weight=0.25,
                           explanation="维度分数偏差越小，一致性越高"),
            DimensionScore(name="recommendation_risk_alignment", name_zh="推荐-风险一致性",
                           score=rec_risk, weight=0.25,
                           explanation=f"recommendation={rec}, risk={risk:.2f}"),
            DimensionScore(name="confidence_data_match", name_zh="置信度-数据匹配",
                           score=conf_match, weight=0.20,
                           explanation=f"confidence={confidence:.2f} vs data_fill={data_fill:.2f}"),
        ]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

STAGE_EVALUATORS: dict[str, BaseStageEvaluator] = {
    "ingest": IngestEvaluator(),
    "card": CardEvaluator(),
    "scorecard": ScorecardEvaluator(),
    "brief": BriefEvaluator(),
    "match": MatchEvaluator(),
    "strategy": StrategyEvaluator(),
    "plan": PlanEvaluator(),
    "asset": AssetEvaluator(),
    "content": ContentEvaluator(),
}


def evaluate_stage(stage: str, opportunity_id: str, context: dict[str, Any]) -> StageEvaluation:
    """便捷入口：按 stage 名称调用对应评估器。"""
    evaluator = STAGE_EVALUATORS.get(stage)
    if evaluator is None:
        logger.warning("Unknown stage %r, returning empty evaluation", stage)
        evaluation = StageEvaluation(opportunity_id=opportunity_id, stage=stage)  # type: ignore[arg-type]
    else:
        evaluation = evaluator.evaluate(opportunity_id, context)

    evaluation.dimensions.extend(
        [
            DimensionScore(
                name="brand_fit",
                name_zh="品牌契合度",
                score=1.0,
                weight=1.0,
                explanation="",
            ),
            DimensionScore(
                name="brand_guardrail_fit",
                name_zh="品牌守护栏契合",
                score=1.0,
                weight=1.0,
                explanation="",
            ),
            DimensionScore(
                name="campaign_fit",
                name_zh="战役契合度",
                score=1.0,
                weight=1.0,
                explanation="",
            ),
        ]
    )
    evaluation.compute_overall()
    return evaluation


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
