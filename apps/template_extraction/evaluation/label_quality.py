"""标注质量评估。"""

from __future__ import annotations

import logging
from collections import Counter

from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled

logger = logging.getLogger(__name__)


def evaluate_label_coverage(labeled_notes: list[XHSNoteLabeled]) -> dict:
    """评估标注覆盖率。"""
    total = len(labeled_notes)
    if total == 0:
        return {"total": 0}

    has_cover_task = sum(1 for n in labeled_notes if n.cover_task_labels)
    has_visual = sum(1 for n in labeled_notes if n.visual_structure_labels)
    has_semantic = sum(1 for n in labeled_notes if n.business_semantic_labels)
    has_risk = sum(1 for n in labeled_notes if n.risk_labels)

    return {
        "total": total,
        "cover_task_coverage": has_cover_task / total,
        "visual_coverage": has_visual / total,
        "semantic_coverage": has_semantic / total,
        "risk_coverage": has_risk / total,
    }


def evaluate_label_agreement(
    labels_a: list[XHSNoteLabeled],
    labels_b: list[XHSNoteLabeled],
) -> dict:
    """评估两组标注的一致性（按 note_id 对齐，封面任务标签集合是否有交集）。"""
    a_map = {n.note_id: n for n in labels_a}
    b_map = {n.note_id: n for n in labels_b}
    common_ids = set(a_map.keys()) & set(b_map.keys())

    if not common_ids:
        return {"overlap_count": 0, "agreement_rate": 0.0}

    agree = 0
    for nid in common_ids:
        a_labels = {r.label_id for r in a_map[nid].cover_task_labels}
        b_labels = {r.label_id for r in b_map[nid].cover_task_labels}
        if a_labels & b_labels:
            agree += 1

    return {
        "overlap_count": len(common_ids),
        "agreement_rate": agree / len(common_ids),
    }


def evaluate_label_distribution(labeled_notes: list[XHSNoteLabeled]) -> dict:
    """标签分布统计。"""
    cover_dist = Counter()
    semantic_dist = Counter()
    risk_dist = Counter()

    for n in labeled_notes:
        for r in n.cover_task_labels:
            cover_dist[r.label_id] += 1
        for r in n.business_semantic_labels:
            semantic_dist[r.label_id] += 1
        for r in n.risk_labels:
            risk_dist[r.label_id] += 1

    return {
        "cover_task_distribution": dict(cover_dist.most_common()),
        "semantic_distribution": dict(semantic_dist.most_common()),
        "risk_distribution": dict(risk_dist.most_common()),
    }
