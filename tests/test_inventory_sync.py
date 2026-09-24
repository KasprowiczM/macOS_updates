#!/usr/bin/env python3
"""tests/test_inventory_sync.py — Unit tests for lib/python/inventory_sync.py."""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

# Add lib/python to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR / "lib" / "python"))

import inventory_sync


class InventorySyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_path = SCRIPT_DIR / "tests" / "fixtures" / "inventory" / "APPLICATIONS_sample.md"
        with open(self.fixture_path, "r", encoding="utf-8") as f:
            self.sample_md = f.read()

        methods_path = SCRIPT_DIR / "config" / "internet_app_methods.txt"
        with open(methods_path, "r", encoding="utf-8") as f:
            self.methods_rows = [line.strip() for line in f if line.strip()]

    def test_mas_group_removes_uninstalled_and_merges_detached_row(self) -> None:
        # Notion Web Clipper (1559269364) is uninstalled; GarageBand (682658836) is installed
        mas_apps = {
            "937984704": ("Amphetamine", "5.3"),
            "6738511300": ("Copilot", "1.0"),
            "682658836": ("GarageBand", "10.4.11"),
        }
        new_md, added, removed = inventory_sync.sync_mas_group(self.sample_md, mas_apps)

        self.assertIn("1559269364", removed)
        self.assertNotIn("Notion Web Clipper", new_md)
        self.assertIn("| GarageBand | 682658836 |", new_md)
        self.assertNotIn("GarageBand 🆕", new_md)
        # Should be a single table under GRUPA 2
        g2_span = inventory_sync.section_span(new_md, r"^## GRUPA 2\b")
        self.assertIsNotNone(g2_span)
        g2_text = new_md[g2_span[0]:g2_span[1]]
        # Exactly 3 data rows in GRUPA 2 table
        data_rows = re.findall(r"^\|\s*([^|\n]+?)\s*\|\s*(\d{6,})\s*\|", g2_text, re.MULTILINE)
        self.assertEqual(len(data_rows), 3)
        self.assertEqual(data_rows[0][0].strip(), "Amphetamine")
        self.assertEqual(data_rows[1][0].strip(), "Copilot")
        self.assertEqual(data_rows[2][0].strip(), "GarageBand")

    def test_mas_group_none_is_noop(self) -> None:
        new_md, added, removed = inventory_sync.sync_mas_group(self.sample_md, None)
        self.assertEqual(new_md, self.sample_md)
        self.assertEqual(added, [])
        self.assertEqual(removed, [])

    def test_ipad_section_created_and_group3_rows_removed(self) -> None:
        ipad_apps = [
            ("UniFi", "1057750342", "10.0"),
            ("S2M", "123456789", "1.0"),
        ]
        new_md, count = inventory_sync.sync_ipad_section(self.sample_md, ipad_apps)
        self.assertEqual(count, 2)
        self.assertIn("### 📱 Aplikacje iPad na Apple Silicon (App Store)", new_md)
        self.assertIn("| UniFi | 1057750342 | 10.0 |", new_md)
        self.assertIn("| S2M | 123456789 | 1.0 |", new_md)
        self.assertNotIn("> ⚠️ **Aplikacje iPad na Apple Silicon**", new_md)

        # Remove iPad apps from GRUPA 3
        cleaned_md, removed_from_g3 = inventory_sync.remove_names_from_group3(new_md, {"UniFi", "S2M"})
        self.assertIn("UniFi", removed_from_g3)
        self.assertIn("S2M", removed_from_g3)

        g3_span = inventory_sync.section_span(cleaned_md, r"^## GRUPA 3\b")
        self.assertIsNotNone(g3_span)
        g3_text = cleaned_md[g3_span[0]:g3_span[1]]
        self.assertNotIn("UniFi", g3_text)
        self.assertNotIn("S2M", g3_text)

    def test_formulae_and_casks_removed_when_uninstalled(self) -> None:
        # stale-pkg and old-dep are uninstalled
        installed_formulae = {"mas", "ca-certificates"}
        md_form, form_removed = inventory_sync.sync_formulae(self.sample_md, installed_formulae)
        self.assertIn("stale-pkg", form_removed)
        self.assertIn("old-dep", form_removed)
        self.assertNotIn("stale-pkg", md_form)
        self.assertNotIn("old-dep", md_form)
        self.assertIn("mas", md_form)
        self.assertIn("ca-certificates", md_form)

        # stale-cask is uninstalled
        installed_casks = {"appcleaner"}
        md_casks, casks_removed = inventory_sync.sync_casks(md_form, installed_casks)
        self.assertIn("stale-cask", casks_removed)
        self.assertNotIn("stale-cask", md_casks)
        self.assertIn("appcleaner", md_casks)

    def test_cli_section_rebuilt_from_detected(self) -> None:
        detected_clis = [
            ("bun", "1.4.2"),
            ("cursor-agent", "2026.09.23"),
        ]
        new_md, added, removed = inventory_sync.rebuild_cli_section(self.sample_md, detected_clis)
        self.assertIn("cursor-agent", added)
        self.assertIn("gemini-cli", removed)
        self.assertIn("qwen-code", removed)

        g4_span = inventory_sync.section_span(new_md, r"^## GRUPA 4\b")
        self.assertIsNotNone(g4_span)
        g4_text = new_md[g4_span[0]:g4_span[1]]
        s4d = inventory_sync.section_span(g4_text, r"^### 4d\b")
        self.assertIsNotNone(s4d)
        d4_text = g4_text[s4d[0]:s4d[1]]

        self.assertIn("| bun | 1.4.2 | Bun runtime |", d4_text)
        self.assertIn("| cursor-agent | 2026.09.23 | — |", d4_text)
        self.assertNotIn("gemini-cli", d4_text)
        self.assertNotIn("qwen-code", d4_text)

    def test_guard_never_wipes_whole_group(self) -> None:
        # Pass empty sets for groups that have rows in sample_md
        flaky_facts = {
            "mas": {},  # empty query
            "formulae": set(),  # empty query
            "casks_nonorphan": set(),  # empty query
            "clis": [],  # empty query
            "ipad": [],
            "installed_app_names": set(),
        }
        new_md, report = inventory_sync.sync_all(self.sample_md, flaky_facts, self.methods_rows)
        self.assertIn("GRUPA 2", report["skipped_groups"])
        self.assertIn("Homebrew Formulae", report["skipped_groups"])
        self.assertIn("Homebrew Casks", report["skipped_groups"])
        self.assertIn("Native CLI", report["skipped_groups"])

        # Tables should NOT have been wiped
        self.assertIn("Amphetamine", new_md)
        self.assertIn("mas", new_md)
        self.assertIn("appcleaner", new_md)
        self.assertIn("bun", new_md)

    def test_summary_counts_match_tables(self) -> None:
        updated_summary_md = inventory_sync.recompute_summary(self.sample_md)
        # Parse numbers from ## Podsumowanie
        sum_span = inventory_sync.section_span(updated_summary_md, r"^## Podsumowanie\b")
        self.assertIsNotNone(sum_span)
        sum_text = updated_summary_md[sum_span[0]:sum_span[1]]

        # System Apple = 2 (Safari, Finder)
        self.assertIn("| 🍎 Systemowe Apple | 2 |", sum_text)
        # App Store = 4 (Amphetamine, Copilot, Notion Web Clipper, GarageBand)
        self.assertIn("| 🛍️ App Store | 4 |", sum_text)
        # App Store iPad = 0
        self.assertIn("| 📱 App Store — iPad | 0 |", sum_text)
        # Pobrane z Internetu = 2 (Chrome, UniFi)
        self.assertIn("| 🌐 Pobrane z Internetu | 2 |", sum_text)
        # Do skategoryzowania = 1 (S2M)
        self.assertIn("| 🆕 Do skategoryzowania | 1 |", sum_text)
        # Formulae (kluczowe) = 2 (mas, stale-pkg)
        self.assertIn("| 🍺 Homebrew Formulae (kluczowe) | 2 |", sum_text)
        # Formulae (biblioteki) = 2 (ca-certificates, old-dep)
        self.assertIn("| 🍺 Homebrew Formulae (biblioteki) | 2 |", sum_text)
        # Casks = 2 (appcleaner, stale-cask)
        self.assertIn("| 🍺 Homebrew Casks | 2 |", sum_text)
        # Native CLI = 3 (bun, gemini-cli, qwen-code)
        self.assertIn("| 🧰 Native CLI + npm | 3 |", sum_text)
        # RAZEM = 18
        self.assertIn("| **RAZEM** | **18** |", sum_text)

    def test_legend_rebuilt_from_config(self) -> None:
        rows = inventory_sync.legend_rows(
            self.methods_rows,
            {"Chrome", "Claude", "Word", "Excel"},
            {"appcleaner"},
            ["Amphetamine", "Copilot"],
            ["UniFi"],
            ["bun", "cursor-agent"],
        )
        self.assertTrue(len(rows) >= 4)
        new_md = inventory_sync.rebuild_legend(self.sample_md, rows)
        leg_span = inventory_sync.section_span(new_md, r"^## Legenda aktualizacji\b")
        self.assertIsNotNone(leg_span)
        leg_text = new_md[leg_span[0]:leg_span[1]]
        self.assertIn("🤖 Auto (Skrypt `update_internet_apps.sh`)", leg_text)
        self.assertIn("💼 Microsoft AutoUpdate (`msupdate`)", leg_text)
        self.assertIn("🛍️ App Store / `sudo mas upgrade`", leg_text)
        self.assertIn("🧰 Native CLI + npm (`update_npm_cli.sh`)", leg_text)
        self.assertIn("🍺 Homebrew `brew upgrade`", leg_text)

    def test_sync_all_is_idempotent(self) -> None:
        facts = {
            "mas": {
                "937984704": ("Amphetamine", "5.3"),
                "6738511300": ("Copilot", "1.0"),
                "682658836": ("GarageBand", "10.4.11"),
            },
            "formulae": {"mas", "ca-certificates"},
            "casks_nonorphan": {"appcleaner"},
            "orphans": ["stale-cask"],
            "clis": [("bun", "1.4.2"), ("cursor-agent", "2026.09.23")],
            "ipad": [("UniFi", "1057750342", "10.0"), ("S2M", "123456789", "1.0")],
            "installed_app_names": {"Chrome", "Safari", "Finder", "UniFi", "S2M"},
        }
        md_run1, rep1 = inventory_sync.sync_all(self.sample_md, facts, self.methods_rows)
        md_run2, rep2 = inventory_sync.sync_all(md_run1, facts, self.methods_rows)

        self.assertEqual(md_run1, md_run2)

    def test_minimal_template_has_golden_gate_and_ipad_section(self) -> None:
        # Test with explicit arguments
        tpl = inventory_sync.minimal_template(
            user="testuser",
            os_label="macOS 27.0 Golden Gate",
            build="26A123",
            home="/Users/testuser",
            script_dir="/Users/testuser/macOS_updates",
            today="2026-09-24",
        )
        self.assertIn("Golden Gate", tpl)
        self.assertIn("### 📱 Aplikacje iPad na Apple Silicon (App Store)", tpl)
        self.assertIn("| Nazwa | App ID | Wersja |", tpl)

        # Test with mock runner returning major 27
        class MockRun:
            def __init__(self, stdout: str) -> None:
                self.stdout = stdout
                self.returncode = 0

        def mock_runner(cmd: list[str], **kwargs) -> MockRun:
            if "-productVersion" in cmd:
                return MockRun("27.1\n")
            if "-buildVersion" in cmd:
                return MockRun("26B50\n")
            return MockRun("")

        auto_tpl = inventory_sync.minimal_template(
            user="runner_user",
            home="/Users/runner_user",
            script_dir="/tmp",
            today="2026-09-24",
            run=mock_runner,
        )
        self.assertIn("macOS 27.1 Golden Gate", auto_tpl)
        self.assertIn("Build 26B50", auto_tpl)
        self.assertIn("### 📱 Aplikacje iPad na Apple Silicon (App Store)", auto_tpl)

    def test_gather_facts_parses_mas7_ndjson(self) -> None:
        ndjson_fixture = (SCRIPT_DIR / "tests" / "fixtures" / "inventory" / "mas7_list.ndjson").read_text(encoding="utf-8")

        class MockRes:
            def __init__(self, stdout: str, returncode: int = 0) -> None:
                self.stdout = stdout
                self.returncode = returncode

        def mock_run(cmd: list[str], **kwargs) -> MockRes:
            if cmd == ["mas", "list", "--json"]:
                return MockRes(ndjson_fixture)
            return MockRes("", returncode=1)

        facts = inventory_sync.gather_facts(str(SCRIPT_DIR), "/tmp/home", run=mock_run)
        self.assertIsNotNone(facts["mas"])
        self.assertIn("409183694", facts["mas"])
        self.assertEqual(facts["mas"]["409183694"], ("Keynote", "14.0"))
        self.assertIn("409201541", facts["mas"])
        self.assertEqual(facts["mas"]["409201541"], ("Pages", "14.0"))
        self.assertIn("409203825", facts["mas"])
        self.assertEqual(facts["mas"]["409203825"], ("Numbers", "14.0"))

    def test_gather_facts_mas_unparseable_falls_back_to_text(self) -> None:
        class MockRes:
            def __init__(self, stdout: str, returncode: int = 0) -> None:
                self.stdout = stdout
                self.returncode = returncode

        def mock_run(cmd: list[str], **kwargs) -> MockRes:
            if cmd == ["mas", "list", "--json"]:
                return MockRes("not-json-content-at-all\n", returncode=0)
            if cmd == ["mas", "list"]:
                return MockRes("409183694 Keynote (14.0)\n", returncode=0)
            return MockRes("", returncode=1)

        facts = inventory_sync.gather_facts(str(SCRIPT_DIR), "/tmp/home", run=mock_run)
        self.assertIsNotNone(facts["mas"])
        self.assertIn("409183694", facts["mas"])
        self.assertEqual(facts["mas"]["409183694"], ("Keynote", "14.0"))

    def test_ipad_rows_use_bundle_name_and_remove_both_names(self) -> None:
        sample = """## GRUPA 2 — Aplikacje z App Store 🛍️

| Nazwa | App ID |
|-------|--------|
| Keynote | 409183694 |

---

## GRUPA 3 — Aplikacje pobrane z Internetu 🌐

| Nazwa | Wersja | Strona aktualizacji |
|-------|--------|---------------------|
| IPMIView | 2.20 | https://example.com |
| OtherApp | 1.0 | https://example.com |

### 🆕 Nowo wykryte aplikacje

| Nazwa | Wersja |
|-------|--------|
| TrackMan.Go.Ios | 4.6.1 |

---

## GRUPA 4 — Homebrew 🍺
"""
        facts = {
            "ipad": [
                ("TrackMan.Go.Ios", "1192720039", "4.6.1", "TrackMan Golf Pro"),
                ("IPMIView", "123456", "2.20", "Supermicro IPMIView"),
            ],
            "mas": None,
            "formulae": None,
            "casks_nonorphan": None,
            "clis": None,
        }
        res_md, report = inventory_sync.sync_all(sample, facts)
        self.assertIn("TrackMan.Go.Ios", res_md)
        self.assertIn("| TrackMan.Go.Ios | 1192720039 | 4.6.1 |", res_md)
        self.assertIn("| IPMIView | 123456 | 2.20 |", res_md)
        # Verify both names removed from Group 3 and 🆕
        self.assertNotIn("| IPMIView | 2.20 |", res_md)
        self.assertNotIn("| TrackMan.Go.Ios | 4.6.1 |", res_md)
        self.assertIn("| OtherApp | 1.0 |", res_md)

    def test_refresh_system_line(self) -> None:
        md = "# Header\n\n> **System:** macOS 26.5F71)\n> **Arch:** arm64\n"
        res = inventory_sync.refresh_system_line(md, "macOS 27.0 Golden Gate", "27A5000")
        self.assertIn("> **System:** macOS 27.0 Golden Gate (Build 27A5000)\n", res)
        self.assertNotIn("26.5F71", res)

    def test_separator_before_summary_preserved(self) -> None:
        md = self.sample_md
        self.assertIn("\n---\n\n## Podsumowanie", md)
        facts = {
            "clis": [("bun", "1.4.2")],
            "mas": None,
            "formulae": None,
            "casks_nonorphan": None,
            "ipad": None,
        }
        out, _ = inventory_sync.sync_all(md, facts, self.methods_rows)
        self.assertIn("\n---\n\n## Podsumowanie", out)

    def test_legend_filters_uninstalled_and_has_ipad_row(self) -> None:
        methods = [
            "Chrome | silent_launch",
            "Slack | silent_launch",
            "Word | msupdate",
            "Excel | msupdate",
        ]
        # Only Chrome and Word are installed; Slack and Excel are uninstalled
        installed = {"Google Chrome"}  # Note: alias of Chrome
        rows = inventory_sync.legend_rows(
            methods_rows=methods,
            installed_names=installed,
            casks=set(),
            mas_names=["Pages", "Keynote"],
            ipad_names=["WiFiman", "IPMIView"],
            cli_names=["bun"],
        )
        methods_in_legend = [r[0] for r in rows]
        apps_in_legend = {r[0]: r[1] for r in rows}

        self.assertIn("🤖 Auto (Skrypt `update_internet_apps.sh`)", methods_in_legend)
        self.assertEqual(apps_in_legend["🤖 Auto (Skrypt `update_internet_apps.sh`)"], "Chrome")
        self.assertNotIn("Slack", apps_in_legend.get("🤖 Auto (Skrypt `update_internet_apps.sh`)", ""))

        self.assertNotIn("💼 Microsoft AutoUpdate (`msupdate`)", methods_in_legend)

        # Order: Auto, MAU, App Store, iPad, CLI, Homebrew
        expected_keys = [
            "🤖 Auto (Skrypt `update_internet_apps.sh`)",
            "🛍️ App Store / `sudo mas upgrade`",
            "📱 App Store — iPad (Track 2 GUI / ręcznie)",
            "🧰 Native CLI + npm (`update_npm_cli.sh`)",
            "🍺 Homebrew `brew upgrade`",
        ]
        self.assertEqual(methods_in_legend, expected_keys)
        # Sorted names
        self.assertEqual(apps_in_legend["🛍️ App Store / `sudo mas upgrade`"], "Keynote, Pages")
        self.assertEqual(apps_in_legend["📱 App Store — iPad (Track 2 GUI / ręcznie)"], "IPMIView, WiFiman")


if __name__ == "__main__":
    unittest.main()
