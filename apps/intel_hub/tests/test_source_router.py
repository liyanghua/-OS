import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRENDRADAR_FIXTURE = ROOT / "data" / "fixtures" / "trendradar_output" / "output"
MC_FIXTURE = ROOT / "data" / "fixtures" / "mediacrawler_output" / "xhs" / "jsonl"


class SourceRouterTests(unittest.TestCase):
    def _make_settings(self, **overrides):
        from apps.intel_hub.config_loader import RuntimeSettings

        defaults = {
            "trendradar_output_dir": str(TRENDRADAR_FIXTURE),
            "storage_path": "data/intel_hub.sqlite",
            "default_page_size": 20,
            "fixture_fallback_dir": str(TRENDRADAR_FIXTURE),
            "mediacrawler_sources": [],
            "xhs_sources": [],
            "xhs_aggregation": {},
        }
        defaults.update(overrides)
        return RuntimeSettings.model_validate(defaults)

    def test_trendradar_only(self) -> None:
        from apps.intel_hub.ingest.source_router import collect_raw_signals

        settings = self._make_settings()
        records = collect_raw_signals(settings)
        self.assertGreater(len(records), 0)
        trendradar_types = {"json", "jsonl", "db_news_items", "db_rss_items", "db_generic"}
        self.assertTrue(
            any(r.get("raw_source_type") in trendradar_types for r in records),
            "should contain trendradar records",
        )

    def test_mediacrawler_only(self) -> None:
        from apps.intel_hub.ingest.source_router import collect_raw_signals

        settings = self._make_settings(
            trendradar_output_dir="/nonexistent",
            fixture_fallback_dir="",
            mediacrawler_sources=[
                {
                    "enabled": True,
                    "platform": "xiaohongshu",
                    "output_path": str(MC_FIXTURE),
                },
            ],
        )
        records = collect_raw_signals(settings)
        self.assertGreater(len(records), 0)
        for r in records:
            self.assertEqual(r["platform"], "xiaohongshu")
            self.assertTrue(r["raw_source_type"].startswith("mediacrawler_"))

    def test_dual_source_merge(self) -> None:
        from apps.intel_hub.ingest.source_router import collect_raw_signals

        settings = self._make_settings(
            mediacrawler_sources=[
                {
                    "enabled": True,
                    "platform": "xiaohongshu",
                    "output_path": str(MC_FIXTURE),
                },
            ],
        )
        records = collect_raw_signals(settings)
        platforms = {r.get("platform") for r in records}
        sources = {r.get("raw_source_type") for r in records}
        self.assertIn("xiaohongshu", platforms)
        self.assertTrue(any(s.startswith("mediacrawler_") for s in sources))

    def test_disabled_source_skipped(self) -> None:
        from apps.intel_hub.ingest.source_router import collect_raw_signals

        settings = self._make_settings(
            trendradar_output_dir="/nonexistent",
            fixture_fallback_dir="",
            mediacrawler_sources=[
                {
                    "enabled": False,
                    "platform": "xiaohongshu",
                    "output_path": str(MC_FIXTURE),
                },
            ],
        )
        records = collect_raw_signals(settings)
        self.assertEqual(len(records), 0)

    def test_fixture_fallback(self) -> None:
        from apps.intel_hub.ingest.source_router import collect_raw_signals

        settings = self._make_settings(
            trendradar_output_dir="/nonexistent",
            fixture_fallback_dir="",
            mediacrawler_sources=[
                {
                    "enabled": True,
                    "platform": "xiaohongshu",
                    "output_path": "/nonexistent/mc",
                    "fixture_fallback": str(MC_FIXTURE),
                },
            ],
        )
        records = collect_raw_signals(settings)
        self.assertGreater(len(records), 0)

    def test_empty_config_returns_empty(self) -> None:
        from apps.intel_hub.ingest.source_router import collect_raw_signals

        settings = self._make_settings(
            trendradar_output_dir="/nonexistent",
            fixture_fallback_dir="",
        )
        records = collect_raw_signals(settings)
        self.assertEqual(len(records), 0)


if __name__ == "__main__":
    unittest.main()
