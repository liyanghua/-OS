"""端到端评价体系。"""
from apps.content_planning.evaluation.stage_evaluator import (
    evaluate_stage,
    STAGE_EVALUATORS,
)
from apps.content_planning.evaluation.pipeline_metrics import compute_pipeline_metrics
from apps.content_planning.evaluation.comparison import (
    collect_baseline,
    compare,
    apply_learning_loop,
    ComparisonReport,
    StageDelta,
)

__all__ = [
    "evaluate_stage",
    "STAGE_EVALUATORS",
    "compute_pipeline_metrics",
    "collect_baseline",
    "compare",
    "apply_learning_loop",
    "ComparisonReport",
    "StageDelta",
]
