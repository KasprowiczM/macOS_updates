#!/usr/bin/env python3
"""tests/test_appstore_mas.py — Tests for mas account version gate and macOS 26.x messages."""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class AppStoreMasGateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="macupd_test_mas_")
        self.bin_dir = os.path.join(self.temp_dir, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)
        self.old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{self.bin_dir}:{self.old_path}"

    def tearDown(self):
        os.environ["PATH"] = self.old_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_mock_bin(self, name: str, script_body: str) -> str:
        bin_path = os.path.join(self.bin_dir, name)
        with open(bin_path, "w", encoding="utf-8") as f:
            f.write(f"#!/bin/sh\n{script_body}\n")
        os.chmod(bin_path, os.stat(bin_path).st_mode | stat.S_IXUSR)
        return bin_path

    def test_mas5_does_not_call_account_and_no_macos26_warning(self):
        log_file = os.path.join(self.temp_dir, "mas_invocations.log")
        # Mock mas 7.0.0 where account fails with Unexpected argument
        mas_script = f"""
echo "$@" >> "{log_file}"
case "$1" in
    version)
        echo "7.0.0"
        exit 0
        ;;
    account)
        echo "Error: Unexpected argument 'account'" >&2
        exit 1
        ;;
    list)
        echo "497799835 Xcode (27.0)"
        exit 0
        ;;
    outdated)
        exit 0
        ;;
    *)
        exit 0
        ;;
esac
"""
        self._create_mock_bin("mas", mas_script)
        # Mock brew
        self._create_mock_bin("brew", 'echo "Homebrew 7.0.2"; exit 0')
        # Mock osascript
        self._create_mock_bin("osascript", 'exit 0')

        sdir = Path(self.temp_dir) / "session"
        sdir.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        env["MAC_UPDATE_SESSION_DIR"] = str(sdir)
        env["MAC_UPDATE_NONINTERACTIVE"] = "1"
        env["MAC_UPDATE_YES"] = "1"
        env["MAC_LANG"] = "pl"

        res = subprocess.run(
            ["bash", str(REPO_ROOT / "update_appstore.sh")],
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(res.returncode, 0, f"Script failed: {res.stderr}")
        # Output should NOT contain macOS 26
        self.assertNotIn("macOS 26", res.stdout)
        self.assertNotIn("macOS 26", res.stderr)

        # Invocations log must NOT contain account
        if os.path.exists(log_file):
            invocations = Path(log_file).read_text(encoding="utf-8").splitlines()
            account_calls = [inv for inv in invocations if inv.startswith("account")]
            self.assertEqual(account_calls, [], "mas account should not be called for mas >= 5")

    def test_appstore_user_session_retry_diagnostics_and_soft_fail(self):
        log_file = os.path.join(self.temp_dir, "mas_invocations.log")
        mas_script = f"""
echo "$@" >> "{log_file}"
case "$1" in
    version)
        echo "7.0.0"
        exit 0
        ;;
    list)
        echo "6446904124 Whisper Transcription (15.1.1)"
        exit 0
        ;;
    outdated)
        echo "6446904124 Whisper Transcription (15.1.1 -> 15.2.1)"
        exit 0
        ;;
    upgrade)
        echo "upgrade called with: $@"
        exit 0
        ;;
    *)
        exit 0
        ;;
esac
"""
        self._create_mock_bin("mas", mas_script)
        self._create_mock_bin("brew", 'echo "Homebrew 7.0.2"; exit 0')
        self._create_mock_bin("osascript", 'exit 0')
        sudo_script = """
if [ "$1" = "-v" ]; then
    exit 0
fi
if [ "$1" = "-n" ]; then
    shift
fi
"$@"
"""
        self._create_mock_bin("sudo", sudo_script)

        sdir = Path(self.temp_dir) / "session"
        sdir.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        env["MAC_UPDATE_SESSION_DIR"] = str(sdir)
        env["MAC_UPDATE_NONINTERACTIVE"] = "1"
        env["MAC_UPDATE_YES"] = "1"
        env["MAC_LANG"] = "en"

        res = subprocess.run(
            ["bash", str(REPO_ROOT / "update_appstore.sh")],
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(res.returncode, 10, f"Expected soft exit (10), got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}")
        self.assertIn("6446904124", res.stdout)
        self.assertIn("Whisper Transcription", res.stdout)
        # Verify retry is recorded in appstore_diag.txt
        diag_file = sdir / "appstore_diag.txt"
        self.assertTrue(diag_file.exists(), "appstore_diag.txt was not created")
        diag_content = diag_file.read_text(encoding="utf-8")
        self.assertIn("TRACK 1 user-session retry", diag_content)
        self.assertIn("Whisper Transcription", diag_content)
        # Verify manual update hint in output
        self.assertIn("manual", res.stdout.lower())


if __name__ == "__main__":
    unittest.main()
