import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_OUTPUT = ROOT / "data" / "fixtures" / "trendradar_tablecloth" / "output"


class TableclothPipelineTests(unittest.TestCase):
    def test_tablecloth_signals_map_to_category_and_compile_opportunity(self) -> None:
        from apps.intel_hub.workflow.refresh_pipeline import run_pipeline
        from apps.intel_hub.storage.repository import Repository

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
            self.assertGreaterEqual(result.opportunity_count, 1)

            repository = Repository(storage_path)
            signals = repository.list_models("signals", entity="category_tablecloth")
            self.assertGreaterEqual(signals["total"], 1)

            tablecloth_signal = signals["items"][0]
            self.assertIn("category_tablecloth", tablecloth_signal["entity_refs"])
            self.assertTrue(tablecloth_signal["source_name"])
            self.assertTrue(tablecloth_signal["platform_refs"])

            topic_tags = set(tablecloth_signal["topic_tags"])
            self.assertTrue({"风格偏好", "材质偏好", "清洁痛点", "场景改造", "内容钩子"} & topic_tags)

            opportunities = repository.list_models("opportunity_cards", entity="category_tablecloth")
            self.assertGreaterEqual(opportunities["total"], 1)
            self.assertTrue(opportunities["items"][0]["evidence_refs"])


if __name__ == "__main__":
    unittest.main()
