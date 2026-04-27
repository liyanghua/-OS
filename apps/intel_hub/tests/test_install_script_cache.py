import hashlib
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INSTALL_SCRIPT = ROOT / "install.sh"


def _extract_function_body(name: str) -> str:
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    marker = f"{name}() {{"
    start = text.index(marker)
    tail = text[start:]
    end = tail.index("\n}\n")
    return tail[:end + 3]


class InstallScriptCacheTests(unittest.TestCase):
    def test_install_script_contains_dependency_fingerprint_helpers(self) -> None:
        text = INSTALL_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("CACHE_DIR=", text)
        self.assertIn("ROOT_DEPS_FINGERPRINT_FILE=", text)
        self.assertIn("TR_DEPS_FINGERPRINT_FILE=", text)
        self.assertIn("MC_DEPS_FINGERPRINT_FILE=", text)
        self.assertIn("compute_file_sha256()", text)
        self.assertIn("install_if_fingerprint_changed()", text)

    def test_install_script_uses_cache_gates_for_repeated_installs(self) -> None:
        text = INSTALL_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('skip_root=1', text)
        self.assertIn('skip_tr=1', text)
        self.assertIn('skip_mc=1', text)
        self.assertIn('playwright_browser_ready()', text)
        self.assertIn('TrendRadar 已在目标 commit', text)

    def test_install_script_contains_apt_lock_wait_helpers(self) -> None:
        text = INSTALL_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("APT_LOCK_WAIT_SECONDS=", text)
        self.assertIn("APT_LOCK_RETRY_SECONDS=", text)
        self.assertIn("wait_for_apt_lock()", text)
        self.assertIn("apt_get()", text)
        self.assertIn("apt_get install -y", text)

    def test_apt_related_installs_go_through_retry_wrapper(self) -> None:
        text = INSTALL_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('apt_get update -y', text)
        self.assertIn('apt_get install -y --no-install-recommends "${missing[@]}"', text)
        self.assertIn('apt_get install -y python3.11 python3.11-venv python3.11-dev', text)
        self.assertIn('apt_get install -y python3.12 python3.12-venv python3.12-dev', text)

    def test_compute_file_sha256_matches_python_hash(self) -> None:
        body = _extract_function_body("compute_file_sha256")
        shell = "\n".join(
            [
                "set -euo pipefail",
                body,
                'compute_file_sha256 "$1"',
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "sample.txt"
            target.write_text("hello install cache\n", encoding="utf-8")
            expected = hashlib.sha256(target.read_bytes()).hexdigest()

            import subprocess

            result = subprocess.run(
                ["bash", "-lc", shell, "bash", str(target)],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), expected)
