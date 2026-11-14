"""Every dashboard language covers its complete UI and consent vocabulary."""

import string
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
try:
    import tui_i18n
except ImportError:
    tui_i18n = None

REQUIRED = {"app_title", "help_body"}
REQUIRED.update("nav_" + name for name in (
    "home", "updates", "inventory", "catalog", "diagnostics", "history", "settings", "wizard", "help"))
REQUIRED.update(prefix + name for prefix in ("action_", "desc_") for name in (
    "preview", "update", "inventory", "setup_inspect", "setup_dependencies", "setup_shell", "catalog",
    "preferences", "doctor", "coverage", "sources", "migration_preview"))
REQUIRED.update((
    "actions", "groups", "details", "live_log", "tasks", "idle", "running", "completed", "warnings", "failed",
    "waiting", "elapsed", "progress", "unknown", "none", "start", "confirm", "cancel", "back", "next", "finish",
    "save", "saved", "input", "secret_input", "input_hint", "confirm_body", "interrupt_body", "busy", "no_history",
    "history_hint", "help_title", "shortcut_hint", "resize", "palette", "search", "language", "theme", "ascii",
    "wizard_complete", "wizard_intro", "settings_hint", "groups_hint", "serial_notice", "readonly_notice", "error",
    "quit_body", "not_available", "job_finished", "scan_hint", "copy", "paste", "copied", "clipboard_unavailable",
    "copy_command", "copy_log", "copy_summary"))
REQUIRED.update(("auto_resize", "window_hint", "queued", "skipped", "ui_recovery", "theme_dark", "theme_light"))
REQUIRED.update("group_" + name for name in ("appstore", "npm", "brew", "internet", "system"))
REQUIRED.update(prefix + name for prefix in ("wizardstep_", "wizarddesc_") for name in (
    "welcome", "requirements", "inventory", "sources", "settings", "preview", "finish"))


class TuiTranslationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(tui_i18n, "dashboard translation catalog is missing")

    def test_every_language_covers_the_complete_dashboard_interface(self):
        self.assertEqual(tui_i18n.LANGUAGES, ("en", "pl", "de", "es", "fr", "it", "pt"))
        self.assertEqual(set(tui_i18n.CATALOGS), set(tui_i18n.LANGUAGES))
        for lang in tui_i18n.LANGUAGES:
            with self.subTest(lang=lang):
                self.assertEqual(set(tui_i18n.CATALOGS[lang]), REQUIRED)
                for key in REQUIRED:
                    text = tui_i18n.tr(key, lang)
                    self.assertIsInstance(text, str)
                    self.assertTrue(text.strip(), key)
                    self.assertNotEqual(text, key)

    def test_placeholders_match_and_values_render_in_each_language(self):
        formatter = string.Formatter()
        for lang in tui_i18n.LANGUAGES:
            for key in REQUIRED:
                fields = {field for _, field, _, _ in formatter.parse(tui_i18n.CATALOGS[lang][key]) if field}
                expected = {"code"} if key == "job_finished" else {"message"} if key == "error" else set()
                self.assertEqual(fields, expected, (lang, key))
            self.assertIn("17", tui_i18n.tr("job_finished", lang, code=17))
            self.assertIn("example", tui_i18n.tr("error", lang, message="example"))

    def test_unknown_language_falls_back_and_missing_values_stay_visible(self):
        self.assertEqual(tui_i18n.tr("confirm_body", "unsupported"), tui_i18n.tr("confirm_body", "en"))
        self.assertEqual(tui_i18n.tr("not_a_ui_key", "pl"), "not_a_ui_key")
        self.assertIn("{code}", tui_i18n.tr("job_finished", "pl"))

    def test_safety_and_help_are_translated_with_all_shortcuts(self):
        for lang in tui_i18n.LANGUAGES:
            catalog = tui_i18n.CATALOGS[lang]
            if lang != "en":
                for key in ("confirm_body", "interrupt_body", "input_hint", "help_body", "settings_hint", "window_hint"):
                    self.assertNotEqual(catalog[key], tui_i18n.CATALOGS["en"][key], (lang, key))
            self.assertIn("80x24", catalog["resize"])
            self.assertIn("80x24", catalog.get("window_hint", ""))
            self.assertIn("Enter", catalog["input_hint"])
            self.assertIn(" i", catalog["input_hint"])
            for shortcut in ("Up/Down", "Tab", "Space", "Enter", "F1", "Ctrl-P", "Esc", "PgUp/PgDn", "Ctrl-V"):
                self.assertIn(shortcut, catalog["help_body"], (lang, shortcut))
            self.assertGreaterEqual(catalog["help_body"].count("\n"), 5)


if __name__ == "__main__":
    unittest.main()
