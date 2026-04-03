"""OpportunityReview schema + XHSReviewStore 测试。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
from apps.intel_hub.schemas.opportunity_review import OpportunityReview
from apps.intel_hub.storage.xhs_review_store import XHSReviewStore


# ── OpportunityReview schema ──

class TestOpportunityReviewSchema:
    def test_valid_review(self) -> None:
        review = OpportunityReview(
            opportunity_id="abc123",
            reviewer="tester",
            manual_quality_score=8,
            is_actionable=True,
            evidence_sufficient=True,
            review_notes="good opportunity",
        )
        assert review.manual_quality_score == 8
        assert review.review_id
        assert review.reviewed_at is not None

    def test_score_too_low(self) -> None:
        with pytest.raises(ValidationError):
            OpportunityReview(
                opportunity_id="abc",
                reviewer="t",
                manual_quality_score=0,
                is_actionable=True,
                evidence_sufficient=True,
            )

    def test_score_too_high(self) -> None:
        with pytest.raises(ValidationError):
            OpportunityReview(
                opportunity_id="abc",
                reviewer="t",
                manual_quality_score=11,
                is_actionable=True,
                evidence_sufficient=True,
            )

    def test_notes_optional(self) -> None:
        review = OpportunityReview(
            opportunity_id="abc",
            reviewer="t",
            manual_quality_score=5,
            is_actionable=False,
            evidence_sufficient=False,
        )
        assert review.review_notes is None


# ── XHSReviewStore ──

def _make_card(oid: str = "card001", otype: str = "visual") -> dict:
    return XHSOpportunityCard(
        opportunity_id=oid,
        title=f"Test Card {oid}",
        summary="Test summary",
        opportunity_type=otype,
        confidence=0.85,
    ).model_dump(mode="json")


@pytest.fixture
def store_and_json(tmp_path: Path):
    db_path = tmp_path / "test.sqlite"
    json_path = tmp_path / "cards.json"
    json_path.write_text(json.dumps([_make_card("c1"), _make_card("c2", "scene")]))
    store = XHSReviewStore(db_path)
    return store, json_path


class TestXHSReviewStore:
    def test_sync_cards(self, store_and_json) -> None:
        store, json_path = store_and_json
        count = store.sync_cards_from_json(json_path)
        assert count == 2
        assert store.card_count() == 2

    def test_get_card(self, store_and_json) -> None:
        store, json_path = store_and_json
        store.sync_cards_from_json(json_path)
        card = store.get_card("c1")
        assert card is not None
        assert card.opportunity_id == "c1"
        assert card.title == "Test Card c1"

    def test_get_card_not_found(self, store_and_json) -> None:
        store, _ = store_and_json
        assert store.get_card("nonexistent") is None

    def test_list_cards_filter_type(self, store_and_json) -> None:
        store, json_path = store_and_json
        store.sync_cards_from_json(json_path)
        result = store.list_cards(opportunity_type="scene")
        assert len(result["items"]) == 1
        assert result["items"][0].opportunity_type == "scene"

    def test_save_and_get_reviews(self, store_and_json) -> None:
        store, json_path = store_and_json
        store.sync_cards_from_json(json_path)
        r1 = OpportunityReview(
            opportunity_id="c1", reviewer="alice",
            manual_quality_score=8, is_actionable=True, evidence_sufficient=True,
        )
        r2 = OpportunityReview(
            opportunity_id="c1", reviewer="bob",
            manual_quality_score=6, is_actionable=False, evidence_sufficient=True,
        )
        store.save_review(r1)
        store.save_review(r2)
        reviews = store.get_reviews("c1")
        assert len(reviews) == 2
        reviewers = {r.reviewer for r in reviews}
        assert reviewers == {"alice", "bob"}

    def test_update_card_review_stats(self, store_and_json) -> None:
        store, json_path = store_and_json
        store.sync_cards_from_json(json_path)
        store.update_card_review_stats("c1", {
            "review_count": 3,
            "manual_quality_score_avg": 7.5,
            "actionable_ratio": 0.667,
            "evidence_sufficient_ratio": 1.0,
            "composite_review_score": 0.775,
            "qualified_opportunity": True,
            "opportunity_status": "promoted",
        })
        card = store.get_card("c1")
        assert card is not None
        assert card.review_count == 3
        assert card.manual_quality_score_avg == 7.5
        assert card.qualified_opportunity is True
        assert card.opportunity_status == "promoted"

    def test_review_count_updates_after_sync(self, store_and_json) -> None:
        store, json_path = store_and_json
        store.sync_cards_from_json(json_path)
        store.update_card_review_stats("c1", {
            "review_count": 2,
            "manual_quality_score_avg": 8.0,
            "opportunity_status": "reviewed",
        })
        store.sync_cards_from_json(json_path)
        card = store.get_card("c1")
        assert card.review_count == 2
        assert card.opportunity_status == "reviewed"

    def test_type_counts(self, store_and_json) -> None:
        store, json_path = store_and_json
        store.sync_cards_from_json(json_path)
        tc = store.type_counts()
        assert tc == {"visual": 1, "scene": 1}

    def test_review_summary(self, store_and_json) -> None:
        store, json_path = store_and_json
        store.sync_cards_from_json(json_path)
        summary = store.get_review_summary()
        assert summary["total_opportunities"] == 2
        assert summary["reviewed_opportunities"] == 0
