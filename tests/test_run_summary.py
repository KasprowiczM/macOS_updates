"""M2/M6: pending measurements and inventory counts must not impersonate installs."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from run_summary import (  # noqa: E402
    FORMAT_VERSION,
    build_run_summary,
    merge_pending,
    write_run_summary,
)


class PendingMeasurementTests(unittest.TestCase):
    def test_missing_measurement_is_unknown_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            counts, verification = merge_pending({}, tmp)
            self.assertIsNone(counts["pending_after_run_appstore"])
            self.assertEqual(verification["pending_after_run_appstore"], "missing")
            self.assertIsNone(counts["pending_after_run_mau"])

    def test_corrupt_measurement_is_unknown_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "pending_appstore").write_text("not-a-number\n", encoding="utf-8")
            counts, verification = merge_pending({}, tmp)
            self.assertIsNone(counts["pending_after_run_appstore"])
            self.assertEqual(verification["pending_after_run_appstore"], "invalid")

    def test_successful_empty_queue_is_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "pending_appstore").write_text("0\n", encoding="utf-8")
            Path(tmp, "pending_brew_formulae").write_text("0\n", encoding="utf-8")
            Path(tmp, "pending_brew_casks").write_text("0\n", encoding="utf-8")
            Path(tmp, "pending_mau").write_text("0\n", encoding="utf-8")
            counts, verification = merge_pending({}, tmp)
            self.assertEqual(counts["pending_after_run_appstore"], 0)
            self.assertEqual(verification["pending_after_run_appstore"], "verified")
            self.assertEqual(counts["pending_after_run_mau"], 0)


class InventoryCountHonestyTests(unittest.TestCase):
    def test_table_edits_are_not_named_installs(self) -> None:
        text = (REPO_ROOT / "update_all.sh").read_text(encoding="utf-8")
        self.assertIn('"inventory_version_fields_changed": updated_count', text)
        self.assertIn("observed_package_changes", text)
        self.assertIn("L_POSTUPDATE_INVENTORY_FIELDS_CHANGED", text)
        self.assertIn("L_POSTUPDATE_OBSERVED_PACKAGE_CHANGES", text)
        self.assertNotIn("L_POSTUPDATE_TOTAL_VERSION_CHANGES", text)

    def test_summary_keeps_unknown_pending_and_format_version(self) -> None:
        summary = build_run_summary(
            start_time=1,
            end_time=2,
            overall_exit=0,
            degraded=0,
            blocking_exit=0,
            step_results={"prescan": "OK"},
            counts={"inventory_version_fields_changed": 18, "observed_package_changes": 10},
            verification={"pending_after_run_appstore": "missing"},
            run_status="completed",
            run_id="run-test",
        )
        self.assertEqual(summary["format_version"], FORMAT_VERSION)
        self.assertEqual(summary["run_status"], "completed")
        self.assertEqual(summary["run_id"], "run-test")
        self.assertEqual(summary["counts"]["inventory_version_fields_changed"], 18)
        self.assertEqual(summary["counts"]["observed_package_changes"], 10)
        self.assertNotEqual(
            summary["counts"]["inventory_version_fields_changed"],
            summary["counts"]["observed_package_changes"],
        )
        self.assertEqual(summary["verification"]["pending_after_run_appstore"], "missing")

    def test_write_run_summary_uses_private_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_summary.json"
            summary = build_run_summary(
                start_time=1, end_time=2, overall_exit=0, degraded=0,
                blocking_exit=0, step_results={},
            )
            write_run_summary(path, summary)
            mode = path.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("format_version", loaded)
            self.assertIn("run_status", loaded)


class JsonWriteFailureIsVisible(unittest.TestCase):
    def test_summary_write_is_not_silently_ignored(self) -> None:
        text = (REPO_ROOT / "update_all.sh").read_text(encoding="utf-8")
        idx = text.find("write_machine_summary completed")
        self.assertGreater(idx, 0)
        self.assertNotIn("2>/dev/null || true", text[idx:idx + 250])


if __name__ == "__main__":
    unittest.main()
