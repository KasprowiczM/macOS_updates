"""Regressions for 2026-09-10 MAU failure handling and run summary extensions."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from run_summary import (
    FORMAT_VERSION,
    INVALID_VERSIONS,
    build_run_summary,
    collect_run_items,
    format_terminal_summary,
    is_valid_version,
    migrate_run_summary,
    normalize_app_key,
    read_mas_versions,
)


def run_bash(cmd: str, env: dict[str, str] | None = None, timeout: int = 15) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=full_env,
        timeout=timeout,
    )


class MauInterruptionDetectionTests(unittest.TestCase):
    def test_interruption_detected_on_update_assistant_terminated(self) -> None:
        cmd = """
        source lib/internet_app_updates.sh
        output="Update Assistant: Idle, Downloading: [MSWD2019: 55%]
Update Assistant terminated.
Something else"
        mau_output_has_interruption "$output"
        """
        res = run_bash(cmd)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_interruption_detected_on_xpc_invalidation(self) -> None:
        cmd = """
        source lib/internet_app_updates.sh
        output="XPC Connection to updater invalidated. Exiting."
        mau_output_has_interruption "$output"
        """
        res = run_bash(cmd)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_no_interruption_on_clean_output(self) -> None:
        cmd = """
        source lib/internet_app_updates.sh
        output="Update Assistant: Idle
Everything is up to date."
        mau_output_has_interruption "$output"
        """
        res = run_bash(cmd)
        self.assertEqual(res.returncode, 1, res.stderr)

    def test_mau_interruption_reason_extraction(self) -> None:
        cmd = """
        source lib/internet_app_updates.sh
        output="Downloading: 55%
