"""Node.js release selection: never an alpha/rc as the managed toolchain."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from node_releases import latest_stable_node  # noqa: E402


class LatestStableNodeTests(unittest.TestCase):
    def test_skips_alpha_at_index_head(self) -> None:
        # nodejs.org/dist/index.json on 2026-10-30.
        index = [
            {"version": "v27.0.0-alpha.0.0.0", "lts": False},
            {"version": "v26.13.0", "lts": "Lithium"},
            {"version": "v26.12.1", "lts": False},
        ]
        self.assertEqual(latest_stable_node(index), "v26.13.0")

    def test_skips_rc_nightly_and_malformed(self) -> None:
        index = [{"version": "v28.0.0-rc.1"}, {"version": "v28.0.0-nightly2026"}, {}, "x", {"version": "v27.1.0"}]
        self.assertEqual(latest_stable_node(index), "v27.1.0")

    def test_no_stable_release_returns_none(self) -> None:
        self.assertIsNone(latest_stable_node([{"version": "v27.0.0-alpha.1"}]))
        self.assertIsNone(latest_stable_node([]))

    def test_update_npm_cli_never_uses_index_head_or_n_latest(self) -> None:
        src = (REPO_ROOT / "update_npm_cli.sh").read_text(encoding="utf-8")
        self.assertNotIn('arr[0]["version"]', src)
        self.assertIn("latest_stable_node", src)
        self.assertNotIn('"$n_bin" latest', src)


if __name__ == "__main__":
    unittest.main()
