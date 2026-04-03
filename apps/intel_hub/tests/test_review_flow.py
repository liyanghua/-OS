import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_OUTPUT = ROOT / "data" / "fixtures" / "trendradar_output" / "output"


class ReviewWritebackTests(unittest.TestCase):
    def test_repository_updates_review_fields_and_filters(self) -> None:
        from apps.intel_hub.schemas.review import ReviewUpdateRequest
        from apps.intel_hub.storage.repository import Repository
        from apps.intel_hub.workflow.refresh_pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        f"trendradar_output_dir: {FIXTURE_OUTPUT.as_posix()}",
                        f"storage_path: {storage_path.as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                    ]
                ),
                encoding="utf-8",
            )

            run_pipeline(runtime_path)
            repository = Repository(storage_path)
            card_id = repository.list_models("opportunity_cards")["items"][0]["id"]

            updated_card = repository.update_card_review(
                "opportunity_cards",
                card_id,
                ReviewUpdateRequest(
                    review_status="accepted",
                    review_notes="Confirmed by analyst",
                    reviewer="analyst_a",
                    feedback_tags=["high_confidence"],
                ),
            )

            self.assertEqual(updated_card.review_status, "accepted")
            self.assertEqual(updated_card.reviewer, "analyst_a")
            self.assertEqual(updated_card.review_notes, "Confirmed by analyst")
            self.assertIsNotNone(updated_card.reviewed_at)

            filtered = repository.list_models(
                "opportunity_cards",
                review_status="accepted",
                reviewer="analyst_a",
            )
            self.assertEqual(filtered["total"], 1)

    def test_review_schema_rejects_invalid_status(self) -> None:
        from pydantic import ValidationError

        from apps.intel_hub.schemas.review import ReviewUpdateRequest

        with self.assertRaises(ValidationError):
            ReviewUpdateRequest(
                review_status="invalid_status",
                review_notes="nope",
                reviewer="analyst_a",
            )


if __name__ == "__main__":
    unittest.main()