Update Assistant terminated."
        reason=$(mau_interruption_reason "$output")
        echo "REASON:$reason"
        """
        res = run_bash(cmd)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("REASON:Update Assistant terminated", res.stdout)


class MauScopedInstallFailureTests(unittest.TestCase):
    def test_exit_0_with_interruption_returns_soft_exit_10(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            mock_msupdate = fake_bin / "msupdate"
            mock_msupdate.write_text(
                "#!/bin/sh\n"
                "echo 'Update Assistant: Downloading 55%'\n"
                "echo 'Update Assistant terminated.'\n"
                "exit 0\n",
                encoding="utf-8",
            )
            mock_msupdate.chmod(0o755)

            cmd = f"""
            export PATH="{fake_bin}:$PATH"
            export MAC_UPDATE_SESSION_DIR="{tmp_path}"
            export MAC_UPDATE_SOFT_EXIT=10
            source lib/proc.sh
            source lib/internet_app_updates.sh
            mau_run_scoped_install "MSWD2019"
            echo "RC:$?"
            echo "INTERRUPTED:$MAU_INSTALL_INTERRUPTED"
            echo "REASON:$MAU_INSTALL_INTERRUPT_REASON"
            """
            res = run_bash(cmd)
            self.assertIn("RC:10", res.stdout)
            self.assertIn("INTERRUPTED:1", res.stdout)
            self.assertIn("REASON:Update Assistant terminated", res.stdout)


class MauActiveProcessAndListingTests(unittest.TestCase):
    def test_mau_active_processes_when_none_running(self) -> None:
        cmd = """
        source lib/internet_app_updates.sh
        if [ -z "$(mau_active_install_processes)" ]; then
            echo "IDLE"
        else
            echo "BUSY"
        fi
        """
        res = run_bash(cmd)
        self.assertEqual(res.returncode, 0)
        self.assertIn("IDLE", res.stdout)

    def test_unknown_written_to_pending_mau_on_listing_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            mock_msupdate = fake_bin / "msupdate"
            # msupdate --list fails
            mock_msupdate.write_text(
                "#!/bin/sh\n"
                "exit 1\n",
                encoding="utf-8",
            )
            mock_msupdate.chmod(0o755)

            fake_apps = tmp_path / "Applications"
            fake_apps.mkdir()
            (fake_apps / "Microsoft Word.app").mkdir()

            fake_prefs = tmp_path / "prefs.plist"
            fake_prefs.write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<plist version=\"1.0\"><dict></dict></plist>\n", encoding="utf-8")

            cmd = f"""
            export PATH="{fake_bin}:$PATH"
            export MAC_UPDATE_MAU_CLI="{mock_msupdate}"
            export MAC_UPDATE_APPS_DIR="{fake_apps}"
            export MAC_UPDATE_MAU_PREFS_FILE="{fake_prefs}"
            export MAC_UPDATE_SESSION_DIR="{tmp_path}"
            export MAC_UPDATE_NONINTERACTIVE=1
            source lib/ui.sh
            source lib/proc.sh
            source lib/internet_i18n.sh
            source lib/internet_app_updates.sh
            iu_microsoft_365
            """
            res = run_bash(cmd)
            pending_file = tmp_path / "pending_mau"
            self.assertTrue(pending_file.exists())
            self.assertEqual(pending_file.read_text(encoding="utf-8").strip(), "unknown")


class MauGuiInteractiveGateTests(unittest.TestCase):
    def test_gui_launch_is_gated_by_interactive_and_terminal(self) -> None:
        lib = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(encoding="utf-8")
        self.assertIn('[ "${MAC_UPDATE_NONINTERACTIVE:-0}" != "1" ] && [ -t 0 ]', lib)
        self.assertIn('open -a "$MAU_APP"', lib)


class MauBehavioralRequirementsTests(unittest.TestCase):
    def test_mau_empty_queue_is_not_proven_by_arbitrary_zero_exit(self) -> None:
        """Requirement 1: Exit 0 with empty output or interruption text must NOT be treated as empty queue."""
        # 1. Semantic listing check in bash
        cmd_valid = """
        source lib/internet_app_updates.sh
        mau_is_valid_listing 0 "" && echo "VALID_EMPTY" || echo "INVALID_EMPTY"
        mau_is_valid_listing 0 "Update Assistant terminated." && echo "VALID_INTERRUPT" || echo "INVALID_INTERRUPT"
        """
        res_valid = run_bash(cmd_valid)
        self.assertIn("INVALID_EMPTY", res_valid.stdout)
        self.assertIn("INVALID_INTERRUPT", res_valid.stdout)

        # 2. iu_microsoft_365 execution with exit 0 but empty output -> pending_mau is unknown
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            mock_msupdate = fake_bin / "msupdate"
            mock_msupdate.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            mock_msupdate.chmod(0o755)

            fake_apps = tmp_path / "Applications"
            fake_apps.mkdir()
            (fake_apps / "Microsoft Word.app").mkdir()

            fake_prefs = tmp_path / "prefs.plist"
            fake_prefs.write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<plist version=\"1.0\"><dict></dict></plist>\n", encoding="utf-8")

            cmd = f"""
            export PATH="{fake_bin}:$PATH"
            export MAC_UPDATE_MAU_CLI="{mock_msupdate}"
            export MAC_UPDATE_APPS_DIR="{fake_apps}"
            export MAC_UPDATE_MAU_PREFS_FILE="{fake_prefs}"
            export MAC_UPDATE_SESSION_DIR="{tmp_path}"
            export MAC_UPDATE_NONINTERACTIVE=1
            source lib/ui.sh
            source lib/proc.sh
            source lib/internet_i18n.sh
            source lib/internet_app_updates.sh
            iu_microsoft_365
            """
            res = run_bash(cmd)
            pending_file = tmp_path / "pending_mau"
            self.assertTrue(pending_file.exists())
            self.assertEqual(pending_file.read_text(encoding="utf-8").strip(), "unknown")
            self.assertFalse((tmp_path / "mau_remaining.txt").exists())

            # 3. collect_run_items check: pending_mau=unknown yields unconfirmed item, NOT 0 pending
            items = collect_run_items(tmp_path)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["status"], "unconfirmed")
            self.assertEqual(items[0]["id"], "MAU")

    def test_mau_valid_empty_queue_sentinel(self) -> None:
        """Requirement 2: 'No updates available' sentinel proves empty queue (0 pending, empty mau_remaining.txt)."""
        cmd_valid = """
        source lib/internet_app_updates.sh
        mau_is_valid_listing 0 "No updates available" && echo "VALID_SENTINEL" || echo "INVALID_SENTINEL"
        mau_has_no_updates_sentinel "No updates available" && echo "HAS_SENTINEL" || echo "NO_SENTINEL"
        """
        res_valid = run_bash(cmd_valid)
        self.assertIn("VALID_SENTINEL", res_valid.stdout)
        self.assertIn("HAS_SENTINEL", res_valid.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            mock_msupdate = fake_bin / "msupdate"
            mock_msupdate.write_text("#!/bin/sh\necho 'No updates available'\nexit 0\n", encoding="utf-8")
            mock_msupdate.chmod(0o755)

            fake_apps = tmp_path / "Applications"
            fake_apps.mkdir()
            (fake_apps / "Microsoft Word.app").mkdir()

            fake_prefs = tmp_path / "prefs.plist"
            fake_prefs.write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<plist version=\"1.0\"><dict></dict></plist>\n", encoding="utf-8")

            cmd = f"""
            export PATH="{fake_bin}:$PATH"
            export MAC_UPDATE_MAU_CLI="{mock_msupdate}"
            export MAC_UPDATE_APPS_DIR="{fake_apps}"
            export MAC_UPDATE_MAU_PREFS_FILE="{fake_prefs}"
            export MAC_UPDATE_SESSION_DIR="{tmp_path}"
            export MAC_UPDATE_NONINTERACTIVE=1
            source lib/ui.sh
            source lib/proc.sh
            source lib/internet_i18n.sh
            source lib/internet_app_updates.sh
            iu_microsoft_365
            """
            res = run_bash(cmd)
            pending_file = tmp_path / "pending_mau"
            self.assertTrue(pending_file.exists())
            self.assertEqual(pending_file.read_text(encoding="utf-8").strip(), "0")

            remaining_file = tmp_path / "mau_remaining.txt"
            self.assertTrue(remaining_file.exists())
            self.assertEqual(remaining_file.stat().st_size, 0)

            items = collect_run_items(tmp_path)
            self.assertEqual(items, [])

    def test_mau_retry_limited_to_intersection_of_fresh_and_permitted_ids(self) -> None:
        """Requirement 3: Retry candidates are strictly limited to the intersection of fresh pending and permitted IDs."""
        cmd_intersect = """
        source lib/internet_app_updates.sh
        res=$(mau_intersect_ids "MSWD2019 XCEL2019 TEAMS21 UNPERMITTED" "MSWD2019 PPT32019")
        echo "INTERSECT:$res"
        """
        res_int = run_bash(cmd_intersect)
        self.assertIn("INTERSECT:MSWD2019", res_int.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            mock_msupdate = fake_bin / "msupdate"
            calls_log = tmp_path / "calls.log"

            mock_script = f"""#!/bin/sh
