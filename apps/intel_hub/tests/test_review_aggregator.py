"""review_aggregator 聚合服务测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
from apps.intel_hub.schemas.opportunity_review import OpportunityReview
from apps.intel_hub.services.review_aggregator import (
    aggregate_all_opportunities_review_stats,
    aggregate_reviews_for_opportunity,
)
from apps.intel_hub.storage.xhs_review_store import XHSReviewStore


def _setup_store(tmp_path: Path, cards_data: list[dict] | None = None) -> XHSReviewStore:
    db_path = tmp_path / "agg_test.sqlite"
    json_path = tmp_path / "cards.json"
    if cards_data is None:
        cards_data = [
            XHSOpportunityCard(
                opportunity_id="opp1", title="T1", opportunity_type="visual", confidence=0.8,
            ).model_dump(mode="json"),
        ]
    json_path.write_text(json.dumps(cards_data))
    store = XHSReviewStore(db_path)
    store.sync_cards_from_json(json_path)
    return store


class TestAggregateReviews:
    def test_no_reviews(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        stats = aggregate_reviews_for_opportunity(store, "opp1")
        assert stats["review_count"] == 0
        assert stats["manual_quality_score_avg"] is None
        assert stats["composite_review_score"] is None

    def test_single_review(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        store.save_review(OpportunityReview(
            opportunity_id="opp1", reviewer="alice",
            manual_quality_score=8, is_actionable=True, evidence_sufficient=True,
        ))
        stats = aggregate_reviews_for_opportunity(store, "opp1")
        assert stats["review_count"] == 1
        assert stats["manual_quality_score_avg"] == 8.0
        assert stats["actionable_ratio"] == 1.0
        assert stats["evidence_sufficient_ratio"] == 1.0
        expected_composite = 0.5 * 0.8 + 0.3 * 1.0 + 0.2 * 1.0
        assert abs(stats["composite_review_score"] - expected_composite) < 0.01

    def test_multiple_reviews(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        store.save_review(OpportunityReview(
            opportunity_id="opp1", reviewer="alice",
            manual_quality_score=8, is_actionable=True, evidence_sufficient=True,
        ))
        store.save_review(OpportunityReview(
            opportunity_id="opp1", reviewer="bob",
            manual_quality_score=6, is_actionable=False, evidence_sufficient=True,
        ))
        stats = aggregate_reviews_for_opportunity(store, "opp1")
        assert stats["review_count"] == 2
        assert stats["manual_quality_score_avg"] == 7.0
        assert stats["actionable_ratio"] == 0.5
        assert stats["evidence_sufficient_ratio"] == 1.0
        expected_composite = 0.5 * 0.7 + 0.3 * 0.5 + 0.2 * 1.0
        assert abs(stats["composite_review_score"] - expected_composite) < 0.01

    def test_stats_persisted_to_store(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        store.save_review(OpportunityReview(
            opportunity_id="opp1", reviewer="alice",
            manual_quality_score=9, is_actionable=True, evidence_sufficient=True,
        ))
        aggregate_reviews_for_opportunity(store, "opp1")
        card = store.get_card("opp1")
        assert card.review_count == 1
        assert card.manual_quality_score_avg == 9.0


class TestGlobalStats:
    def test_empty_store(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path)
        summary = aggregate_all_opportunities_review_stats(store)
        assert summary["total_opportunities"] == 1
        assert summary["reviewed_opportunities"] == 0
        assert summary["needs_optimization"] is True

    def test_with_reviewed_cards(self, tmp_path: Path) -> None:
        store = _setup_store(tmp_path, [
            XHSOpportunityCard(
                opportunity_id="o1", title="T1", opportunity_type="visual", confidence=0.8,
            ).model_dump(mode="json"),
            XHSOpportunityCard(
                opportunity_id="o2", title="T2", opportunity_type="scene", confidence=0.7,
            ).model_dump(mode="json"),
        ])
        store.save_review(OpportunityReview(
            opportunity_id="o1", reviewer="a",
            manual_quality_score=9, is_actionable=True, evidence_sufficient=True,
        ))
        aggregate_reviews_for_opportunity(store, "o1")
        summary = aggregate_all_opportunities_review_stats(store)
        assert summary["reviewed_opportunities"] == 1
        assert summary["average_manual_quality_score"] == 9.0
