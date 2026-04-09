"""管线级聚合指标计算。"""
from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.schemas.evaluation import PipelineMetrics

logger = logging.getLogger(__name__)


def compute_pipeline_metrics(opportunity_id: str, session_data: dict[str, Any]) -> PipelineMetrics:
    """Compute pipeline-level metrics from session state."""
    metrics = PipelineMetrics(opportunity_id=opportunity_id)

    stages_expected = [
        "brief", "match_result", "strategy", "note_plan",
        "titles", "body", "image_briefs", "asset_bundle",
    ]
    stages_present = sum(1 for s in stages_expected if session_data.get(s))
    metrics.pipeline_completion_rate = stages_present / len(stages_expected) if stages_expected else 0.0

    for stage_key in ("brief_versions", "strategy_versions", "plan_versions"):
        versions = session_data.get(stage_key, [])
        if isinstance(versions, list):
            stage_name = stage_key.replace("_versions", "")
            metrics.version_count[stage_name] = len(versions)

    for obj_key in ("brief", "strategy", "note_plan"):
        obj = session_data.get(obj_key)
        if isinstance(obj, dict):
            locks = obj.get("locks")
            if isinstance(locks, dict):
                locked_fields = locks.get("locked_fields", {})
                metrics.locked_field_count += sum(1 for v in locked_fields.values() if v)

    total_fields = 20
    edited_estimate = sum(max(0, c - 1) for c in metrics.version_count.values())
    metrics.human_edit_ratio = min(edited_estimate / total_fields, 1.0)

    return metrics