echo "$@" >> "{calls_log}"
if [ "$1" = "--list" ]; then
    count=$(grep -c -- "--list" "{calls_log}")
    if [ "$count" -eq 1 ]; then
        echo "MSWD2019  Microsoft Word Update 16.90 (240901)"
        echo "XCEL2019  Microsoft Excel Update 16.90 (240901)"
    elif [ "$count" -eq 2 ]; then
        echo "MSWD2019  Microsoft Word Update 16.90 (240901)"
        echo "TEAMS21   Microsoft Teams Update"
        echo "UNPERM    Unpermitted App Update"
    else
        echo "No updates available"
    fi
    exit 0
elif [ "$1" = "--install" ]; then
    exit 0
fi
exit 0
"""
            mock_msupdate.write_text(mock_script, encoding="utf-8")
            mock_msupdate.chmod(0o755)

            fake_apps = tmp_path / "Applications"
            fake_apps.mkdir()
            (fake_apps / "Microsoft Word.app").mkdir()
            (fake_apps / "Microsoft Excel.app").mkdir()

            fake_prefs = tmp_path / "prefs.plist"
            fake_prefs.write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<plist version=\"1.0\"><dict></dict></plist>\n", encoding="utf-8")

            cmd = f"""
            export PATH="{fake_bin}:$PATH"
            export MAC_UPDATE_MAU_CLI="{mock_msupdate}"
            export MAC_UPDATE_APPS_DIR="{fake_apps}"
            export MAC_UPDATE_MAU_PREFS_FILE="{fake_prefs}"
            export MAC_UPDATE_SESSION_DIR="{tmp_path}"
            export MAC_UPDATE_NONINTERACTIVE=1
            source lib/ui.sh
            source lib/proc.sh
            source lib/internet_i18n.sh
            source lib/internet_app_updates.sh
            mau_installed_short_version() {{ echo "16.89"; }}
            iu_microsoft_365
            """
            res = run_bash(cmd)
            self.assertTrue(calls_log.exists())
            calls = calls_log.read_text(encoding="utf-8").splitlines()
            install_calls = [c for c in calls if "--install" in c]
            self.assertGreaterEqual(len(install_calls), 2)
            retry_call = install_calls[1]
            self.assertIn("MSWD2019", retry_call)
            self.assertNotIn("TEAMS21", retry_call)
            self.assertNotIn("UNPERM", retry_call)
            self.assertNotIn("XCEL2019", retry_call)

    def test_mau_retry_skipped_if_installer_processes_active(self) -> None:
        """Requirement 4: When an installer process is still active, retry is skipped."""
        cmd_proc = """
        source lib/internet_app_updates.sh
        export MAC_UPDATE_MOCK_ACTIVE_PROCESSES="99999"
        res=$(mau_active_install_processes)
        echo "ACTIVE:$res"
        """
        res_proc = run_bash(cmd_proc)
        self.assertIn("ACTIVE:99999", res_proc.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            mock_msupdate = fake_bin / "msupdate"
            calls_log = tmp_path / "calls.log"

            mock_script = f"""#!/bin/sh
