"""Tests for step status codes and schema v4 (P1-8)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from chronic_warnings import is_ok
from run_summary import (
    FORMAT_VERSION,
    build_run_summary,
    classify_step_status,
    migrate_run_summary,
)


class StepStatusCodesTests(unittest.TestCase):
    def test_classify_step_status(self) -> None:
        self.assertEqual(classify_step_status("ok"), "ok")
        self.assertEqual(classify_step_status("OK completed"), "ok")
        self.assertEqual(classify_step_status("Ostrzeżenie zakończono z ostrzeżeniami"), "warn")
        self.assertEqual(classify_step_status("Błąd podczas aktualizacji"), "error")
        self.assertEqual(classify_step_status("pominięte przez użytkownika"), "skipped_by_user")
        self.assertEqual(classify_step_status("[DRY-RUN] skipped"), "skipped")
        self.assertEqual(classify_step_status({"code": "warn", "text": "Something"}), "warn")
        self.assertEqual(classify_step_status(None), "unconfirmed")

    def test_build_run_summary_with_explicit_step_codes(self) -> None:
        step_results = {
            "prescan": "OK",
            "appstore": "Ostrzeżenie (niezweryfikowane)",
            "brew": "Błąd połączenia",
            "system": "pominięte przez użytkownika",
        }
        step_codes = {
            "prescan": "ok",
            "appstore": "warn",
            "brew": "error",
            "system": "skipped_by_user",
        }
        summary = build_run_summary(
            start_time=1000,
            end_time=1050,
            overall_exit=0,
            degraded=1,
            blocking_exit=0,
            step_results=step_results,
            step_codes=step_codes,
        )
        self.assertEqual(summary["format_version"], 4)
        self.assertEqual(summary["steps"]["prescan"]["code"], "ok")
        self.assertEqual(summary["steps"]["prescan"]["text"], "OK")
        self.assertEqual(summary["steps"]["appstore"]["code"], "warn")
        self.assertEqual(summary["steps"]["brew"]["code"], "error")
        self.assertEqual(summary["steps"]["system"]["code"], "skipped_by_user")

    def test_migrate_v3_to_v4_steps_structure(self) -> None:
        v3_data = {
            "format_version": 3,
            "run_id": "test-v3",
            "steps": {
                "prescan": "OK",
                "appstore": "OK completed",
                "brew": "Ostrzeżenie zakończono z ostrzeżeniami",
                "system": "pominięte przez użytkownika",
            },
        }
        migrated = migrate_run_summary(v3_data)
        self.assertEqual(migrated["format_version"], FORMAT_VERSION)
        self.assertEqual(migrated["steps"]["prescan"], {"code": "ok", "text": "OK"})
        self.assertEqual(migrated["steps"]["appstore"], {"code": "ok", "text": "OK completed"})
        self.assertEqual(
            migrated["steps"]["brew"],
            {"code": "warn", "text": "Ostrzeżenie zakończono z ostrzeżeniami"},
        )
        self.assertEqual(
            migrated["steps"]["system"],
            {"code": "skipped_by_user", "text": "pominięte przez użytkownika"},
        )

    def test_chronic_warnings_is_ok(self) -> None:
        self.assertTrue(is_ok({"code": "ok", "text": "OK completed"}))
        self.assertFalse(is_ok({"code": "warn", "text": "Warning"}))
        self.assertFalse(is_ok({"code": "error", "text": "Error"}))
        self.assertFalse(is_ok({"code": "skipped", "text": "Skipped"}))

        # Legacy strings
        self.assertTrue(is_ok("OK completed"))
        self.assertTrue(is_ok("OK"))
        self.assertFalse(is_ok("Ostrzeżenie"))
        self.assertFalse(is_ok("Błąd"))


if __name__ == "__main__":
    unittest.main()
