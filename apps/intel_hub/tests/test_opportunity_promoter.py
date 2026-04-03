"""opportunity_promoter 升级判定服务测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
from apps.intel_hub.schemas.opportunity_review import OpportunityReview
from apps.intel_hub.services.opportunity_promoter import evaluate_opportunity_promotion
from apps.intel_hub.services.review_aggregator import aggregate_reviews_for_opportunity
from apps.intel_hub.storage.xhs_review_store import XHSReviewStore


def _setup_store(tmp_path: Path) -> XHSReviewStore:
    db_path = tmp_path / "promo_test.sqlite"
    json_path = tmp_path / "cards.json"
    json_path.write_text(json.dumps([
        XHSOpportunityCard(
            opportunity_id="p1", title="Promo Test", opportunity_type="visual", confidence=0.8,
        ).model_dump(mode="json"),
    ]))
    store = XHSReviewStore(db_path)
    store.sync_cards_from_json(json_path)
    return store


class TestOpportunityPromoter:
    def test_no_reviews_pending(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        status = evaluate_opportunity_promotion(store, "p1")
        assert status == "pending_review"

    def test_meets_all_thresholds_promoted(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        store.save_review(OpportunityReview(
            opportunity_id="p1", reviewer="alice",
            manual_quality_score=9, is_actionable=True, evidence_sufficient=True,
        ))
        aggregate_reviews_for_opportunity(store, "p1")
        status = evaluate_opportunity_promotion(store, "p1")
        assert status == "promoted"
        card = store.get_card("p1")
        assert card.qualified_opportunity is True
        assert card.opportunity_status == "promoted"

    def test_low_quality_reviewed(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        store.save_review(OpportunityReview(
            opportunity_id="p1", reviewer="alice",
            manual_quality_score=5, is_actionable=True, evidence_sufficient=True,
        ))
        aggregate_reviews_for_opportunity(store, "p1")
        status = evaluate_opportunity_promotion(store, "p1")
        assert status == "reviewed"
        card = store.get_card("p1")
        assert card.qualified_opportunity is False

    def test_not_actionable_reviewed(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        store.save_review(OpportunityReview(
            opportunity_id="p1", reviewer="alice",
            manual_quality_score=9, is_actionable=False, evidence_sufficient=True,
        ))
        aggregate_reviews_for_opportunity(store, "p1")
        status = evaluate_opportunity_promotion(store, "p1")
        assert status == "reviewed"

    def test_insufficient_evidence_reviewed(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        store.save_review(OpportunityReview(
            opportunity_id="p1", reviewer="alice",
            manual_quality_score=9, is_actionable=True, evidence_sufficient=False,
        ))
        aggregate_reviews_for_opportunity(store, "p1")
        status = evaluate_opportunity_promotion(store, "p1")
        assert status == "reviewed"

    def test_nonexistent_card_pending(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        status = evaluate_opportunity_promotion(store, "nonexistent")
        assert status == "pending_review"

    def test_mixed_reviews_not_promoted(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        store.save_review(OpportunityReview(
            opportunity_id="p1", reviewer="alice",
            manual_quality_score=9, is_actionable=True, evidence_sufficient=True,
        ))
        store.save_review(OpportunityReview(
            opportunity_id="p1", reviewer="bob",
            manual_quality_score=4, is_actionable=False, evidence_sufficient=False,
        ))
        aggregate_reviews_for_opportunity(store, "p1")
        status = evaluate_opportunity_promotion(store, "p1")
        assert status == "reviewed"
