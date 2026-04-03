import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_OUTPUT = ROOT / "data" / "fixtures" / "trendradar_output" / "output"


class PipelineWorkflowTests(unittest.TestCase):
    def test_pipeline_generates_signals_and_cards_from_trendradar_output(self) -> None:
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

            result = run_pipeline(runtime_path)

            self.assertEqual(result.raw_count, 3)
            self.assertEqual(result.signal_count, 3)
            self.assertGreaterEqual(result.opportunity_count, 1)
            self.assertGreaterEqual(result.risk_count, 1)
            self.assertTrue(storage_path.exists())

            from apps.intel_hub.storage.repository import Repository

            repository = Repository(storage_path)
            opportunity = repository.list_models("opportunity_cards")["items"][0]
            self.assertEqual(opportunity["review_status"], "pending")
            self.assertIn("dedupe_key", opportunity)
            self.assertIn("merged_signal_ids", opportunity)
            self.assertIn("merged_evidence_refs", opportunity)


if __name__ == "__main__":
    unittest.main()
