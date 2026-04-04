"""两阶段聚类：封面原型 → 图组策略。"""

from apps.template_extraction.clustering.cluster_pipeline import run_cluster_pipeline
from apps.template_extraction.clustering.cluster_report import generate_cluster_report
from apps.template_extraction.clustering.cover_clustering import (
    build_cover_feature_matrix,
    get_cluster_summary,
    run_cover_clustering,
)
from apps.template_extraction.clustering.strategy_clustering import (
    TARGET_TEMPLATES,
    build_strategy_feature_matrix,
    get_strategy_cluster_summary,
    map_clusters_to_templates,
    run_strategy_clustering,
)

__all__ = [
    "TARGET_TEMPLATES",
    "build_cover_feature_matrix",
    "build_strategy_feature_matrix",
    "generate_cluster_report",
    "get_cluster_summary",
    "get_strategy_cluster_summary",
    "map_clusters_to_templates",
    "run_cluster_pipeline",
    "run_cover_clustering",
    "run_strategy_clustering",
]
