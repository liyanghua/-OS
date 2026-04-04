"""模板抽取链路：标注 / 聚类 / 模板质量评估与验收报告。"""

from __future__ import annotations

from apps.template_extraction.evaluation.acceptance_report import generate_acceptance_report
from apps.template_extraction.evaluation.cluster_quality import (
    evaluate_cluster_balance,
    evaluate_cluster_purity,
    evaluate_engagement_coverage,
)
from apps.template_extraction.evaluation.label_quality import (
    evaluate_label_agreement,
    evaluate_label_coverage,
    evaluate_label_distribution,
)
from apps.template_extraction.evaluation.template_quality import (
    evaluate_template_boundaries,
    evaluate_template_completeness,
    evaluate_template_executability,
)

__all__ = [
    "generate_acceptance_report",
    "evaluate_cluster_balance",
    "evaluate_cluster_purity",
    "evaluate_engagement_coverage",
    "evaluate_label_agreement",
    "evaluate_label_coverage",
    "evaluate_label_distribution",
    "evaluate_template_boundaries",
    "evaluate_template_completeness",
    "evaluate_template_executability",
]
