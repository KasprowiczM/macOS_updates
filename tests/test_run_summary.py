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


class FormatVersion3AndMigrationTests(unittest.TestCase):
    def test_format_version_is_3(self) -> None:
        self.assertEqual(FORMAT_VERSION, 3)

    def test_build_run_summary_has_items_field(self) -> None:
        sample_item = {
            "name": "WhatsApp",
            "category": "appstore",
            "old_version": "26.35.72",
            "new_version": "26.35.74",
            "status": "updated",
            "details": None,
        }
        summary = build_run_summary(
            start_time=100,
            end_time=150,
            overall_exit=0,
            degraded=0,
            blocking_exit=0,
            step_results={"appstore": "OK"},
            items=[sample_item],
        )
        self.assertEqual(summary["format_version"], 3)
        self.assertEqual(len(summary["items"]), 1)
        self.assertEqual(summary["items"][0]["name"], "WhatsApp")

    def test_migrate_run_summary_backward_compatibility(self) -> None:
        from run_summary import migrate_run_summary
        v2_data = {
            "format_version": 2,
            "run_id": "v2-run",
            "run_status": "completed",
            "counts": {"observed_package_changes": 6, "inventory_version_fields_changed": 9},
            "steps": {"brew": "OK"},
        }
        migrated = migrate_run_summary(v2_data)
        self.assertEqual(migrated["format_version"], 3)
        self.assertEqual(migrated["items"], [])
        self.assertEqual(migrated["verification"], {})
        self.assertEqual(migrated["counts"]["observed_package_changes"], 6)

        v1_data = {
            "exit_code": 0,
            "counts": {"inventory_fields_changed": 5},
        }
        migrated_v1 = migrate_run_summary(v1_data)
        self.assertEqual(migrated_v1["format_version"], 3)
        self.assertEqual(migrated_v1["run_status"], "completed")
        self.assertEqual(migrated_v1["items"], [])
        self.assertEqual(migrated_v1["counts"]["inventory_version_fields_changed"], 5)


class RunItemsAndTerminalSummaryTests(unittest.TestCase):
    def test_collect_run_items_from_snapshots(self) -> None:
        from run_summary import collect_run_items, format_terminal_summary
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 1. App Store
            (tmp_path / "mas_before.txt").write_text(" 310633997  WhatsApp  (26.35.72)\n", encoding="utf-8")
            (tmp_path / "mas_after.txt").write_text(" 310633997  WhatsApp  (26.35.74)\n", encoding="utf-8")
            # 2. Formula
            (tmp_path / "brew_formulae_before.txt").write_text("nss 3.109\nuv 0.6.2\n", encoding="utf-8")
            (tmp_path / "brew_formulae_after.txt").write_text("nss 3.110\nuv 0.6.3\n", encoding="utf-8")
            # 3. Cask
            (tmp_path / "brew_casks_before.txt").write_text("stripe 1.23.0\n", encoding="utf-8")
            (tmp_path / "brew_casks_after.txt").write_text("stripe 1.24.0\n", encoding="utf-8")
            # 4. npm CLI
            (tmp_path / "npm_cli_before.txt").write_text(
                "claude-code|@anthropic-ai/claude-code|2.1.266|claude|/bin/claude\n", encoding="utf-8"
            )
            (tmp_path / "npm_cli_after.txt").write_text(
                "claude-code|@anthropic-ai/claude-code|2.1.267|claude|/bin/claude\n", encoding="utf-8"
            )
            # 5. MAU remaining
            (tmp_path / "mau_remaining.txt").write_text("MSWD2019 XCEL2019\n", encoding="utf-8")
            (tmp_path / "mau_interrupt_reason.txt").write_text("Update Assistant terminated.\n", encoding="utf-8")

            step_results = {
                "internet": "completed with warnings (unverified)",
            }
            items = collect_run_items(tmp_path, step_results=step_results, inventory_updated_count=9)

            updated_names = [it["name"] for it in items if it["status"] == "updated"]
            self.assertIn("WhatsApp", updated_names)
            self.assertIn("nss", updated_names)
            self.assertIn("uv", updated_names)
            self.assertIn("stripe", updated_names)
            self.assertIn("claude-code", updated_names)

            pending_items = [it for it in items if it["status"] == "pending"]
            pending_names = [it["name"] for it in pending_items]
            self.assertTrue(any("Word" in n for n in pending_names))
            self.assertTrue(any("Excel" in n for n in pending_names))

            unconfirmed_items = [it for it in items if it["status"] == "unconfirmed"]
            self.assertTrue(any("Internet apps" in it["name"] for it in unconfirmed_items))

            summary = {
                "items": items,
                "counts": {
                    "inventory_version_fields_changed": 9,
                    "observed_package_changes": len(updated_names),
                },
            }
            term_en = format_terminal_summary(summary, lang="en")
            self.assertIn("Updated:", term_en)
            self.assertIn("WhatsApp", term_en)
            self.assertIn("26.35.72 -> 26.35.74", term_en)
            self.assertIn("Still pending / failed:", term_en)
            self.assertIn("Microsoft Word", term_en)
            self.assertIn("Update Assistant terminated.", term_en)
            self.assertIn("Updater launched, but update not confirmed:", term_en)
            self.assertIn("Inventory version fields changed: 9", term_en)

            term_pl = format_terminal_summary(summary, lang="pl")
            self.assertIn("Zaktualizowano:", term_pl)
            self.assertIn("Nadal oczekuje / niepowodzenie:", term_pl)
            self.assertIn("Uruchomiono updater, ale nie potwierdzono aktualizacji:", term_pl)
            self.assertIn("Zmieniono pól wersji w inventory: 9", term_pl)


if __name__ == "__main__":
    unittest.main()
