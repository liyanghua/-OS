import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_OUTPUT = ROOT / "data" / "fixtures" / "trendradar_output" / "output"


def _write_runtime(tmp: Path, *, output_dir: Path = FIXTURE_OUTPUT) -> Path:
    runtime_path = tmp / "runtime.yaml"
    runtime_path.write_text(
        "\n".join(
            [
                f"trendradar_output_dir: {output_dir.as_posix()}",
                f"storage_path: {(tmp / 'intel_hub.sqlite').as_posix()}",
                "default_page_size: 20",
                "fixture_fallback_dir: ''",
            ]
        ),
        encoding="utf-8",
    )
    return runtime_path


class ServerDeployRuntimeTests(unittest.TestCase):
    def tearDown(self) -> None:
        from apps.intel_hub.config_loader import clear_config_caches

        clear_config_caches()

    def test_load_runtime_settings_uses_env_var_when_path_omitted(self) -> None:
        from apps.intel_hub.config_loader import load_runtime_settings

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            with patch.dict(os.environ, {"INTEL_HUB_RUNTIME_CONFIG": str(runtime_path)}, clear=False):
                settings = load_runtime_settings()

            self.assertEqual(
                settings.storage_path,
                (tmp / "intel_hub.sqlite").as_posix(),
            )

    def test_create_crawl_job_uses_browser_headless_env_default(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            with patch.dict(os.environ, {"BROWSER_HEADLESS": "true"}, clear=False):
                client = TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))
                response = client.post(
                    "/crawl-jobs",
                    json={
                        "platform": "xhs",
                        "job_type": "keyword_search",
                        "keywords": "婴儿面霜",
                        "max_notes": 20,
                        "max_comments": 10,
                    },
                )

            self.assertEqual(response.status_code, 200)
            jobs = FileJobQueue(tmp / "job_queue.json").list_all()
            self.assertEqual(len(jobs), 1)
            self.assertTrue(jobs[0].payload.get("headless"))

    def test_session_service_discovers_imported_storage_state_files_without_registry(self) -> None:
        from apps.intel_hub.workflow.session_service import SessionService

        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir)
            (sessions_dir / "xhs_state.json").write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
            (sessions_dir / "xhs_state.meta.json").write_text(
                json.dumps({"exported_at": "2026-04-27T00:00:00+00:00", "platform": "xhs"}),
                encoding="utf-8",
            )

            service = SessionService(sessions_dir)
            session = service.acquire_session("xhs")

            self.assertIsNotNone(session)
            assert session is not None
            self.assertEqual(session.platform, "xhs")
            self.assertEqual(Path(session.storage_state_path), sessions_dir / "xhs_state.json")

    def test_session_service_reports_import_required_alert_without_state_files(self) -> None:
        from apps.intel_hub.workflow.session_service import SessionService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = SessionService(Path(tmpdir))
            alerts = service.get_alerts()

            self.assertTrue(any(a.get("type") == "session_import_required" for a in alerts))

    def test_growth_lab_playwright_services_use_browser_headless_env_default(self) -> None:
        from apps.growth_lab.services.note_metrics_syncer import NoteMetricsSyncer
        from apps.growth_lab.services.xhs_publisher import XHSPublishService

        with patch.dict(os.environ, {"BROWSER_HEADLESS": "true"}, clear=False):
            publish_service = XHSPublishService()
            metrics_syncer = NoteMetricsSyncer()

        self.assertTrue(publish_service._headless)
        self.assertTrue(metrics_syncer._headless)

    def test_execute_keyword_search_fails_fast_without_imported_session_in_server_mode(self) -> None:
        from apps.intel_hub.workflow.collector_worker import execute_keyword_search
        from apps.intel_hub.workflow.crawl_status import CrawlStatusReporter
        from apps.intel_hub.workflow.job_models import CrawlJob
        from apps.intel_hub.workflow.job_queue import FileJobQueue
        from apps.intel_hub.workflow.session_service import SessionService

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            queue = FileJobQueue(tmp / "job_queue.json")
            reporter = CrawlStatusReporter(tmp / "crawl_status.json", platform="xhs")
            session_service = SessionService(tmp / "sessions")
            job = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={
                    "platform": "xhs",
                    "keywords": "婴儿面霜",
                    "max_notes": 12,
                    "max_comments": 6,
                    "login_type": "qrcode",
                    "sort_type": "popularity_descending",
                    "headless": True,
                },
                display_keyword="婴儿面霜",
            )
            queue.enqueue(job)
            queue.dequeue()

            with (
                patch.dict(os.environ, {"BROWSER_HEADLESS": "true"}, clear=False),
                patch("apps.intel_hub.workflow.collector_worker.asyncio.create_subprocess_exec") as mocked_subprocess,
            ):
                with self.assertRaisesRegex(RuntimeError, "导入登录态"):
                    asyncio.run(
                        execute_keyword_search(
                            job,
                            queue=queue,
                            reporter=reporter,
                            session_service=session_service,
                        )
                    )

            mocked_subprocess.assert_not_called()
