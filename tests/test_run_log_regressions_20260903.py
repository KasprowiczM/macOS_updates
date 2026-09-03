"""Regressions for the 2026-09-03 hang and Ultra Review R1–R6 (v1.4.4)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_proc(snippet: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'source "{REPO_ROOT}/lib/proc.sh"; {snippet}'],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=timeout,
    )


class TimeoutKillAfterTests(unittest.TestCase):
    def test_term_ignoring_child_still_returns_124(self) -> None:
        """GNU timeout without --kill-after waits forever if the child traps TERM.

        That is the 2026-09-03 hang class: claude install TUI after a successful
        binary swap. The bash fallback already SIGKILLs; the GNU path must too.
        """
        start = time.monotonic()
        out = run_proc(
            'run_with_timeout 1 bash -c \'trap "" TERM; sleep 30\'',
            timeout=15,
        )
        elapsed = time.monotonic() - start
        self.assertEqual(out.returncode, 124, out.stderr)
        self.assertLess(elapsed, 10)
