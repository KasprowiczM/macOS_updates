"""Every dashboard language covers its complete UI and consent vocabulary."""

import string
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
try:
    import tui_i18n
    import tui_widgets
except ImportError:
    tui_i18n = None

REQUIRED = {"app_title", "help_body", 'context_title', 'context_workflow', 'context_navigation', 'context_answer', 'context_confirm', 'context_wizard'}
REQUIRED.update("nav_" + name for name in (
    "home", "updates", "inventory", "catalog", "diagnostics", "history", "settings", "wizard", "help"))
REQUIRED.add("nav_about")
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
REQUIRED.update(("inventory_reason_unsupported", "inventory_reason_owner_manual"))
REQUIRED.update(('catalog_hint', 'catalog_prepare', 'catalog_choose_source', 'catalog_unavailable',
                 'catalog_selection_empty', 'catalog_source_required', 'inventory_missing',
                 'installed_default_scope', 'installed_default_enable', 'installed_default_enabled',
                 'installed_default_confirm', 'wizardstep_catalog', 'wizarddesc_catalog',
                 'wizardstep_agreement', 'wizarddesc_agreement'))
REQUIRED.update(('catalog_status_manager_delegated', 'catalog_status_automatic', 'catalog_status_manual',
                 'catalog_status_already_installed', 'context_group_counts'))
REQUIRED.update(("native_observing_detail", "native_version_changed_detail", "legacy_unconfirmed_detail"))
REQUIRED.update(("internet_mode", "internet_mode_automatic", "internet_mode_per_app", "internet_batch_hint",
                 "internet_per_app_hint", "internet_mode_changed", "native_pending", "native_pending_detail"))
REQUIRED.update(("auto_resize", "window_hint", "queued", "skipped", "ui_recovery", "theme_dark", "theme_light"))
REQUIRED.update(("preview_button", "run_button", "help_button", "exit_button", "send_button", "cancel_button",
                 "output_button", "controls_hint", "disabled_control", "inventory_search", "inventory_source",
                 "inventory_sort", "inventory_reload", "inventory_save", "inventory_empty", "inventory_unavailable",
                 "inventory_scope_note", "inventory_changes", "inventory_save_first", "inventory_discard",
                 "inventory_column_name", "inventory_column_version", "inventory_column_status", "inventory_all_sources",
                 "inventory_sort_name", "inventory_sort_version", "inventory_sort_source", "inventory_sort_status",
                 "inventory_status_enabled", "inventory_status_excluded", "inventory_status_manual",
                 "inventory_status_blocked", "inventory_reason_evidence", "inventory_reason_conflict",
                 "inventory_reason_manual", "inventory_reason_excluded", "inventory_reason_consent",
                 "inventory_reason_running", "inventory_reason_deferred", "inventory_reason_review", "about_author",
                 "about_version", "about_website", "about_source", "toolkit_check", "toolkit_preview", "toolkit_apply",
                 "toolkit_idle", "toolkit_checking", "toolkit_result", "prompt_pending", "prompt_cancelled",
                 "preview_notice", "activity_unknown", "phase_progress"))
REQUIRED.update(("action_toolkit_check", "desc_toolkit_check", "action_toolkit_prepare", "desc_toolkit_prepare",
                 "toolkit_restart", "toolkit_unavailable", "toolkit_current", "toolkit_available",
                 "toolkit_status", "toolkit_current_version", "toolkit_target_version", "toolkit_reasons",
                 "toolkit_confirm_sha", "toolkit_invalid_receipt", "toolkit_terminal_required"))
REQUIRED.update(("action_native_recovery", "desc_native_recovery", "interrupt_button", "inventory_column_activity", "inventory_column_elapsed", "inventory_source_conflict", "inventory_source_managed", "inventory_source_vendor"))
REQUIRED.update("toolkit_status_" + name for name in ("blocked", "current", "available", "ready", "updated", "failed"))
REQUIRED.update("toolkit_reason_" + name for name in ("dirty", "branch", "origin", "busy", "changed", "unknown"))
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

    def test_widget_manifest_is_fully_localized(self):
        for lang in tui_i18n.LANGUAGES:
            with self.subTest(lang=lang):
                self.assertTrue(set(tui_widgets.UI_EN).issubset(tui_i18n.CATALOGS[lang]))

    def test_placeholders_match_and_values_render_in_each_language(self):
        formatter = string.Formatter()
        for lang in tui_i18n.LANGUAGES:
            for key in REQUIRED:
                fields = {field for _, field, _, _ in formatter.parse(tui_i18n.CATALOGS[lang][key]) if field}
                expected = {"code"} if key == "job_finished" else {"message"} if key == "error" else {"count"} if key == "inventory_changes" else {"version"} if key == "about_version" else {"status"} if key in ("toolkit_result", "context_workflow") else {"sha"} if key == "toolkit_confirm_sha" else {'done','total'} if key == 'context_group_counts' else set()
                self.assertEqual(fields, expected, (lang, key))
            self.assertIn("17", tui_i18n.tr("job_finished", lang, code=17))
            self.assertIn("example", tui_i18n.tr("error", lang, message="example"))
            self.assertIn("abc123", tui_i18n.tr("toolkit_confirm_sha", lang, sha="abc123"))

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
            for shortcut in ("Tab", "Space", "Enter", "80x24", "Ctrl-V"):
                self.assertIn(shortcut, catalog["help_body"], (lang, shortcut))
            self.assertGreaterEqual(catalog["help_body"].count("\n"), 5)
            for concept in ("send_button", "cancel_button", "inventory_save", "toolkit_check"):
                self.assertIn(tui_i18n.CATALOGS[lang][concept], catalog["help_body"], (lang, concept))


if __name__ == "__main__":
    unittest.main()
