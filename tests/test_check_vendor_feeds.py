#!/usr/bin/env bash
"""tests/test_check_vendor_feeds.py — Tests for scripts/check_vendor_feeds.sh (T14)."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class CheckVendorFeedsTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self) -> None:
        script = REPO_ROOT / "scripts" / "check_vendor_feeds.sh"
        self.assertTrue(script.is_file())
        st = os.stat(script)
        self.assertTrue(bool(st.st_mode & stat.S_IXUSR))

    def test_check_vendor_feeds_json_mode(self) -> None:
        # Run with mock PATH or direct invocation
        res = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts" / "check_vendor_feeds.sh"), "--json"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(res.returncode, 0, f"Error:\n{res.stdout}\n{res.stderr}")
        data = json.loads(res.stdout)
        self.assertIsInstance(data, list)
        app_names = [item["app"] for item in data]
        self.assertIn("Google Chrome", app_names)
        self.assertIn("Gemini", app_names)
        self.assertIn("Comet", app_names)


if __name__ == "__main__":
    unittest.main()
