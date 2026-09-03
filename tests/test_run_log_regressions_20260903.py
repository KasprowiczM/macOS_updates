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
    def test_sigkill_before_deadline_is_not_124(self) -> None:
        """SIGKILL before the deadline is 137, not timeout 124."""
        start = time.monotonic()
        out = run_proc(
            "run_with_timeout 10 bash -c 'kill -KILL $$'",
            timeout=5,
        )
        elapsed = time.monotonic() - start
        self.assertEqual(out.returncode, 137, out.stderr)
        self.assertLess(elapsed, 2)


class ClaudeNativeInstallerPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = (REPO_ROOT / "update_npm_cli.sh").read_text(encoding="utf-8")

    def test_installed_claude_uses_self_update_not_install_sh(self) -> None:
        """install.sh always downloads ~200MB then runs a TUI (`claude install`).

        2026-09-03: binary 2.1.259 landed at 10:15; the TUI never returned, so
        brew/internet/system never ran. The vendor's own `claude update` is the
        update path once ~/.local/bin/claude exists.
        """
        self.assertIn('"claude" update', self.source)
        self.assertIn("https://claude.ai/install.sh", self.source)

    def test_claude_update_is_gated_on_existing_binary(self) -> None:
        self.assertRegex(
            self.source,
            r'command_name" = "claude".*-x "\$LOCAL_BIN/claude"',
        )


class AgentsRuleTenTests(unittest.TestCase):
    def test_rule_10_is_in_agents_md(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("hides its own diagnostic input", text)
        self.assertIn("mau_quarantine_expired_ids", text)
