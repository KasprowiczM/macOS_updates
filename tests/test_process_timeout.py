"""M3: timeout must stop a TERM-ignoring parent and its child."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_fallback(snippet: str, timeout: int = 20) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["MAC_UPDATE_FORCE_TIMEOUT_FALLBACK"] = "1"
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    return subprocess.run(
        ["bash", "-c", f'source "{REPO_ROOT}/lib/proc.sh"; {snippet}'],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=timeout,
    )


class ProcessGroupTimeoutTests(unittest.TestCase):
    def test_term_ignoring_parent_and_child_stop_after_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "late.txt"
            start = time.monotonic()
            script = f"""
run_with_timeout 1 bash -c '
  trap "" TERM
  (sleep 2; echo late > "{marker}") &
  sleep 30
'
"""
            out = _run_fallback(script, timeout=15)
            elapsed = time.monotonic() - start
            self.assertEqual(out.returncode, 124, out.stderr)
            self.assertLess(elapsed, 12)
            time.sleep(3)
            self.assertFalse(
                marker.exists(),
                "child wrote after timeout — process group was not killed",
            )


if __name__ == "__main__":
    unittest.main()
