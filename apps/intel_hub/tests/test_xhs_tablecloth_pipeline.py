import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MC_FIXTURE = ROOT / "data" / "fixtures" / "mediacrawler_output" / "xhs" / "jsonl"


class XhsTableclothPipelineTests(unittest.TestCase):
    """End-to-end: MediaCrawler fixture -> pipeline -> signals/opportunities."""

    def test_xhs_tablecloth_signals_and_opportunities(self) -> None:
        from apps.intel_hub.config_loader import clear_config_caches
        from apps.intel_hub.workflow.refresh_pipeline import run_pipeline
        from apps.intel_hub.storage.repository import Repository

        clear_config_caches()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        "trendradar_output_dir: /nonexistent",
                        f"storage_path: {storage_path.as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                        "include_rss: false",
                        "mediacrawler_sources:",
                        "  - enabled: true",
                        "    platform: xiaohongshu",
                        f"    output_path: {MC_FIXTURE.as_posix()}",
                    ]
                ),
                encoding="utf-8",
            )

            result = run_pipeline(runtime_path)

            self.assertGreaterEqual(result.raw_count, 5, "should have at least 5 raw records from fixture")
            self.assertGreaterEqual(result.signal_count, 1, "should produce signals")
            self.assertGreaterEqual(result.opportunity_count, 1, "should produce at least 1 opportunity card")

            repository = Repository(storage_path)

            signals = repository.list_models("signals", entity="category_tablecloth")
            self.assertGreaterEqual(signals["total"], 1, "should have category_tablecloth signals")

            for sig in signals["items"]:
                self.assertIn("category_tablecloth", sig["entity_refs"])
                self.assertIn("xiaohongshu", sig["platform_refs"])

            all_signals = repository.list_models("signals", platform="xiaohongshu")
            self.assertGreaterEqual(all_signals["total"], 1)

            all_topic_tags = set()
            for sig in all_signals["items"]:
                all_topic_tags.update(sig.get("topic_tags", []))

            expected_tags = {"风格偏好", "材质偏好", "清洁痛点", "场景改造", "内容钩子",
                             "拍照出片", "价格敏感", "尺寸适配"}
            self.assertTrue(
                expected_tags & all_topic_tags,
                f"should have at least one tablecloth tag; got {all_topic_tags}",
            )

            xhs_tags = {"用户真实体验", "购买意向", "负面反馈", "推荐种草"}
            self.assertTrue(
                xhs_tags & all_topic_tags,
                f"should have at least one xhs review tag; got {all_topic_tags}",
            )

            opportunities = repository.list_models("opportunity_cards", entity="category_tablecloth")
            self.assertGreaterEqual(opportunities["total"], 1)
            for opp in opportunities["items"]:
                self.assertTrue(opp["evidence_refs"], "opportunity must have evidence_refs")

    def test_evidence_refs_not_empty(self) -> None:
        from apps.intel_hub.config_loader import clear_config_caches
        from apps.intel_hub.workflow.refresh_pipeline import run_pipeline
        from apps.intel_hub.storage.repository import Repository

        clear_config_caches()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        "trendradar_output_dir: /nonexistent",
                        f"storage_path: {storage_path.as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                        "include_rss: false",
                        "mediacrawler_sources:",
                        "  - enabled: true",
                        "    platform: xiaohongshu",
                        f"    output_path: {MC_FIXTURE.as_posix()}",
                    ]
                ),
                encoding="utf-8",
            )

            run_pipeline(runtime_path)
            repository = Repository(storage_path)

            evidence = repository.list_models("evidence_refs")
            self.assertGreater(evidence["total"], 0, "should have evidence_refs")
            for ev in evidence["items"]:
                self.assertTrue(ev.get("title"), "evidence must have title")
                self.assertTrue(ev.get("raw_text"), "evidence must have raw_text")


if __name__ == "__main__":
    unittest.main()