echo "$@" >> "{calls_log}"
if [ "$1" = "--list" ]; then
    echo "MSWD2019  Microsoft Word Update 16.90 (240901)"
    exit 0
elif [ "$1" = "--install" ]; then
    exit 0
fi
exit 0
"""
            mock_msupdate.write_text(mock_script, encoding="utf-8")
            mock_msupdate.chmod(0o755)

            fake_apps = tmp_path / "Applications"
            fake_apps.mkdir()
            (fake_apps / "Microsoft Word.app").mkdir()

            fake_prefs = tmp_path / "prefs.plist"
            fake_prefs.write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<plist version=\"1.0\"><dict></dict></plist>\n", encoding="utf-8")

            cmd = f"""
            export PATH="{fake_bin}:$PATH"
            export MAC_UPDATE_MAU_CLI="{mock_msupdate}"
            export MAC_UPDATE_APPS_DIR="{fake_apps}"
            export MAC_UPDATE_MAU_PREFS_FILE="{fake_prefs}"
            export MAC_UPDATE_SESSION_DIR="{tmp_path}"
            export MAC_UPDATE_NONINTERACTIVE=1
            export MAC_UPDATE_MOCK_ACTIVE_PROCESSES="12345"
            export MAC_UPDATE_MAU_IDLE_TIMEOUT=0
            source lib/ui.sh
            source lib/proc.sh
            source lib/internet_i18n.sh
            source lib/internet_app_updates.sh
            mau_installed_short_version() {{ echo "16.89"; }}
            iu_microsoft_365
            """
            res = run_bash(cmd)
            self.assertIn("Active Microsoft installer process detected; skipping retry", res.stdout + res.stderr)
            calls = calls_log.read_text(encoding="utf-8").splitlines()
            install_calls = [c for c in calls if "--install" in c]
            self.assertEqual(len(install_calls), 1)

    def test_mau_install_success_requires_version_change_or_clean_listing(self) -> None:
        """Requirement 5: Interrupted installer without version changes is not marked updated."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            mock_msupdate = fake_bin / "msupdate"
            marker = tmp_path / ".mau_test_listed"

            mock_script = f"""#!/bin/sh
if [ "$1" = "--list" ]; then
    if [ ! -f "{marker}" ]; then
        touch "{marker}"
        echo "MSWD2019  Microsoft Word Update 16.90 (240901)"
    else
        echo "No updates available"
    fi
    exit 0
elif [ "$1" = "--install" ]; then
    echo "Update Assistant terminated."
    exit 0
fi
exit 0
"""
            mock_msupdate.write_text(mock_script, encoding="utf-8")
            mock_msupdate.chmod(0o755)

            fake_apps = tmp_path / "Applications"
            fake_apps.mkdir()
            (fake_apps / "Microsoft Word.app").mkdir()

            fake_prefs = tmp_path / "prefs.plist"
            fake_prefs.write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<plist version=\"1.0\"><dict></dict></plist>\n", encoding="utf-8")

            cmd = f"""
            export PATH="{fake_bin}:$PATH"
            export MAC_UPDATE_MAU_CLI="{mock_msupdate}"
            export MAC_UPDATE_APPS_DIR="{fake_apps}"
            export MAC_UPDATE_MAU_PREFS_FILE="{fake_prefs}"
            export MAC_UPDATE_SESSION_DIR="{tmp_path}"
            export MAC_UPDATE_NONINTERACTIVE=1
            export L_INTERNET_STATUS_CHECK_MAU="check MAU"
            source lib/ui.sh
            source lib/proc.sh
            source lib/internet_i18n.sh
            source lib/internet_app_updates.sh
            mau_installed_short_version() {{ echo "16.89"; }}
            iu_microsoft_365
            echo "STATUS:$STATUS_MICROSOFT"
            """
            res = run_bash(cmd)
            self.assertIn("no version changes observed", res.stdout + res.stderr)
            self.assertIn("STATUS:check MAU", res.stdout)


