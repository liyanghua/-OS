"""机会卡升级判定服务。

根据聚合检视结果判断机会卡是否达到 promoted 阈值。
"""

from __future__ import annotations

import os

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


def auto_promote_for_dev(
    store: XHSReviewStore,
    opportunity_id: str,
) -> str:
    """开发环境一键将机会卡标为 promoted（仅 ENVIRONMENT=dev 时生效）。"""
    card = store.get_card(opportunity_id)
    if card is None:
        return "not_found"
    if os.environ.get("ENVIRONMENT", "dev") != "dev":
        return card.opportunity_status
    store.update_card_review_stats(opportunity_id, {
        "qualified_opportunity": True,
        "opportunity_status": "promoted",
        "manual_quality_score_avg": 8.0,
        "composite_review_score": 0.85,
        "review_count": 1,
    })
    return "promoted"


def batch_auto_promote(store: XHSReviewStore) -> dict[str, str]:
    """对 store 中全部机会卡依次调用 auto_promote_for_dev，返回 id -> 状态。"""
    out: dict[str, str] = {}
    for card in store.list_cards(page_size=10_000)["items"]:
        out[card.opportunity_id] = auto_promote_for_dev(store, card.opportunity_id)
    return out
