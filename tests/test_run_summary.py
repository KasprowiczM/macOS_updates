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


class FormatVersion4AndMigrationTests(unittest.TestCase):
    def test_format_version_is_4(self) -> None:
        self.assertEqual(FORMAT_VERSION, 4)

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
        self.assertEqual(summary["format_version"], 4)
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
        self.assertEqual(migrated["format_version"], 4)
        self.assertEqual(migrated["items"], [])
        self.assertEqual(migrated["verification"], {})
        self.assertEqual(migrated["counts"]["observed_package_changes"], 6)
        self.assertEqual(migrated["steps"]["brew"], {"code": "ok", "text": "OK"})

        v1_data = {
            "exit_code": 0,
            "counts": {"inventory_fields_changed": 5},
        }
        migrated_v1 = migrate_run_summary(v1_data)
        self.assertEqual(migrated_v1["format_version"], 4)
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

    def test_collect_run_items_system_installed_and_deduplicated(self) -> None:
        from run_summary import collect_run_items
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "system_installed_labels.txt").write_text(
                "Command Line Tools for Xcode 27.0-27.0\n", encoding="utf-8"
            )
            (tmp_path / "system_available.txt").write_text(
                "Software Update found the following new or updated software:\n"
                "* Label: Command Line Tools for Xcode 27.0-27.0\n"
                "\tTitle: Command Line Tools for Xcode 27.0, Version: 27.0, Size: 519460KiB, Recommended: YES, \n"
                "* Label: macOS 27.1 Update-27.1\n"
                "\tTitle: macOS 27.1 Update, Version: 27.1, Size: 2519460KiB, Recommended: YES, \n",
                encoding="utf-8",
            )
            (tmp_path / "pending_system").write_text("1\n", encoding="utf-8")

            items = collect_run_items(tmp_path)
            updated_items = [it for it in items if it["status"] == "updated" and it["category"] == "system"]
            self.assertEqual(len(updated_items), 1)
            self.assertEqual(updated_items[0]["name"], "Command Line Tools for Xcode 27.0")
            self.assertEqual(updated_items[0]["new_version"], "27.0")

            pending_items = [it for it in items if it["status"] == "pending" and it["category"] == "system"]
            self.assertEqual(len(pending_items), 1)
            self.assertEqual(pending_items[0]["name"], "macOS 27.1 Update")

    def test_between_step_changes_are_attributed(self) -> None:
        from run_summary import collect_run_items
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "installed_apps_scan.txt").write_text(
                "Claude|2.2553.13\nGoogle Chrome|130.0.6723.69\n", encoding="utf-8"
            )
            (tmp_path / "installed_apps_after.txt").write_text(
                "Claude|2.7032.0\nGoogle Chrome|131.0.6778.86\n", encoding="utf-8"
            )
            (tmp_path / "appstore_ios_before.txt").write_text(
                "Picsart|30.7.2\n", encoding="utf-8"
            )
            (tmp_path / "appstore_ios_after.txt").write_text(
                "Picsart|30.8.2\n", encoding="utf-8"
            )
            (tmp_path / "internet_before.txt").write_text(
                "Google Chrome|130.0.6723.69\n", encoding="utf-8"
            )
            (tmp_path / "internet_after.txt").write_text(
                "Google Chrome|131.0.6778.86\n", encoding="utf-8"
            )

            items = collect_run_items(tmp_path)

            bg_items = [it for it in items if it.get("category") == "background"]
            self.assertEqual(len(bg_items), 1)
            bg_names = {it["name"]: it for it in bg_items}
            self.assertIn("Claude", bg_names)
            self.assertEqual(bg_names["Claude"]["old_version"], "2.2553.13")
            self.assertEqual(bg_names["Claude"]["new_version"], "2.7032.0")
            self.assertEqual(bg_names["Claude"]["status"], "updated")
            self.assertEqual(bg_names["Claude"]["details"], "updated outside toolkit steps (vendor updater / App Store)")

            appstore_items = [it for it in items if it.get("category") == "appstore"]
            self.assertEqual(len(appstore_items), 1)
            self.assertEqual(appstore_items[0]["name"], "Picsart")
            self.assertEqual(appstore_items[0]["old_version"], "30.7.2")
            self.assertEqual(appstore_items[0]["new_version"], "30.8.2")
            self.assertEqual(appstore_items[0]["status"], "updated")
            self.assertEqual(appstore_items[0]["details"], "App Store (iPad) — Track 2")

            # Google Chrome was already updated in step 5 internet, must NOT be duplicated in background
            chrome_items = [it for it in items if "Chrome" in it["name"]]
            self.assertEqual(len(chrome_items), 1)
            self.assertEqual(chrome_items[0]["category"], "internet")

    def test_ipad_update_during_track2_is_appstore_not_background(self) -> None:
        """iPad apps updated during Track 2 are attributed to appstore and not duplicated in background."""
        from run_summary import collect_run_items
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "appstore_ios_before.txt").write_text("Picsart|30.7.2\n", encoding="utf-8")
            (tmp_path / "appstore_ios_after.txt").write_text("Picsart|30.8.2\n", encoding="utf-8")
            (tmp_path / "installed_apps_scan.txt").write_text("Picsart|30.7.2\n", encoding="utf-8")
            (tmp_path / "installed_apps_after.txt").write_text("Picsart|30.8.2\n", encoding="utf-8")

            items = collect_run_items(tmp_path)
            appstore_items = [it for it in items if it.get("category") == "appstore"]
            bg_items = [it for it in items if it.get("category") == "background"]

            self.assertEqual(len(appstore_items), 1)
            self.assertEqual(appstore_items[0]["name"], "Picsart")
            self.assertEqual(appstore_items[0]["details"], "App Store (iPad) — Track 2")
            self.assertEqual(len(bg_items), 0, "iPad update should not be duplicated in background")

    def test_cask_with_different_app_name_not_duplicated_as_background(self) -> None:
        """Cask updates with different .app target names are not duplicated in background."""
        from run_summary import collect_run_items
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "brew_casks_before.txt").write_text("mycask 5.0\n", encoding="utf-8")
            (tmp_path / "brew_casks_after.txt").write_text("mycask 5.1\n", encoding="utf-8")
            (tmp_path / "brew_cask_targets.txt").write_text("mycask|MySpecialApp.app\n", encoding="utf-8")
            (tmp_path / "installed_apps_scan.txt").write_text("MySpecialApp|5.0\n", encoding="utf-8")
            (tmp_path / "installed_apps_after.txt").write_text("MySpecialApp|5.1\n", encoding="utf-8")

            items = collect_run_items(tmp_path)
            cask_items = [it for it in items if it.get("category") == "brew_cask"]
            bg_items = [it for it in items if it.get("category") == "background"]

            self.assertEqual(len(cask_items), 1)
            self.assertEqual(cask_items[0]["name"], "mycask")
            self.assertEqual(len(bg_items), 0, "Cask app target should not be duplicated as background")


if __name__ == "__main__":
    unittest.main()