class RunSummaryBehavioralRequirementsTests(unittest.TestCase):
    def test_run_summary_missing_before_snapshot_not_labeled_newly_installed(self) -> None:
        """Requirement 6: Missing before snapshots must not confirm changes or label items newly installed."""
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp)
            (sdir / "mas_after.txt").write_text(" 310633997  WhatsApp (26.35.74)\n", encoding="utf-8")
            (sdir / "brew_formulae_after.txt").write_text("nss 3.129\n", encoding="utf-8")
            (sdir / "brew_casks_after.txt").write_text("stripe 1.50.11\n", encoding="utf-8")
            (sdir / "npm_cli_after.txt").write_text("claude-code|@anthropic-ai/claude-code|2.1.267|claude|/bin/claude\n", encoding="utf-8")
            (sdir / "internet_after.txt").write_text("Visual Studio Code|1.97.0\n", encoding="utf-8")

            items = collect_run_items(sdir)
            self.assertEqual(items, [])
            updated = [it for it in items if it.get("status") == "updated"]
            self.assertEqual(len(updated), 0)

    def test_run_summary_invalid_versions_rejected(self) -> None:
        """Requirement 7: Unknown, blank, or placeholder versions cannot create success."""
        for inv in INVALID_VERSIONS:
            self.assertFalse(is_valid_version(inv), f"Expected {inv!r} to be invalid")

        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp)
            (sdir / "mas_before.txt").write_text(" 310633997  WhatsApp (?)\n", encoding="utf-8")
            (sdir / "mas_after.txt").write_text(" 310633997  WhatsApp (26.35.74)\n", encoding="utf-8")

            (sdir / "brew_formulae_before.txt").write_text("nss 3.128\n", encoding="utf-8")
            (sdir / "brew_formulae_after.txt").write_text("nss unknown\n", encoding="utf-8")

            (sdir / "brew_casks_before.txt").write_text("cask1 not installed\n", encoding="utf-8")
            (sdir / "brew_casks_after.txt").write_text("cask1 none\n", encoding="utf-8")

            items = collect_run_items(sdir)
            updated = [it for it in items if it.get("status") == "updated"]
            self.assertEqual(len(updated), 0)

    def test_run_summary_deduplicates_updated_apps_across_sources(self) -> None:
        """Requirement 8: Applications updated across multiple subsystems are deduplicated and counted once."""
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp)
            (sdir / "mas_before.txt").write_text(" 310633997  WhatsApp (26.35.72)\n", encoding="utf-8")
            (sdir / "mas_after.txt").write_text(" 310633997  WhatsApp (26.35.74)\n", encoding="utf-8")

            (sdir / "brew_casks_before.txt").write_text("whatsapp 26.35.72\n", encoding="utf-8")
            (sdir / "brew_casks_after.txt").write_text("whatsapp 26.35.74\n", encoding="utf-8")

            (sdir / "internet_before.txt").write_text("WhatsApp.app|26.35.72\n", encoding="utf-8")
            (sdir / "internet_after.txt").write_text("WhatsApp.app|26.35.74\n", encoding="utf-8")

            items = collect_run_items(sdir)
            updated = [it for it in items if it.get("status") == "updated"]
            self.assertEqual(len(updated), 1)
            self.assertEqual(normalize_app_key(updated[0]["name"]), "whatsapp")


