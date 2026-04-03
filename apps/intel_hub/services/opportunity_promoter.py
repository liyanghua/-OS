"""机会卡升级判定服务。

根据聚合检视结果判断机会卡是否达到 promoted 阈值。
"""

from __future__ import annotations

from apps.intel_hub.storage.xhs_review_store import XHSReviewStore

PROMOTION_THRESHOLDS = {
    "min_review_count": 1,
    "min_quality_avg": 7.5,
    "min_actionable_ratio": 0.6,
    "min_evidence_ratio": 0.7,
    "min_composite_score": 0.72,
}


def evaluate_opportunity_promotion(
    store: XHSReviewStore,
    opportunity_id: str,
) -> str:
    """评估并更新机会卡状态，返回新状态。"""
    card = store.get_card(opportunity_id)
    if card is None:
        return "pending_review"

    if card.review_count < PROMOTION_THRESHOLDS["min_review_count"]:
        new_status = "pending_review"
    elif (
        (card.manual_quality_score_avg or 0) >= PROMOTION_THRESHOLDS["min_quality_avg"]
        and (card.actionable_ratio or 0) >= PROMOTION_THRESHOLDS["min_actionable_ratio"]
        and (card.evidence_sufficient_ratio or 0) >= PROMOTION_THRESHOLDS["min_evidence_ratio"]
        and (card.composite_review_score or 0) >= PROMOTION_THRESHOLDS["min_composite_score"]
    ):
        new_status = "promoted"
    else:
        new_status = "reviewed"

    qualified = new_status == "promoted"
    store.update_card_review_stats(opportunity_id, {
        "qualified_opportunity": qualified,
        "opportunity_status": new_status,
    })
    return new_status
