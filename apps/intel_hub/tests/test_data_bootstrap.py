import argparse
import io
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
EXPORT_SCRIPT = ROOT / "scripts" / "export_dataset.sh"
BOOTSTRAP_SCRIPT = ROOT / "scripts" / "bootstrap_data.sh"


def _create_sqlite(path: Path, statements: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


def _build_bundle(bundle_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _create_sqlite(
            root / "data" / "intel_hub.sqlite",
            [
                "CREATE TABLE opportunity_cards (id TEXT PRIMARY KEY)",
                "INSERT INTO opportunity_cards (id) VALUES ('opp_1')",
            ],
        )
        (root / "data" / "alerts.json").write_text('{"items":["legacy_alert"]}', encoding="utf-8")
        (root / "data" / "job_queue.json").write_text('{"jobs":["legacy_job"]}', encoding="utf-8")
        with tarfile.open(bundle_path, "w:gz") as tar:
            tar.add(root / "data", arcname="data")


class BootstrapDataCliTests(unittest.TestCase):
    def test_manifest_supports_legacy_and_repo_relative_sqlite_keys(self) -> None:
        from apps.intel_hub.scripts import bootstrap_data

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _create_sqlite(
                repo_root / "data" / "intel_hub.sqlite",
                [
                    "CREATE TABLE opportunity_cards (id TEXT PRIMARY KEY)",
                    "INSERT INTO opportunity_cards (id) VALUES ('opp_1')",
                ],
            )
            manifest_path = repo_root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "sqlite_rows": {
                            "intel_hub.sqlite::opportunity_cards": 1,
                            "data/intel_hub.sqlite::opportunity_cards": 1,
                        }
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.object(
                    bootstrap_data,
                    "resolve_repo_path",
                    side_effect=lambda rel: repo_root / rel,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                rc = bootstrap_data.cmd_manifest(argparse.Namespace(path=str(manifest_path)))

            self.assertEqual(rc, 0)
            self.assertNotIn("[DIFF] intel_hub.sqlite::opportunity_cards", stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")


class BootstrapShellScriptTests(unittest.TestCase):
    def test_import_snapshot_skips_runtime_state_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bundle_path = tmp / "dataset.tar.gz"
            install_dir = tmp / "install"
            install_dir.mkdir()
            (install_dir / "pyproject.toml").write_text("", encoding="utf-8")
            (install_dir / "data").mkdir()
            (install_dir / "data" / "alerts.json").write_text(
                '{"items":["stale_alert"]}', encoding="utf-8"
            )
            _build_bundle(bundle_path)

            result = subprocess.run(
                [
                    "bash",
                    str(BOOTSTRAP_SCRIPT),
                    "--bundle",
                    str(bundle_path),
                    "--install-dir",
                    str(install_dir),
                    "--no-sync",
                    "--no-validate",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertTrue((install_dir / "data" / "intel_hub.sqlite").exists())
            self.assertFalse((install_dir / "data" / "alerts.json").exists())
            self.assertFalse((install_dir / "data" / "job_queue.json").exists())

    def test_restart_service_stops_before_restart_when_importing_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bundle_path = tmp / "dataset.tar.gz"
            install_dir = tmp / "install"
            fake_bin = tmp / "bin"
            log_path = tmp / "systemctl.log"
            install_dir.mkdir()
            fake_bin.mkdir()
            (install_dir / "pyproject.toml").write_text("", encoding="utf-8")
            _build_bundle(bundle_path)

            (fake_bin / "sudo").write_text(
                "#!/bin/sh\nexec \"$@\"\n",
                encoding="utf-8",
            )
            (fake_bin / "systemctl").write_text(
                (
                    "#!/bin/sh\n"
                    f"echo \"$@\" >> \"{log_path}\"\n"
                    "if [ \"$1\" = \"list-unit-files\" ]; then\n"
                    "  echo 'ontology-os.service enabled'\n"
                    "  exit 0\n"
                    "fi\n"
                    "if [ \"$1\" = \"is-active\" ]; then\n"
                    "  exit 0\n"
                    "fi\n"
                    "exit 0\n"
                ),
                encoding="utf-8",
            )
            os.chmod(fake_bin / "sudo", 0o755)
            os.chmod(fake_bin / "systemctl", 0o755)

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            result = subprocess.run(
                [
                    "bash",
                    str(BOOTSTRAP_SCRIPT),
                    "--bundle",
                    str(bundle_path),
                    "--install-dir",
                    str(install_dir),
                    "--no-sync",
                    "--no-validate",
                    "--restart-service",
                ],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            lines = log_path.read_text(encoding="utf-8").splitlines()
            stop_index = next(i for i, line in enumerate(lines) if line == "stop ontology-os")
            restart_index = next(i for i, line in enumerate(lines) if line == "restart ontology-os")
            self.assertLess(stop_index, restart_index)


class ExportDatasetShellScriptTests(unittest.TestCase):
    def test_export_bundle_omits_runtime_state_files_and_uses_repo_relative_manifest_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            scripts_dir = repo_root / "scripts"
            output_dir = repo_root / "data" / "output" / "xhs_opportunities"
            mc_dir = repo_root / "third_party" / "MediaCrawler" / "data" / "xhs" / "jsonl"
            scripts_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)
            mc_dir.mkdir(parents=True)
            shutil.copy2(EXPORT_SCRIPT, scripts_dir / "export_dataset.sh")

            _create_sqlite(
                repo_root / "data" / "intel_hub.sqlite",
                [
                    "CREATE TABLE opportunity_cards (id TEXT PRIMARY KEY)",
                    "INSERT INTO opportunity_cards (id) VALUES ('opp_1')",
                ],
            )
            (repo_root / "data" / "alerts.json").write_text("{}", encoding="utf-8")
            (repo_root / "data" / "job_queue.json").write_text("{}", encoding="utf-8")
            (output_dir / "opportunity_cards.json").write_text("[]", encoding="utf-8")
            (output_dir / "pipeline_details.json").write_text("[]", encoding="utf-8")
            (mc_dir / "sample.jsonl").write_text('{"note_id":"n1"}\n', encoding="utf-8")

            bundle_path = repo_root / "dist" / "dataset.tar.gz"
            result = subprocess.run(
                [
                    "bash",
                    str(scripts_dir / "export_dataset.sh"),
                    "--lite",
                    "--out",
                    str(bundle_path),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            extract_dir = repo_root / "extracted"
            extract_dir.mkdir()
            with tarfile.open(bundle_path, "r:gz") as tar:
                tar.extractall(extract_dir)

            self.assertFalse((extract_dir / "data" / "alerts.json").exists())
            self.assertFalse((extract_dir / "data" / "job_queue.json").exists())

            manifest = json.loads((extract_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("data/intel_hub.sqlite::opportunity_cards", manifest["sqlite_rows"])
            self.assertNotIn("intel_hub.sqlite::opportunity_cards", manifest["sqlite_rows"])
