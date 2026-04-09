"""评价对比模块：Before/After 对比 + 学习闭环。

支持：
1. 采集 baseline 评价
2. 升级后重跑评价
3. 生成各环节 delta 报告
4. 高分讨论自动提取 Skill
5. 低分环节自动写入教训
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from apps.content_planning.adapters.hermes_adapter import HermesAdapter
from apps.content_planning.evaluation.pipeline_metrics import compute_pipeline_metrics
from apps.content_planning.evaluation.stage_evaluator import evaluate_stage
from apps.content_planning.schemas.evaluation import (
    PipelineEvaluation,
    PipelineMetrics,
    StageEvaluation,
)

logger = logging.getLogger(__name__)


class StageDelta(BaseModel):
    """单环节 Before/After 对比。"""
    stage: str = ""
    before_score: float = 0.0
    after_score: float = 0.0
    delta: float = 0.0
    before_evaluator: str = ""
    after_evaluator: str = ""
    dimension_deltas: list[dict[str, Any]] = Field(default_factory=list)
    improved: bool = False


class ComparisonReport(BaseModel):
    """完整 Before/After 对比报告。"""
    report_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    baseline_id: str = ""
    upgrade_id: str = ""
    stage_deltas: dict[str, StageDelta] = Field(default_factory=dict)
    pipeline_delta: float = 0.0
    baseline_pipeline_score: float = 0.0
    upgrade_pipeline_score: float = 0.0
    summary: str = ""
    skills_extracted: int = 0
    lessons_written: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_baseline_store: dict[str, PipelineEvaluation] = {}


def collect_baseline(opportunity_id: str, context: dict[str, Any]) -> PipelineEvaluation:
    """Collect baseline evaluation scores before any upgrades."""
    stages = ["card", "brief", "match", "strategy", "content"]
    stage_scores: dict[str, StageEvaluation] = {}

    for stage in stages:
        try:
            score = evaluate_stage(stage, opportunity_id, context)
            stage_scores[stage] = score
        except Exception:
            logger.debug("Baseline eval failed for %s/%s", stage, opportunity_id)

    metrics = compute_pipeline_metrics(opportunity_id, context)

    baseline = PipelineEvaluation(
        opportunity_id=opportunity_id,
        stage_scores=stage_scores,
        metrics=metrics,
    )
    baseline.compute_pipeline_score()

    _baseline_store[opportunity_id] = baseline
    logger.info(
        "Baseline collected for %s: pipeline_score=%.3f stages=%d",
        opportunity_id, baseline.pipeline_score, len(stage_scores),
    )
    return baseline


def collect_upgrade_evaluation(opportunity_id: str, context: dict[str, Any]) -> PipelineEvaluation:
    """Collect evaluation scores after upgrade."""
    stages = ["card", "brief", "match", "strategy", "content"]
    stage_scores: dict[str, StageEvaluation] = {}

    for stage in stages:
        try:
            score = evaluate_stage(stage, opportunity_id, context)
            stage_scores[stage] = score
        except Exception:
            logger.debug("Upgrade eval failed for %s/%s", stage, opportunity_id)

    metrics = compute_pipeline_metrics(opportunity_id, context)

    upgrade_eval = PipelineEvaluation(
        opportunity_id=opportunity_id,
        stage_scores=stage_scores,
        metrics=metrics,
    )
    upgrade_eval.compute_pipeline_score()
    return upgrade_eval


def compare(
    opportunity_id: str,
    baseline: PipelineEvaluation | None = None,
    upgrade: PipelineEvaluation | None = None,
    context: dict[str, Any] | None = None,
) -> ComparisonReport:
    """Generate a before/after comparison report."""
    if baseline is None:
        baseline = _baseline_store.get(opportunity_id)
    if baseline is None and context:
        baseline = collect_baseline(opportunity_id, context)
    if baseline is None:
        baseline = PipelineEvaluation(opportunity_id=opportunity_id)

    if upgrade is None and context:
        upgrade = collect_upgrade_evaluation(opportunity_id, context)
    if upgrade is None:
        upgrade = PipelineEvaluation(opportunity_id=opportunity_id)

    report = ComparisonReport(
        opportunity_id=opportunity_id,
        baseline_id=baseline.evaluation_id,
        upgrade_id=upgrade.evaluation_id,
        baseline_pipeline_score=baseline.pipeline_score,
        upgrade_pipeline_score=upgrade.pipeline_score,
        pipeline_delta=upgrade.pipeline_score - baseline.pipeline_score,
    )

    all_stages = set(list(baseline.stage_scores.keys()) + list(upgrade.stage_scores.keys()))

    for stage in all_stages:
        before_eval = baseline.stage_scores.get(stage)
        after_eval = upgrade.stage_scores.get(stage)

        before_score = before_eval.overall_score if before_eval else 0.0
        after_score = after_eval.overall_score if after_eval else 0.0

        dim_deltas = _compute_dimension_deltas(before_eval, after_eval)

        report.stage_deltas[stage] = StageDelta(
            stage=stage,
            before_score=before_score,
            after_score=after_score,
            delta=after_score - before_score,
            before_evaluator=before_eval.evaluator if before_eval else "",
            after_evaluator=after_eval.evaluator if after_eval else "",
            dimension_deltas=dim_deltas,
            improved=after_score > before_score,
        )

    improved = [s for s, d in report.stage_deltas.items() if d.improved]
    regressed = [s for s, d in report.stage_deltas.items() if d.delta < -0.05]

    summary_parts = []
    if report.pipeline_delta > 0:
        summary_parts.append(f"管线总分提升 {report.pipeline_delta:+.3f}")
    elif report.pipeline_delta < 0:
        summary_parts.append(f"管线总分下降 {report.pipeline_delta:+.3f}")
    else:
        summary_parts.append("管线总分无变化")

    if improved:
        summary_parts.append(f"提升环节: {', '.join(improved)}")
    if regressed:
        summary_parts.append(f"下降环节: {', '.join(regressed)}")

    report.summary = "；".join(summary_parts)
    return report


def apply_learning_loop(report: ComparisonReport, discussion_rounds: list[dict] | None = None) -> ComparisonReport:
    """Apply the learning loop: extract skills from high-score discussions, write lessons from low scores."""
    hermes = HermesAdapter()
    skills_extracted = 0
    lessons_written = 0

    if discussion_rounds:
        for dr in discussion_rounds:
            skill = hermes.extract_skill_from_experience(dr)
            if skill:
                skills_extracted += 1
                logger.info("Extracted skill: %s from round %s", skill.skill_name, dr.get("round_id", "?"))

    for stage, delta in report.stage_deltas.items():
        if delta.after_score < 0.4:
            lesson = f"环节 {stage} 评分较低 ({delta.after_score:.2f})，需优化。"
            if delta.dimension_deltas:
                worst = min(delta.dimension_deltas, key=lambda d: d.get("after", 1.0))
                lesson += f" 最弱维度: {worst.get('name_zh', worst.get('name', '?'))}"
            hermes.write_lesson(report.opportunity_id, stage, lesson, delta.after_score)
            lessons_written += 1

    report.skills_extracted = skills_extracted
    report.lessons_written = lessons_written
    return report


def _compute_dimension_deltas(
    before: StageEvaluation | None,
    after: StageEvaluation | None,
) -> list[dict[str, Any]]:
    """Compute per-dimension deltas between two evaluations."""
    if before is None and after is None:
        return []

    before_dims = {d.name: d for d in (before.dimensions if before else [])}
    after_dims = {d.name: d for d in (after.dimensions if after else [])}

    all_names = set(list(before_dims.keys()) + list(after_dims.keys()))
    deltas = []
    for name in sorted(all_names):
        bd = before_dims.get(name)
        ad = after_dims.get(name)
        deltas.append({
            "name": name,
            "name_zh": (ad or bd).name_zh if (ad or bd) else name,
            "before": bd.score if bd else 0.0,
            "after": ad.score if ad else 0.0,
            "delta": (ad.score if ad else 0.0) - (bd.score if bd else 0.0),
        })
    return deltas
