"""将标注结果转为各层标签的 multi-hot 向量。"""

from __future__ import annotations

from enum import Enum

from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled
from apps.template_extraction.schemas.labels import (
    BusinessSemanticLabel,
    CoverTaskLabel,
    RiskLabel,
    VisualStructureLabel,
)


def _enum_order(enum_cls: type[Enum]) -> list[Enum]:
    return list(enum_cls)


def _multi_hot_for_results(
    results: list,
    enum_cls: type[Enum],
) -> list[float]:
    members = _enum_order(enum_cls)
    n = len(members)
    vec = [0.0] * n
    value_to_idx = {m.value: i for i, m in enumerate(members)}
    for r in results:
        lid = getattr(r, "label_id", None)
        if not lid or lid not in value_to_idx:
            continue
        vec[value_to_idx[lid]] = 1.0
    return vec


def vectorize_labels(labeled: XHSNoteLabeled) -> dict[str, list[float]]:
    """四层标签 multi-hot；下标顺序与各 Enum 定义顺序一致。"""
    return {
        "task_label_vector": _multi_hot_for_results(
            labeled.cover_task_labels,
            CoverTaskLabel,
        ),
        "visual_label_vector": _multi_hot_for_results(
            labeled.visual_structure_labels,
            VisualStructureLabel,
        ),
        "semantic_label_vector": _multi_hot_for_results(
            labeled.business_semantic_labels,
            BusinessSemanticLabel,
        ),
        "risk_label_vector": _multi_hot_for_results(
            labeled.risk_labels,
            RiskLabel,
        ),
    }