class FixtureRun20260910RegressionTests(unittest.TestCase):
    def test_fixture_matches_7_updates_5_pending_and_9_inventory_changes(self) -> None:
        """Verify the exact metrics from the 2026-09-10 21:54:22 run:
        - WhatsApp (App Store: 26.35.72 -> 26.35.74)
        - 3 Homebrew Formulae: nss (3.128 -> 3.129), uv (0.12.11 -> 0.12.12), stripe (1.50.10 -> 1.50.11)
        - 0 Homebrew Casks
        - 3 Native CLI + npm: claude-code (2.1.266 -> 2.1.267), codex-cli (0.153.4 -> 0.154.0), agy-cli (1.1.28 -> 1.2.0)
        - 5 pending Office apps: PPT32019, ONMC2019, XCEL2019, OPIM2019, MSWD2019.
        - 7 observed package changes, 9 inventory version fields changed.
        """
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp)

            # 1. App Store: WhatsApp 26.35.72 -> 26.35.74
            (sdir / "mas_before.txt").write_text(
                " 310633997  WhatsApp               (26.35.72)\n", encoding="utf-8"
            )
            (sdir / "mas_after.txt").write_text(
                " 310633997  WhatsApp               (26.35.74)\n", encoding="utf-8"
            )

            # 2. Brew Formulae: nss 3.128 -> 3.129, uv 0.12.11 -> 0.12.12, stripe 1.50.10 -> 1.50.11
            (sdir / "brew_formulae_before.txt").write_text(
                "libuv 1.52.1\nnss 3.128\nopenssl@3 3.6.4\nstripe 1.50.10\nuv 0.12.11\n",
                encoding="utf-8",
            )
            (sdir / "brew_formulae_after.txt").write_text(
                "libuv 1.52.1\nnss 3.129\nopenssl@3 3.6.4\nstripe 1.50.11\nuv 0.12.12\n",
                encoding="utf-8",
            )

            # 3. Brew Casks: 0 updates
            (sdir / "brew_casks_before.txt").write_text("", encoding="utf-8")
            (sdir / "brew_casks_after.txt").write_text("", encoding="utf-8")

            # 4. Native CLI + npm: claude-code, codex-cli, agy-cli
            (sdir / "npm_cli_before.txt").write_text(
                "claude-code|@anthropic-ai/claude-code|2.1.266|claude|/Users/testuser/.local/bin/claude\n"
                "codex-cli|@openai/codex|0.153.4|codex|/Users/testuser/.local/bin/codex\n"
                "agy-cli|agy|1.1.28|agy|/Users/testuser/.local/bin/agy\n",
                encoding="utf-8",
            )
            (sdir / "npm_cli_after.txt").write_text(
                "claude-code|@anthropic-ai/claude-code|2.1.267|claude|/Users/testuser/.local/bin/claude\n"
                "codex-cli|@openai/codex|0.154.0|codex|/Users/testuser/.local/bin/codex\n"
                "agy-cli|agy|1.2.0|agy|/Users/testuser/.local/bin/agy\n",
                encoding="utf-8",
            )

            # 5. MAU: 5 pending apps
            (sdir / "mau_remaining.txt").write_text(
                "PPT32019 ONMC2019 XCEL2019 OPIM2019 MSWD2019\n", encoding="utf-8"
            )
            (sdir / "mau_interrupt_reason.txt").write_text(
                "Update Assistant terminated.\n", encoding="utf-8"
            )
            (sdir / "pending_mau").write_text("5\n", encoding="utf-8")

            step_results = {
                "prescan": "OK",
                "appstore": "OK completed",
                "npmcli": "OK completed",
                "brew": "OK completed",
                "internet": "Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane)",
                "postupdate": "OK completed",
                "system": "OK completed",
            }

            items = collect_run_items(sdir, step_results=step_results, inventory_updated_count=9)

            updated_items = [it for it in items if it["status"] == "updated"]
            self.assertEqual(len(updated_items), 7)
            names = {it["name"] for it in updated_items}
            self.assertEqual(
                names,
                {"WhatsApp", "nss", "uv", "stripe", "claude-code", "codex-cli", "agy-cli"},
            )

            pending_items = [it for it in items if it["status"] == "pending"]
            self.assertEqual(len(pending_items), 5)
            pending_names = {it["name"] for it in pending_items}
            self.assertTrue(any("PowerPoint" in n for n in pending_names))
            self.assertTrue(any("OneNote" in n for n in pending_names))
            self.assertTrue(any("Excel" in n for n in pending_names))
            self.assertTrue(any("Outlook" in n for n in pending_names))
            self.assertTrue(any("Word" in n for n in pending_names))

            summary = build_run_summary(
                start_time=1725998061,
                end_time=1725998369,
                overall_exit=0,
                degraded=1,
                blocking_exit=0,
                step_results=step_results,
                counts={
                    "appstore_upgraded": 1,
                    "brew_formulae_upgraded": 3,
                    "brew_casks_upgraded": 0,
                    "brew_new_packages": 0,
                    "native_cli_npm_changed": 3,
                    "internet_app_versions_changed": 0,
                    "inventory_version_fields_changed": 9,
                    "observed_package_changes": len(updated_items),
                    "pending_after_run_appstore": 0,
                    "pending_after_run_brew_formulae": 0,
                    "pending_after_run_brew_casks": 0,
                    "pending_after_run_mau": 5,
                },
                items=items,
            )

            self.assertEqual(summary["format_version"], 3)
            self.assertEqual(summary["counts"]["observed_package_changes"], 7)
            self.assertEqual(summary["counts"]["inventory_version_fields_changed"], 9)
            self.assertNotEqual(
                summary["counts"]["observed_package_changes"],
                summary["counts"]["inventory_version_fields_changed"],
            )

            # Terminal formatting checks
            term = format_terminal_summary(summary, lang="pl")
            self.assertIn("Zaktualizowano:", term)
            self.assertIn("WhatsApp (appstore): 26.35.72 -> 26.35.74", term)
            self.assertIn("nss (brew_formula): 3.128 -> 3.129", term)
            self.assertIn("uv (brew_formula): 0.12.11 -> 0.12.12", term)
            self.assertIn("stripe (brew_formula): 1.50.10 -> 1.50.11", term)
            self.assertIn("claude-code (npm_cli): 2.1.266 -> 2.1.267", term)
            self.assertIn("codex-cli (npm_cli): 0.153.4 -> 0.154.0", term)
            self.assertIn("agy-cli (npm_cli): 1.1.28 -> 1.2.0", term)
            self.assertIn("Nadal oczekuje / niepowodzenie:", term)
            self.assertIn("Microsoft Word (MSWD2019) — Update Assistant terminated.", term)
            self.assertIn("Zmieniono pól wersji w inventory: 9", term)


if __name__ == "__main__":
    unittest.main()
