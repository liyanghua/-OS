"""机会卡检视反馈聚合服务。

将多条人工 review 聚合为单卡评分指标，并计算全局统计。
"""

from __future__ import annotations

from typing import Any

from apps.intel_hub.storage.xhs_review_store import XHSReviewStore


def aggregate_reviews_for_opportunity(
    store: XHSReviewStore,
    opportunity_id: str,
) -> dict[str, Any]:
    """计算单卡聚合指标并回写到 store，返回聚合结果。"""
    reviews = store.get_reviews(opportunity_id)
    if not reviews:
        stats = {
            "review_count": 0,
            "manual_quality_score_avg": None,
            "actionable_ratio": None,
            "evidence_sufficient_ratio": None,
            "composite_review_score": None,
        }
        store.update_card_review_stats(opportunity_id, stats)
        return stats

    n = len(reviews)
    total_quality = sum(r.manual_quality_score for r in reviews)
    total_actionable = sum(1 for r in reviews if r.is_actionable)
    total_evidence = sum(1 for r in reviews if r.evidence_sufficient)

    avg_quality = total_quality / n
    actionable_ratio = total_actionable / n
    evidence_ratio = total_evidence / n

    normalized_quality = avg_quality / 10.0
    composite = (
        0.5 * normalized_quality
        + 0.3 * actionable_ratio
        + 0.2 * evidence_ratio
    )

    stats = {
        "review_count": n,
        "manual_quality_score_avg": round(avg_quality, 2),
        "actionable_ratio": round(actionable_ratio, 3),
        "evidence_sufficient_ratio": round(evidence_ratio, 3),
        "composite_review_score": round(composite, 3),
    }
    store.update_card_review_stats(opportunity_id, stats)
    return stats


def aggregate_all_opportunities_review_stats(
    store: XHSReviewStore,
) -> dict[str, Any]:
    """全局检视统计摘要。"""
    return store.get_review_summary()
