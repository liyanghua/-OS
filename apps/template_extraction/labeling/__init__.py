"""模板提取：四层标签加载、规则/VLM 标注与流水线。"""

from __future__ import annotations

from apps.template_extraction.labeling.label_taxonomy import (
    ALL_COVER_TASK_LABELS,
    ALL_GALLERY_TASK_LABELS,
    ALL_RISK_LABELS,
    ALL_SEMANTIC_LABELS,
    ALL_VISUAL_LABELS,
    get_trigger_keywords,
    load_taxonomy,
)
from apps.template_extraction.labeling.labeler_pipeline import run_labeling_pipeline
from apps.template_extraction.labeling.rule_labeler import label_note_by_rules
from apps.template_extraction.labeling.vlm_labeler import label_note_by_vlm

__all__ = [
    "ALL_COVER_TASK_LABELS",
    "ALL_GALLERY_TASK_LABELS",
    "ALL_RISK_LABELS",
    "ALL_SEMANTIC_LABELS",
    "ALL_VISUAL_LABELS",
    "get_trigger_keywords",
    "label_note_by_rules",
    "label_note_by_vlm",
    "load_taxonomy",
    "run_labeling_pipeline",
]
