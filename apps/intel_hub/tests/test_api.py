import asyncio
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_OUTPUT = ROOT / "data" / "fixtures" / "trendradar_output" / "output"
TABLECLOTH_FIXTURE_OUTPUT = ROOT / "data" / "fixtures" / "trendradar_tablecloth" / "output"


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


def _wait_until(predicate, *, timeout: float = 2.0, interval: float = 0.02) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


class ApiSurfaceTests(unittest.TestCase):
    def test_crawl_observer_returns_idle_when_no_active_jobs(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            client = TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))
            response = client.get("/crawl-observer")
            self.assertEqual(response.status_code, 200)

            payload = response.json()
            self.assertEqual(payload["derived_state"], "idle")
            self.assertEqual(payload["stalled_reason"], "")
            self.assertIsNone(payload["active_job"])
            self.assertEqual(payload["pipeline"]["status"], "not_started")
            self.assertEqual(payload["queue"]["pending_count"], 0)

    def test_crawl_observer_detects_worker_not_running_for_pending_job(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.job_models import CrawlJob
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            queue_path = tmp / "job_queue.json"
            queue = FileJobQueue(queue_path)
            old_created_at = (datetime.now(tz=timezone.utc) - timedelta(seconds=45)).isoformat()
            job = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={"keywords": "婴儿洁面乳", "max_notes": 20},
                display_keyword="婴儿洁面乳",
                created_at=old_created_at,
            )
            queue.enqueue(job)

            client = TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))
            response = client.get("/crawl-observer")
            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload["derived_state"], "stalled")
            self.assertEqual(payload["stalled_reason"], "worker_not_running")
            self.assertEqual(payload["active_job"]["job_id"], job.job_id)
            self.assertEqual(payload["active_job"]["display_keyword"], "婴儿洁面乳")

    def test_crawl_observer_reports_pipeline_running_and_result_ready(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.job_models import CrawlJob
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            queue_path = tmp / "job_queue.json"
            queue = FileJobQueue(queue_path)
            group_id = "group123"
            crawl_job = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={"keywords": "抗老精华", "max_notes": 20},
                job_group_id=group_id,
                display_keyword="抗老精华",
            )
            queue.enqueue(crawl_job)
            queue.dequeue()
            queue.complete(crawl_job.job_id, result_path="/tmp/jsonl")

            pipeline_job = CrawlJob(
                platform="xhs",
                job_type="pipeline_refresh",
                payload={},
                job_group_id=group_id,
                display_keyword="抗老精华",
                priority=0,
            )
            queue.enqueue(pipeline_job)
            queue.dequeue()

            client = TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))
            running_response = client.get(f"/crawl-observer?job_id={crawl_job.job_id}")
            self.assertEqual(running_response.status_code, 200)
            running_payload = running_response.json()
            self.assertEqual(running_payload["derived_state"], "pipeline_running")
            self.assertEqual(running_payload["pipeline"]["job_id"], pipeline_job.job_id)
            self.assertEqual(running_payload["pipeline"]["status"], "running")

            queue.complete(pipeline_job.job_id)
            ready_response = client.get(f"/crawl-observer?job_id={crawl_job.job_id}")
            self.assertEqual(ready_response.status_code, 200)
            ready_payload = ready_response.json()
            self.assertEqual(ready_payload["derived_state"], "result_ready")
            self.assertEqual(ready_payload["pipeline"]["status"], "completed")
            self.assertEqual(
                ready_payload["actions"]["view_result_url"],
                "/notes?platform=xhs&category=%E6%8A%97%E8%80%81%E7%B2%BE%E5%8D%8E",
            )

    def test_crawl_observer_ignores_completed_ready_job_without_target(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.job_models import CrawlJob
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            queue = FileJobQueue(tmp / "job_queue.json")
            crawl_job = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={"keywords": "婴儿面霜", "max_notes": 20},
                display_keyword="婴儿面霜",
            )
            queue.enqueue(crawl_job)
            queue.dequeue()
            queue.complete(crawl_job.job_id, result_path="/tmp/jsonl")

            client = TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))
            response = client.get("/crawl-observer")
            self.assertEqual(response.status_code, 200)

            payload = response.json()
            self.assertEqual(payload["derived_state"], "idle")
            self.assertIsNone(payload["active_job"])

    def test_dashboard_and_notes_include_shared_observer_hooks(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            client = TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))

            dashboard_response = client.get("/")
            self.assertEqual(dashboard_response.status_code, 200)
            self.assertIn("crawl-observer-drawer", dashboard_response.text)
            self.assertIn("/crawl-observer", dashboard_response.text)

            notes_response = client.get("/notes", headers={"Accept": "text/html"})
            self.assertEqual(notes_response.status_code, 200)
            self.assertIn("notes:active_observer_job", notes_response.text)
            self.assertIn("window.CrawlObserver", notes_response.text)

    def test_create_crawl_job_returns_group_id_and_observer_can_target_it(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            client = TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))
            create_response = client.post(
                "/crawl-jobs",
                json={
                    "platform": "xhs",
                    "job_type": "keyword_search",
                    "keywords": "婴儿面霜",
                    "max_notes": 20,
                    "max_comments": 10,
                },
            )
            self.assertEqual(create_response.status_code, 200)
            payload = create_response.json()
            self.assertTrue(payload["job_group_id"])

            observer_response = client.get(f"/crawl-observer?job_id={payload['job_id']}")
            self.assertEqual(observer_response.status_code, 200)
            observer_payload = observer_response.json()
            self.assertEqual(observer_payload["active_job"]["job_group_id"], payload["job_group_id"])

    def test_create_crawl_job_reuses_open_batch_group_id(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            client = TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))

            first = client.post(
                "/crawl-jobs",
                json={
                    "platform": "xhs",
                    "job_type": "keyword_search",
                    "keywords": "婴儿面霜",
                    "max_notes": 20,
                    "max_comments": 10,
                },
            )
            self.assertEqual(first.status_code, 200)
            first_payload = first.json()

            second = client.post(
                "/crawl-jobs",
                json={
                    "platform": "xhs",
                    "job_type": "keyword_search",
                    "keywords": "婴儿防晒",
                    "max_notes": 20,
                    "max_comments": 10,
                },
            )
            self.assertEqual(second.status_code, 200)
            second_payload = second.json()

            self.assertEqual(first_payload["job_group_id"], second_payload["job_group_id"])

            queue = FileJobQueue(tmp / "job_queue.json")
            group_jobs = queue.list_batch_jobs(first_payload["job_group_id"])
            self.assertEqual([job.display_keyword for job in group_jobs], ["婴儿面霜", "婴儿防晒"])

    def test_file_job_queue_dequeues_crawl_before_pipeline_refresh(self) -> None:
        from apps.intel_hub.workflow.job_models import CrawlJob
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = FileJobQueue(Path(tmpdir) / "job_queue.json")
            queue.enqueue(
                CrawlJob(
                    platform="xhs",
                    job_type="keyword_search",
                    payload={"keywords": "婴儿面霜"},
                    display_keyword="婴儿面霜",
                    job_group_id="group-001",
                    priority=5,
                )
            )
            queue.enqueue(
                CrawlJob(
                    platform="xhs",
                    job_type="pipeline_refresh",
                    display_keyword="婴儿面霜",
                    job_group_id="group-001",
                    priority=0,
                )
            )
            queue.enqueue(
                CrawlJob(
                    platform="xhs",
                    job_type="keyword_search",
                    payload={"keywords": "婴儿防晒"},
                    display_keyword="婴儿防晒",
                    job_group_id="group-001",
                    priority=5,
                )
            )

            first = queue.dequeue()
            self.assertIsNotNone(first)
            assert first is not None
            self.assertEqual(first.job_type, "keyword_search")
            self.assertEqual(first.display_keyword, "婴儿面霜")
            queue.complete(first.job_id)

            second = queue.dequeue()
            self.assertIsNotNone(second)
            assert second is not None
            self.assertEqual(second.job_type, "keyword_search")
            self.assertEqual(second.display_keyword, "婴儿防晒")

    def test_crawl_observer_returns_batch_queue_summary(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.job_models import CrawlJob
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            queue = FileJobQueue(tmp / "job_queue.json")
            group_id = "batch-001"

            first = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={"keywords": "婴儿面霜", "max_notes": 20},
                display_keyword="婴儿面霜",
                job_group_id=group_id,
            )
            second = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={"keywords": "婴儿防晒", "max_notes": 20},
                display_keyword="婴儿防晒",
                job_group_id=group_id,
            )
            third = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={"keywords": "婴儿乳液", "max_notes": 20},
                display_keyword="婴儿乳液",
                job_group_id=group_id,
            )
            queue.enqueue(first)
            queue.enqueue(second)
            queue.enqueue(third)
            running = queue.dequeue()
            self.assertIsNotNone(running)

            client = TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))
            response = client.get(f"/crawl-observer?job_id={first.job_id}")
            self.assertEqual(response.status_code, 200)
            payload = response.json()

            self.assertEqual(payload["queue"]["batch_job_group_id"], group_id)
            self.assertEqual(payload["queue"]["batch_total"], 3)
            self.assertEqual(payload["queue"]["batch_completed"], 0)
            self.assertEqual(payload["queue"]["pending_count"], 2)
            self.assertEqual(payload["queue"]["running_count"], 1)
            self.assertEqual(
                [item["display_keyword"] for item in payload["queue"]["pending_jobs"]],
                ["婴儿防晒", "婴儿乳液"],
            )

    def test_embedded_worker_auto_consumes_and_enqueues_single_pipeline_refresh(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_path = _write_runtime(tmp)
            execution_order: list[tuple[str, str]] = []
            block_first = threading.Event()
            block_second = threading.Event()
            second_running = threading.Event()

            async def fake_execute_keyword_search(job, queue=None, reporter=None, session_service=None):
                execution_order.append(("start", job.display_keyword))
                if job.display_keyword == "婴儿面霜":
                    while not block_first.is_set():
                        await asyncio.sleep(0.01)
                if job.display_keyword == "婴儿防晒":
                    second_running.set()
                    while not block_second.is_set():
                        await asyncio.sleep(0.01)
                if queue:
                    queue.touch_heartbeat(job.job_id)
                execution_order.append(("done", job.display_keyword))
                return f"/tmp/{job.display_keyword}"

            def fake_run_pipeline(runtime_config_path=None, *, enable_vision=False):
                execution_order.append(("pipeline", str(runtime_config_path or "")))
                return None

            with patch(
                "apps.intel_hub.workflow.collector_worker.execute_keyword_search",
                new=AsyncMock(side_effect=fake_execute_keyword_search),
            ), patch(
                "apps.intel_hub.workflow.refresh_pipeline.run_pipeline",
                side_effect=fake_run_pipeline,
            ):
                with TestClient(create_app(runtime_path, enable_embedded_crawl_worker=True)) as client:
                    first = client.post(
                        "/crawl-jobs",
                        json={
                            "platform": "xhs",
                            "job_type": "keyword_search",
                            "keywords": "婴儿面霜",
                            "max_notes": 20,
                            "max_comments": 10,
                        },
                    )
                    self.assertEqual(first.status_code, 200)

                    started = _wait_until(
                        lambda: (
                            (lambda job: job is not None and job.status in ("running", "completed"))(
                                FileJobQueue(tmp / "job_queue.json").get_job(first.json()["job_id"])
                            )
                        )
                    )
                    self.assertTrue(started)

                    second = client.post(
                        "/crawl-jobs",
                        json={
                            "platform": "xhs",
                            "job_type": "keyword_search",
                            "keywords": "婴儿防晒",
                            "max_notes": 20,
                            "max_comments": 10,
                        },
                    )
                    self.assertEqual(second.status_code, 200)
                    self.assertEqual(first.json()["job_group_id"], second.json()["job_group_id"])

                    block_first.set()

                    entered_second = _wait_until(second_running.is_set)
                    self.assertTrue(entered_second)

                    observer = client.get(f"/crawl-observer?job_id={first.json()['job_id']}")
                    self.assertEqual(observer.status_code, 200)
                    observer_payload = observer.json()
                    self.assertEqual(observer_payload["derived_state"], "crawling")
                    self.assertEqual(observer_payload["queue"]["batch_total"], 2)
                    self.assertEqual(observer_payload["queue"]["batch_completed"], 1)
                    self.assertEqual(observer_payload["queue"]["running_count"], 1)
                    self.assertEqual(observer_payload["queue"]["pending_count"], 0)
                    self.assertEqual(observer_payload["active_job"]["display_keyword"], "婴儿防晒")

                    block_second.set()

                    drained = _wait_until(
                        lambda: FileJobQueue(tmp / "job_queue.json").find_pipeline_job(
                            first.json()["job_group_id"],
                            statuses=("completed",),
                        )
                        is not None,
                        timeout=3.0,
                    )
                    self.assertTrue(drained)

                    queue = FileJobQueue(tmp / "job_queue.json")
                    jobs = queue.list_batch_jobs(first.json()["job_group_id"])
                    self.assertEqual(
                        [(job.job_type, job.status) for job in jobs],
                        [
                            ("keyword_search", "completed"),
                            ("keyword_search", "completed"),
                            ("pipeline_refresh", "completed"),
                        ],
                    )
                    self.assertEqual(
                        execution_order,
                        [
                            ("start", "婴儿面霜"),
                            ("done", "婴儿面霜"),
                            ("start", "婴儿防晒"),
                            ("done", "婴儿防晒"),
                            ("pipeline", str(runtime_path)),
                        ],
                    )

    def test_file_job_queue_supports_heartbeat_and_group_queries(self) -> None:
        from apps.intel_hub.workflow.job_models import CrawlJob
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = FileJobQueue(Path(tmpdir) / "job_queue.json")
            base_job = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={"keywords": "餐桌布"},
                job_group_id="group-heartbeat",
                display_keyword="餐桌布",
            )
            queue.enqueue(base_job)
            queue.dequeue()

            self.assertTrue(queue.touch_heartbeat(base_job.job_id))
            job = queue.get_job(base_job.job_id)
            self.assertIsNotNone(job)
            self.assertIsNotNone(job.last_heartbeat_at)

            pipeline_job = CrawlJob(
                platform="xhs",
                job_type="pipeline_refresh",
                payload={},
                job_group_id="group-heartbeat",
                display_keyword="餐桌布",
            )
            queue.enqueue(pipeline_job)

            group_jobs = queue.list_group_jobs("group-heartbeat")
            self.assertEqual(len(group_jobs), 2)
            self.assertEqual({j.job_type for j in group_jobs}, {"keyword_search", "pipeline_refresh"})

            queue.fail(base_job.job_id, "network timeout")
            self.assertTrue(queue.retry(base_job.job_id))
            retried_job = queue.get_job(base_job.job_id)
            self.assertIsNotNone(retried_job)
            assert retried_job is not None
            self.assertEqual(retried_job.status, "pending")
            self.assertIsNone(retried_job.started_at)
            self.assertIsNone(retried_job.completed_at)
            self.assertIsNone(retried_job.last_heartbeat_at)
            self.assertIsNone(retried_job.result_path)

    def test_process_one_job_uses_custom_status_and_alert_paths(self) -> None:
        from apps.intel_hub.workflow.collector_worker import process_one_job
        from apps.intel_hub.workflow.job_models import CrawlJob
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            queue = FileJobQueue(tmp / "job_queue.json")
            status_path = tmp / "crawl_status.json"
            alerts_path = tmp / "alerts.json"
            job = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={"keywords": "防晒喷雾", "max_notes": 20},
                display_keyword="防晒喷雾",
            )
            queue.enqueue(job)

            with patch(
                "apps.intel_hub.workflow.collector_worker.execute_keyword_search",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ):
                processed = asyncio.run(
                    process_one_job(
                        queue,
                        status_path=status_path,
                        alerts_path=alerts_path,
                    )
                )

            self.assertTrue(processed)
            platform_status_path = status_path.with_name("crawl_status_xhs.json")
            self.assertTrue(platform_status_path.exists())
            self.assertTrue(alerts_path.exists())

            status_payload = json.loads(platform_status_path.read_text(encoding="utf-8"))
            self.assertEqual(status_payload["status"], "failed")

            alerts_payload = json.loads(alerts_path.read_text(encoding="utf-8"))
            self.assertEqual(len(alerts_payload["alerts"]), 1)
            self.assertEqual(alerts_payload["alerts"][0]["alert_type"], "crawl_failure")
            self.assertIn(job.job_id, alerts_payload["alerts"][0]["title"])

    def test_mediacrawler_dependency_paths_include_embedded_site_packages(self) -> None:
        from apps.intel_hub.workflow.collector_worker import MC_ROOT, _mediacrawler_dependency_paths

        paths = _mediacrawler_dependency_paths()

        self.assertGreaterEqual(len(paths), 1)
        self.assertEqual(paths[0], MC_ROOT)
        self.assertTrue(
            any(path.as_posix().endswith("site-packages") for path in paths[1:]),
            "expected MediaCrawler embedded site-packages to be included",
        )

    def test_crawl_runner_builds_legacy_main_semantics_command(self) -> None:
        from apps.intel_hub.workflow.crawl_runner import (
            MC_LEGACY_RUNNER,
            MC_VENV_PYTHON,
            build_legacy_crawl_command,
        )

        command = build_legacy_crawl_command(
            platform="xhs",
            keywords="婴儿面霜,婴儿乳液",
            login_type="qrcode",
            max_notes=12,
            max_comments=6,
            sort_type="popularity_descending",
            headless=False,
            status_path=Path("/tmp/crawl_status_xhs.json"),
            session_id="session-001",
        )

        self.assertEqual(command[0], str(MC_VENV_PYTHON))
        self.assertEqual(command[1], str(MC_LEGACY_RUNNER))
        self.assertIn("--platform", command)
        self.assertIn("xhs", command)
        self.assertIn("--lt", command)
        self.assertIn("qrcode", command)
        self.assertIn("--type", command)
        self.assertIn("search", command)
        self.assertIn("--save_data_option", command)
        self.assertIn("jsonl", command)
        self.assertIn("--keywords", command)
        self.assertIn("婴儿面霜,婴儿乳液", command)
        self.assertIn("--max_notes", command)
        self.assertIn("12", command)
        self.assertIn("--max_comments", command)
        self.assertIn("6", command)
        self.assertIn("--sort_type", command)
        self.assertIn("popularity_descending", command)
        self.assertIn("--status_path", command)
        self.assertIn("/tmp/crawl_status_xhs.json", command)
        self.assertIn("--session_id", command)
        self.assertIn("session-001", command)

    def test_execute_keyword_search_uses_legacy_mediacrawler_main_runner(self) -> None:
        from apps.intel_hub.workflow.collector_worker import execute_keyword_search
        from apps.intel_hub.workflow.crawl_status import CrawlStatusReporter
        from apps.intel_hub.workflow.crawl_runner import MC_LEGACY_RUNNER, MC_VENV_PYTHON
        from apps.intel_hub.workflow.job_models import CrawlJob
        from apps.intel_hub.workflow.job_queue import FileJobQueue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            queue = FileJobQueue(tmp / "job_queue.json")
            reporter = CrawlStatusReporter(tmp / "crawl_status.json", platform="xhs")
            job = CrawlJob(
                platform="xhs",
                job_type="keyword_search",
                payload={
                    "keywords": "婴儿面霜",
                    "max_notes": 12,
                    "max_comments": 6,
                    "platform": "xhs",
                    "login_type": "qrcode",
                    "sort_type": "popularity_descending",
                },
                display_keyword="婴儿面霜",
            )
            queue.enqueue(job)
            queue.dequeue()

            captured: dict[str, object] = {}

            class FakeProcess:
                async def wait(self) -> int:
                    return 0

            async def fake_create_subprocess_exec(*args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
                return FakeProcess()

            with patch(
                "apps.intel_hub.workflow.collector_worker.asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess_exec,
            ):
                result = asyncio.run(execute_keyword_search(job, queue=queue, reporter=reporter))

            args = cast(tuple[object, ...], captured["args"])
            kwargs = cast(dict[str, object], captured["kwargs"])

            self.assertTrue(str(result).endswith("third_party/MediaCrawler/data/xhs/jsonl"))
            self.assertEqual(args[0], str(MC_VENV_PYTHON))
            self.assertEqual(args[1], str(MC_LEGACY_RUNNER))
            self.assertIn("--platform", args)
            self.assertIn("xhs", args)
            self.assertIn("--lt", args)
            self.assertIn("qrcode", args)
            self.assertIn("--type", args)
            self.assertIn("search", args)
            self.assertIn("--save_data_option", args)
            self.assertIn("jsonl", args)
            self.assertIn("--keywords", args)
            self.assertIn("婴儿面霜", args)
            self.assertIn("--max_notes", args)
            self.assertIn("12", args)
            self.assertIn("--max_comments", args)
            self.assertIn("6", args)
            self.assertIn("--sort_type", args)
            self.assertIn("popularity_descending", args)
            self.assertIn("--status_path", args)
            self.assertIn(str(reporter.path), args)
            self.assertEqual(kwargs["cwd"], str(MC_LEGACY_RUNNER.parent))
            kwargs = cast(dict[str, object], captured["kwargs"])
            env = cast(dict[str, str], kwargs["env"])
            self.assertNotIn("INTEL_HUB_STATUS_PATH", env)
            self.assertNotIn("INTEL_HUB_KEYWORDS", env)

    def test_legacy_runner_resets_argv_before_delegating_to_mediacrawler(self) -> None:
        from pathlib import Path as _Path

        runner_path = _Path(
            "/Users/yichen/Desktop/OntologyBrain/Ai- native 经营操作OS/third_party/MediaCrawler/legacy_intel_hub_runner.py"
        )
        source = runner_path.read_text(encoding="utf-8")

        namespace: dict[str, object] = {}
        start = source.index("def _reset_argv_for_mediacrawler")
        end = source.index("\n\ndef cli", start)
        exec("import sys\n" + source[start:end], namespace)
        reset_argv = namespace["_reset_argv_for_mediacrawler"]
        fake_sys = namespace["sys"]
        fake_sys.argv = ["legacy_intel_hub_runner.py", "--max_notes", "12", "--status_path", "/tmp/status.json"]

        reset_argv()

        self.assertEqual(fake_sys.argv, ["legacy_intel_hub_runner.py"])

    def test_b2b_platform_bootstrap_queue_and_content_planning_review(self) -> None:
        from fastapi.testclient import TestClient

        from apps.b2b_platform.storage import B2BPlatformStore
        from apps.content_planning.storage.plan_store import ContentPlanStore
        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.schemas.evidence import XHSEvidenceRef
        from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
        from apps.intel_hub.storage.xhs_review_store import XHSReviewStore

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        f"trendradar_output_dir: {FIXTURE_OUTPUT.as_posix()}",
                        f"storage_path: {storage_path.as_posix()}",
                        f"b2b_platform_db_path: {(tmp / 'b2b.sqlite').as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                    ]
                ),
                encoding="utf-8",
            )

            review_store = XHSReviewStore(tmp / "xhs_review.sqlite")
            card = XHSOpportunityCard(
                opportunity_id="opp_api_b2b_001",
                title="桌布场景机会卡",
                summary="promoted 机会卡",
                opportunity_type="visual",
                scene_refs=["早餐"],
                style_refs=["奶油风"],
                need_refs=["提升颜值"],
                visual_pattern_refs=["暖调"],
                audience_refs=["精致宝妈"],
                value_proposition_refs=["氛围感强"],
                evidence_refs=[XHSEvidenceRef(snippet="桌布很出片")],
                source_note_ids=["note_001"],
                confidence=0.92,
                opportunity_status="promoted",
            )
            cards_json = tmp / "cards.json"
            cards_json.write_text(f"[{card.model_dump_json()}]", encoding="utf-8")
            review_store.sync_cards_from_json(cards_json)

            client = TestClient(
                create_app(
                    runtime_path,
                    review_store=review_store,
                    content_plan_store=ContentPlanStore(tmp / "plan.sqlite"),
                    platform_store=B2BPlatformStore(tmp / "b2b.sqlite"),
                )
            )

            bootstrap = client.post(
                "/b2b/bootstrap",
                json={
                    "organization_name": "Acme Group",
                    "workspace_name": "Acme Beauty",
                    "brand_name": "Acme Table",
                    "campaign_name": "Spring Launch",
                    "admin_user_id": "u_admin",
                    "admin_display_name": "Admin",
                },
            )
            self.assertEqual(bootstrap.status_code, 200)
            payload = bootstrap.json()
            workspace_id = payload["workspace"]["workspace_id"]
            brand_id = payload["brand"]["brand_id"]
            campaign_id = payload["campaign"]["campaign_id"]
            token = payload["admin_membership"]["api_token"]
            headers = {
                "X-Workspace-Id": workspace_id,
                "X-User-Id": "u_admin",
                "X-Api-Token": token,
            }

            queued = client.post(
                f"/b2b/workspaces/{workspace_id}/opportunities/{card.opportunity_id}/queue",
                headers=headers,
                json={"brand_id": brand_id, "campaign_id": campaign_id, "queue_status": "promoted"},
            )
            self.assertEqual(queued.status_code, 200)

            brief = client.post(
                f"/content-planning/xhs-opportunities/{card.opportunity_id}/generate-brief",
                headers=headers,
            )
            self.assertEqual(brief.status_code, 200)
            self.assertEqual(brief.json()["workspace_id"], workspace_id)

            approved = client.post(
                f"/content-planning/xhs-opportunities/{card.opportunity_id}/approve",
                headers=headers,
                json={"object_type": "brief", "decision": "approved", "notes": "Ready"},
            )
            self.assertEqual(approved.status_code, 200)
            self.assertEqual(approved.json()["decision"], "approved")

            usage = client.get(f"/b2b/workspaces/{workspace_id}/usage", headers=headers)
            self.assertEqual(usage.status_code, 200)
            self.assertEqual(usage.json()["by_event_type"]["brief_generated"], 1)

    def test_api_serves_paginated_lists_and_html_dashboard(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
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
            client = TestClient(create_app(runtime_path))

            signals_response = client.get("/signals?page=1&page_size=10")
            self.assertEqual(signals_response.status_code, 200)
            self.assertEqual(signals_response.json()["total"], 3)

            opportunities_response = client.get("/opportunities?page=1&page_size=10")
            self.assertEqual(opportunities_response.status_code, 200)
            self.assertGreaterEqual(opportunities_response.json()["total"], 1)

            risks_response = client.get("/risks?page=1&page_size=10")
            self.assertEqual(risks_response.status_code, 200)
            self.assertGreaterEqual(risks_response.json()["total"], 1)

            watchlists_response = client.get("/watchlists?page=1&page_size=10")
            self.assertEqual(watchlists_response.status_code, 200)
            self.assertGreaterEqual(watchlists_response.json()["total"], 3)

            dashboard_response = client.get("/")
            self.assertEqual(dashboard_response.status_code, 200)
            self.assertIn("主线 1 · 内容生产", dashboard_response.text)
            self.assertIn("主线 2 · 增长实验室", dashboard_response.text)
            self.assertIn("主线 3 · 套图工作台", dashboard_response.text)

    def test_api_filters_tablecloth_entity_and_platform(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.refresh_pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        f"trendradar_output_dir: {TABLECLOTH_FIXTURE_OUTPUT.as_posix()}",
                        f"storage_path: {storage_path.as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                    ]
                ),
                encoding="utf-8",
            )

            run_pipeline(runtime_path)
            client = TestClient(create_app(runtime_path))

            signals_response = client.get("/signals?entity=category_tablecloth&platform=weibo")
            self.assertEqual(signals_response.status_code, 200)
            self.assertGreaterEqual(signals_response.json()["total"], 1)

            opportunities_response = client.get("/opportunities?entity=category_tablecloth&platform=weibo")
            self.assertEqual(opportunities_response.status_code, 200)
            self.assertGreaterEqual(opportunities_response.json()["total"], 1)

    def test_api_supports_review_writeback_and_filtering(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
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
            client = TestClient(create_app(runtime_path))

            opportunity = client.get("/opportunities").json()["items"][0]
            review_response = client.post(
                f"/opportunities/{opportunity['id']}/review",
                json={
                    "review_status": "accepted",
                    "review_notes": "Reviewed by API test",
                    "reviewer": "api_reviewer",
                    "feedback_tags": ["confirmed"],
                },
            )
            self.assertEqual(review_response.status_code, 200)
            self.assertEqual(review_response.json()["review_status"], "accepted")
            self.assertEqual(review_response.json()["reviewer"], "api_reviewer")
            self.assertIsNotNone(review_response.json()["reviewed_at"])

            filtered = client.get("/opportunities?review_status=accepted&reviewer=api_reviewer")
            self.assertEqual(filtered.status_code, 200)
            self.assertEqual(filtered.json()["total"], 1)

            risk = client.get("/risks").json()["items"][0]
            risk_review_response = client.post(
                f"/risks/{risk['id']}/review",
                json={
                    "review_status": "needs_followup",
                    "review_notes": "Need more evidence",
                    "reviewer": "risk_reviewer",
                },
            )
            self.assertEqual(risk_review_response.status_code, 200)
            self.assertEqual(risk_review_response.json()["review_status"], "needs_followup")

    def test_api_rejects_invalid_review_status(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
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
            client = TestClient(create_app(runtime_path))
            opportunity = client.get("/opportunities").json()["items"][0]

            response = client.post(
                f"/opportunities/{opportunity['id']}/review",
                json={
                    "review_status": "not_valid",
                    "review_notes": "bad",
                    "reviewer": "api_reviewer",
                },
            )

            self.assertEqual(response.status_code, 422)


class VisualBuilderBootstrapTests(unittest.TestCase):
    """覆盖 /planning/{id}/visual-builder 首屏 bootstrap + 参考图过滤行为。"""

    def _client_with_first_card(self):
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.content_planning.storage.plan_store import ContentPlanStore

        tmp = Path(tempfile.mkdtemp())
        runtime_path = _write_runtime(tmp)
        # 使用独立的 ContentPlanStore 避免污染共享的 data/content_plan.sqlite
        plan_store = ContentPlanStore(tmp / "content_plan.sqlite")
        client = TestClient(
            create_app(
                runtime_path,
                enable_embedded_crawl_worker=False,
                content_plan_store=plan_store,
            )
        )
        cards_resp = client.get(
            "/xhs-opportunities", headers={"accept": "application/json"}
        )
        self.assertEqual(cards_resp.status_code, 200)
        items = cards_resp.json().get("items", [])
        self.assertTrue(items, "fixture xhs-opportunities should not be empty")
        opp_id = items[0]["opportunity_id"]
        return client, opp_id, plan_store

    def test_visual_builder_bootstrap_keys_present(self) -> None:
        client, opp_id, _ = self._client_with_first_card()
        resp = client.get(
            f"/planning/{opp_id}/visual-builder",
            headers={"accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("bootstrap", body)
        bs = body["bootstrap"]
        for key in (
            "opportunity_id",
            "quick_draft",
            "titles",
            "body",
            "image_briefs",
            "saved_prompts",
            "initial_prompts",
            "ref_count",
            "has_ref_images",
            "gen_mode_effective",
            "latest_generated_images",
        ):
            self.assertIn(key, bs, f"bootstrap 缺少 {key}")

    def test_visual_builder_filters_example_com_covers(self) -> None:
        """注入 example.com cover，验证 _persist_source_images 过滤后 ref_count=0。"""
        client, opp_id, plan_store = self._client_with_first_card()
        # 注入仅含 example.com 占位 URL 的 source_images
        plan_store.save_session(opp_id)
        plan_store.update_field(
            opp_id,
            "source_images",
            [
                {
                    "note_id": "fixture1",
                    "title": "占位笔记",
                    "cover_image": "https://example.com/cover.jpg",
                    "image_urls": [
                        "https://example.com/cover.jpg",
                        "https://example.com/img2.jpg",
                    ],
                    "ref_quality": "unusable_fixture",
                }
            ],
        )
        resp = client.get(
            f"/planning/{opp_id}/visual-builder",
            headers={"accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        bs = resp.json()["bootstrap"]
        self.assertEqual(bs["ref_count"], 0, msg=f"bootstrap={bs}")
        self.assertFalse(bs["has_ref_images"])
        self.assertEqual(bs["gen_mode_effective"], "prompt_only")

    def test_visual_builder_with_real_cover_keeps_ref_count(self) -> None:
        """注入一条带真实 cover 的 source_images，应得到 ref_count > 0 且 gen_mode_effective=ref_image。"""
        client, opp_id, plan_store = self._client_with_first_card()
        plan_store.save_session(opp_id)
        plan_store.update_field(
            opp_id,
            "source_images",
            [
                {
                    "note_id": "fake1",
                    "title": "真实笔记",
                    "cover_image": "https://sns-img-bd.xhscdn.com/abc.jpg",
                    "image_urls": [
                        "https://sns-img-bd.xhscdn.com/abc.jpg",
                        "https://sns-img-bd.xhscdn.com/def.jpg",
                    ],
                    "ref_quality": "ok",
                }
            ],
        )

        resp = client.get(
            f"/planning/{opp_id}/visual-builder",
            headers={"accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        bs = resp.json()["bootstrap"]
        self.assertGreater(bs["ref_count"], 0, msg=f"bootstrap={bs}")
        self.assertTrue(bs["has_ref_images"])
        self.assertEqual(bs["gen_mode_effective"], "ref_image")


class ImgProxyTests(unittest.TestCase):
    """覆盖 /img-proxy：白名单准入 + 上游 mock 透传 + 失败占位。"""

    def _make_client(self):
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app

        tmp = Path(tempfile.mkdtemp())
        runtime_path = _write_runtime(tmp)
        return TestClient(
            create_app(runtime_path, enable_embedded_crawl_worker=False)
        )

    def test_img_proxy_rejects_non_whitelisted_host(self) -> None:
        client = self._make_client()
        resp = client.get("/img-proxy", params={"url": "https://example.com/x.jpg"})
        self.assertEqual(resp.status_code, 400)

    def test_img_proxy_rejects_relative_url(self) -> None:
        client = self._make_client()
        resp = client.get("/img-proxy", params={"url": "/source-images/x.jpg"})
        self.assertEqual(resp.status_code, 400)

    def test_img_proxy_streams_whitelisted_xhscdn(self) -> None:
        client = self._make_client()
        fake_bytes = b"\x89PNG\r\n\x1a\nfake-image-bytes"

        class _FakeResp:
            status_code = 200
            content = fake_bytes
            headers = {"content-type": "image/png"}

        class _FakeClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url, headers=None):
                return _FakeResp()

        with patch("apps.intel_hub.api.app.httpx.AsyncClient", _FakeClient):
            resp = client.get(
                "/img-proxy",
                params={"url": "https://sns-img-bd.xhscdn.com/abc.jpg"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("content-type"), "image/png")
        self.assertEqual(resp.content, fake_bytes)


class OpportunityAgentRunsTests(unittest.TestCase):
    """覆盖 4 条新路由 + xhs_opportunities 空态新文案。"""

    def _make_client(self, tmp: Path):
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app

        runtime_path = _write_runtime(tmp)
        return TestClient(create_app(runtime_path, enable_embedded_crawl_worker=False))

    def test_xhs_opportunities_empty_state_renders_business_copy_and_drawer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = self._make_client(Path(tmpdir))
            resp = client.get(
                "/xhs-opportunities",
                params={"lens": "wig"},
                headers={"Accept": "text/html"},
            )
            self.assertEqual(resp.status_code, 200)
            text = resp.text
            self.assertNotIn(
                "请先运行 <code>python -m apps.intel_hub.workflow.xhs_opportunity_pipeline",
                text,
            )
            self.assertTrue(
                "立即生成机会卡" in text,
                "新空态文案应包含「立即生成机会卡」",
            )
            self.assertIn("OpportunityAgentRunner", text)
            self.assertIn("/xhs-opportunities/agent-runs", text)

    def test_no_source_run_emits_failed_with_guide(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = self._make_client(Path(tmpdir))
            # 启动一个 lens=wig 的任务，因 fixtures 中无 wig 笔记应得 no_source
            resp = client.post(
                "/xhs-opportunities/agent-runs",
                json={"lens_id": "wig", "max_notes": 3},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("task_id", data)
            self.assertEqual(data["lens_id"], "wig")
            task_id = data["task_id"]

            # 轮询 snapshot 直到 failed/done
            ok = _wait_until(
                lambda: client.get(f"/xhs-opportunities/agent-runs/{task_id}").json().get("status")
                in {"failed", "done", "cancelled"},
                timeout=8.0,
                interval=0.05,
            )
            self.assertTrue(ok, "Agent 任务未在超时内进入终态")
            snap = client.get(f"/xhs-opportunities/agent-runs/{task_id}").json()
            self.assertEqual(snap["status"], "failed")
            self.assertIsNotNone(snap.get("error"))
            self.assertEqual(snap["error"]["error_kind"], "no_source")
            self.assertIn("/notes?lens=wig", snap["error"]["suggested_url"])

    def test_double_start_returns_409(self) -> None:
        from apps.intel_hub.services.agent_run_registry import agent_run_registry

        # 清理可能残留的注册表（避免与其他测试串扰）
        agent_run_registry._tasks.clear()  # type: ignore[attr-defined]

        with tempfile.TemporaryDirectory() as tmpdir:
            client = self._make_client(Path(tmpdir))
            # 先占住一个 lens
            tid, _ = agent_run_registry.start("wig", lens_label="假发")
            try:
                resp = client.post(
                    "/xhs-opportunities/agent-runs",
                    json={"lens_id": "wig", "max_notes": 3},
                )
                self.assertEqual(resp.status_code, 409)
            finally:
                agent_run_registry.mark_cancelled(tid)

    def test_cancel_endpoint_returns_404_for_unknown_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = self._make_client(Path(tmpdir))
            resp = client.post("/xhs-opportunities/agent-runs/__missing__/cancel")
            self.assertEqual(resp.status_code, 404)

    def test_get_snapshot_returns_404_for_unknown_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = self._make_client(Path(tmpdir))
            resp = client.get("/xhs-opportunities/agent-runs/__missing__")
            self.assertEqual(resp.status_code, 404)

    def test_start_agent_run_default_max_notes_is_one(self) -> None:
        """默认请求体只带 lens_id 时，max_notes 应被解析为 1（先跑 1 条预览）。"""
        from apps.intel_hub.services.agent_run_registry import agent_run_registry

        agent_run_registry._tasks.clear()  # type: ignore[attr-defined]

        captured: dict[str, object] = {}

        class _StubAgent:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            async def run(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmpdir:
            # 注意：create_app 内 `from ... import OpportunityGenAgent`
            # 会把 class 绑定到 closure 局部变量，因此 patch 必须在
            # _make_client 之前进入，才能让闭包拿到 stub。
            with patch(
                "apps.intel_hub.services.opportunity_gen_agent.OpportunityGenAgent",
                _StubAgent,
            ):
                client = self._make_client(Path(tmpdir))
                resp = client.post(
                    "/xhs-opportunities/agent-runs",
                    json={"lens_id": "wig"},
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                self.assertEqual(captured.get("max_notes"), 1)
                self.assertEqual(list(captured.get("skip_note_ids") or []), [])
                self.assertIsNone(captured.get("note_id_filter"))

    def test_start_agent_run_passes_skip_note_ids_to_agent(self) -> None:
        """skip_note_ids 应被透传到 OpportunityGenAgent，用于增量补跑。"""
        from apps.intel_hub.services.agent_run_registry import agent_run_registry

        agent_run_registry._tasks.clear()  # type: ignore[attr-defined]

        captured: dict[str, object] = {}

        class _StubAgent:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            async def run(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "apps.intel_hub.services.opportunity_gen_agent.OpportunityGenAgent",
                _StubAgent,
            ):
                client = self._make_client(Path(tmpdir))
                resp = client.post(
                    "/xhs-opportunities/agent-runs",
                    json={
                        "lens_id": "wig",
                        "max_notes": 5,
                        "skip_note_ids": ["a", "b", "c"],
                    },
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                self.assertEqual(captured.get("max_notes"), 5)
                self.assertEqual(list(captured.get("skip_note_ids") or []), ["a", "b", "c"])

    def test_xhs_opportunities_groups_cards_by_source_note(self) -> None:
        """带 lens 过滤的列表渲染应按 source_note_id 分组、显示 angle chip。"""
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.schemas.evidence import XHSEvidenceRef
        from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
        from apps.intel_hub.storage.xhs_review_store import XHSReviewStore

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # 写 mediacrawler 风格 jsonl，让 _get_notes 能把 note_id -> 标题/封面
            # join 进 note_groups 元信息（用于断言 "本笔记产出 N 张机会卡"）。
            jsonl_dir = tmp / "mc_jsonl"
            jsonl_dir.mkdir()
            jsonl_dir.joinpath("search_contents_test.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "note_id": "note_shared",
                                "title": "桌布同源原始笔记",
                                "desc": "两张机会卡的来源笔记。",
                                "image_list": "https://sns-img-bd.xhscdn.com/share.jpg",
                                "source_keyword": "桌布",
                                "lens_id": "tablecloth",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "note_id": "note_other",
                                "title": "另一篇桌布笔记",
                                "desc": "用于检查跨来源排序。",
                                "image_list": "https://sns-img-bd.xhscdn.com/other.jpg",
                                "source_keyword": "桌布",
                                "lens_id": "tablecloth",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        f"trendradar_output_dir: {FIXTURE_OUTPUT.as_posix()}",
                        f"storage_path: {(tmp / 'intel_hub.sqlite').as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                        "mediacrawler_sources:",
                        "  - enabled: true",
                        "    platform: xiaohongshu",
                        f"    output_path: {jsonl_dir.as_posix()}",
                    ]
                ),
                encoding="utf-8",
            )
            review_store = XHSReviewStore(tmp / "xhs_review.sqlite")

            cards = [
                XHSOpportunityCard(
                    opportunity_id="opp_grp_visual",
                    title="视觉钩子卡",
                    summary="同源笔记的视觉角度",
                    opportunity_type="visual",
                    content_angle="撞色对比",
                    source_note_ids=["note_shared"],
                    evidence_refs=[XHSEvidenceRef(snippet="s1")],
                    confidence=0.91,
                    lens_id="tablecloth",
                ),
                XHSOpportunityCard(
                    opportunity_id="opp_grp_demand",
                    title="需求洞察卡",
                    summary="同源笔记的需求角度",
                    opportunity_type="demand",
                    content_angle="租房党痛点",
                    source_note_ids=["note_shared"],
                    evidence_refs=[XHSEvidenceRef(snippet="s2")],
                    confidence=0.85,
                    lens_id="tablecloth",
                ),
                XHSOpportunityCard(
                    opportunity_id="opp_grp_other",
                    title="另一篇笔记的卡",
                    summary="独立来源",
                    opportunity_type="visual",
                    source_note_ids=["note_other"],
                    evidence_refs=[XHSEvidenceRef(snippet="s3")],
                    confidence=0.7,
                    lens_id="tablecloth",
                ),
            ]
            cards_json = tmp / "cards.json"
            cards_json.write_text(
                json.dumps([c.model_dump(mode="json") for c in cards], ensure_ascii=False),
                encoding="utf-8",
            )
            review_store.sync_cards_from_json(cards_json)

            client = TestClient(
                create_app(
                    runtime_path,
                    review_store=review_store,
                    enable_embedded_crawl_worker=False,
                )
            )
            resp = client.get(
                "/xhs-opportunities",
                params={"lens": "tablecloth"},
                headers={"Accept": "text/html"},
            )
            self.assertEqual(resp.status_code, 200)
            text = resp.text
            self.assertIn("note-group", text, "应渲染 note-group 容器")
            self.assertIn("本笔记产出 2 张机会卡", text)
            self.assertIn("angle-chip", text, "应在卡片上渲染角度 chip")
            self.assertIn("撞色对比", text)
            self.assertIn("租房党痛点", text)
            visual_idx = text.find("视觉钩子卡")
            demand_idx = text.find("需求洞察卡")
            other_idx = text.find("另一篇笔记的卡")
            self.assertTrue(0 < visual_idx < other_idx, "同源两张卡应排在另一篇笔记前")
            self.assertTrue(0 < demand_idx < other_idx, "同源两张卡应排在另一篇笔记前")


if __name__ == "__main__":
    unittest.main()
