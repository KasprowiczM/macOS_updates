from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_SYNC_DIR = REPO_ROOT / "dev_sync"
sys.path.insert(0, str(DEV_SYNC_DIR))

from dev_sync_core import (  # noqa: E402
    DevSyncConfig,
    DevSyncError,
    Logger,
    RCloneProvider,
    RunOptions,
    copy_relpaths,
    path_matches_pattern,
    read_manifest,
    safe_relpath,
    should_include_candidate,
    should_keep_path,
    write_json,
)
from dev_sync_prune_excluded import quarantine_from_plan  # noqa: E402


class NullLogger:
    def log(self, message: str, always_stdout: bool = True) -> None:
        pass

    def verbose(self, message: str) -> None:
        pass


class DevSyncPathSafetyTests(unittest.TestCase):
    def test_safe_relpath_rejects_escape_paths(self) -> None:
        bad_paths = [
            "../outside",
            "nested/../../outside",
            "/tmp/outside",
            "C:/outside",
            "nested/\noutside",
            "",
            ".",
        ]
        for bad_path in bad_paths:
            with self.subTest(path=bad_path):
                with self.assertRaises(DevSyncError):
                    safe_relpath(bad_path)

    def test_safe_relpath_keeps_normal_project_paths(self) -> None:
        self.assertEqual(safe_relpath("./.env.local"), ".env.local")
        self.assertEqual(safe_relpath("dir/private.txt"), "dir/private.txt")

    def test_read_manifest_rejects_unsafe_relpaths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev_sync_manifest.json").write_text(
                json.dumps({"format": 1, "files": ["../outside"]}),
                encoding="utf-8",
            )
            with self.assertRaises(DevSyncError):
                read_manifest(root)

    def test_quarantine_plan_rebuilds_source_from_safe_relpath(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "provider"
            base.mkdir()
            plan = {
                "provider_root": str(base),
                "entries": [
                    {
                        "path": str(base / "safe.txt"),
                        "relpath": "../outside.txt",
                    }
                ],
            }
            with self.assertRaises(DevSyncError):
                quarantine_from_plan(plan, base, base / "dev_sync_quarantine", NullLogger())

    def test_transactional_copy_rolls_back_on_failed_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            dest = root / "dest"
            source.mkdir()
            dest.mkdir()
            (source / "first.txt").write_text("new-first", encoding="utf-8")
            (source / "second.txt").write_text("new-second", encoding="utf-8")
            (dest / "first.txt").write_text("old-first", encoding="utf-8")
            (dest / "second.txt").write_text("old-second", encoding="utf-8")

            real_replace = os.replace

            def fail_incoming_swap(src, target):
                if Path(target) == dest / "second.txt" and "incoming" in Path(src).parts:
                    raise OSError("simulated swap failure")
                return real_replace(src, target)

            with mock.patch("dev_sync_core.os.replace", side_effect=fail_incoming_swap):
                with self.assertRaises(OSError):
                    copy_relpaths(
                        source,
                        dest,
                        ["first.txt", "second.txt"],
                        NullLogger(),
                        RunOptions(),
                    )

            self.assertEqual((dest / "first.txt").read_text(encoding="utf-8"), "old-first")
            self.assertEqual((dest / "second.txt").read_text(encoding="utf-8"), "old-second")

    def test_private_overlay_logs_use_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logger = Logger(root, "permission-test", RunOptions())
            try:
                logger.log("safe")
                self.assertEqual(logger.log_dir.stat().st_mode & 0o777, 0o700)
                self.assertEqual(logger.log_path.stat().st_mode & 0o777, 0o600)
            finally:
                logger.close()

    def test_write_json_is_atomic_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private.json"
            path.write_text('{"old": true}', encoding="utf-8")
            path.chmod(0o644)
            write_json(path, {"new": True})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"new": True})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class DevSyncMatchingTests(unittest.TestCase):
    """Behavioral coverage for the include/exclude matching engine and the
    rclone dry-run plan (previously only path-safety was exercised)."""

    def test_hard_exclude_cannot_be_overridden(self) -> None:
        # .git and the manifest must never sync, even if a user lists them in
        # include_always — HARD_EXCLUDE_PATTERNS wins over everything else.
        self.assertFalse(should_keep_path(".git/config", [], [".git/"]))
        self.assertFalse(
            should_keep_path(".dev_sync_manifest.json", [], [".dev_sync_manifest.json"])
        )

    def test_include_always_overrides_plain_exclude(self) -> None:
        self.assertTrue(should_keep_path("secret.key", ["*.key"], ["secret.key"]))

    def test_plain_exclude_and_default_keep(self) -> None:
        self.assertFalse(should_keep_path("debug.log", ["*.log"], []))
        self.assertTrue(should_keep_path("src/main.py", ["*.log"], []))

    def test_path_matches_pattern_directory_and_glob(self) -> None:
        self.assertTrue(path_matches_pattern("node_modules/foo/bar.js", "node_modules/"))
        self.assertTrue(path_matches_pattern("src/node_modules/x.js", "node_modules/"))
        self.assertTrue(path_matches_pattern("dev_sync_logs/x.log", "dev_sync_logs/"))
        self.assertTrue(path_matches_pattern("a/b/.DS_Store", ".DS_Store"))
        self.assertTrue(path_matches_pattern("logs/run.log", "*.log"))
        self.assertFalse(path_matches_pattern("src/main.py", "*.log"))
        self.assertFalse(path_matches_pattern("src/main.py", "node_modules/"))

    def test_should_include_candidate_with_default_config(self) -> None:
        config = DevSyncConfig(project_name="proj")
        keep = ["src/app.py", ".env.local", "APPLICATIONS.md"]
        drop = [".DS_Store", "node_modules/pkg/index.js", ".git/config", "debug.log"]
        for rel in keep:
            with self.subTest(keep=rel):
                self.assertTrue(should_include_candidate(rel, config))
        for rel in drop:
            with self.subTest(drop=rel):
                self.assertFalse(should_include_candidate(rel, config))

    def test_rclone_sync_to_dry_run_plans_without_mutating(self) -> None:
        # dry-run must return the planned (sorted, de-duplicated) relpaths and
        # must NOT exec rclone — proven here by the call succeeding with no
        # rclone binary present.
        config = DevSyncConfig(
            project_name="proj",
            provider="rclone",
            rclone_remote="remote",
            rclone_remote_path="base",
        )
        provider = RCloneProvider(config)
        files, transport = provider.sync_to(
            ["b.txt", "a.txt", "a.txt"], Path("/tmp"), dry_run=True
        )
        self.assertEqual(transport, "rclone")
        self.assertEqual(files, ["a.txt", "b.txt"])


class StaticShellSafetyTests(unittest.TestCase):
    def read_script(self, name: str) -> str:
        return (REPO_ROOT / name).read_text(encoding="utf-8")

    def test_softwareupdate_install_uses_restart_flag(self) -> None:
        text = self.read_script("update_system.sh")
        self.assertNotIn("softwareupdate -ia --verbose", text)
        self.assertIn("softwareupdate -ia -R --verbose", text)

    def test_update_all_uses_secure_tempdir(self) -> None:
        text = self.read_script("update_all.sh")
        self.assertIn("mktemp -d", text)
        self.assertNotIn("/tmp/mac_update_$(date", text)

    def test_downloaded_dmg_names_are_not_pid_predictable(self) -> None:
        text = self.read_script("update_internet_apps.sh")
        self.assertNotIn("_$$.dmg", text)
        self.assertIn("hdiutil verify", text)
        self.assertIn("spctl --assess", text)

    def test_node_bootstrap_verifies_checksum(self) -> None:
        text = self.read_script("update_npm_cli.sh")
        self.assertIn("SHASUMS256.txt", text)
        self.assertIn("shasum -a 256 -c", text)

    def test_npm_cli_uses_tmpdir_env_for_mktemp(self) -> None:
        """update_npm_cli.sh must NOT hardcode /tmp/mac_update_*; use ${TMPDIR:-/tmp}.

        Hardcoding /tmp ignores the user's TMPDIR (e.g. macOS per-user temp under
        /var/folders/...) and can collide with other users on shared boxes.
        """
        text = self.read_script("update_npm_cli.sh")
        self.assertNotIn('"/tmp/mac_update_', text)
        # Spot-check that the new pattern is present
        self.assertIn('${TMPDIR:-/tmp}/mac_update_', text)

    def test_orchestrators_set_pipefail(self) -> None:
        """All update_*.sh orchestrator scripts must enable pipefail.

        Without pipefail, `cmd1 | cmd2` returns cmd2's status, hiding upstream
        failures (e.g. brew list | grep) and producing silently-bad results.
        """
        orchestrators = [
            "update_all.sh",
            "update_appstore.sh",
            "update_brew.sh",
            "update_internet_apps.sh",
            "update_npm_cli.sh",
            "update_system.sh",
        ]
        for name in orchestrators:
            with self.subTest(script=name):
                text = self.read_script(name)
                self.assertIn("set -o pipefail", text)

    def test_update_all_persists_run_log(self) -> None:
        """update_all.sh must tee output to a persistent log under logs/.

        Without on-disk logs, post-mortem on failed runs is impossible because
        the temp session dir is wiped by the EXIT trap.
        """
        text = self.read_script("update_all.sh")
        self.assertIn('LOGS_DIR="$SCRIPT_DIR/logs"', text)
        self.assertIn("tee -a", text)
        self.assertIn("update_all_", text)

    def test_update_all_renders_multiline_step_list(self) -> None:
        text = self.read_script("update_all.sh")
        self.assertIn('printf "%b\\n" "$L_UPDATE_ALL_STEPS"', text)
        self.assertIn("sed 's/^/    /'", text)

    def test_update_all_dry_run_reports_every_step_as_skipped(self) -> None:
        text = self.read_script("update_all.sh")
        npm_step = text[text.index("# STEP 2: Native CLI & npm update"):]
        self.assertIn('RESULT_NPMCLI="[DRY-RUN] skipped"', npm_step)
        self.assertIn("DRY-RUN: no applications, inventory, or history files were changed.", text)

    def test_appstore_diag_captured_on_failure(self) -> None:
        """update_appstore.sh must persist diagnostics on TRACK 1 / TRACK 2 failure.

        The recurring App Store TRACK-2 failures had no diagnostic context —
        appstore_diag.txt now captures sudo mas upgrade output and AS_RESULT.
        """
        text = self.read_script("update_appstore.sh")
        self.assertIn("appstore_diag.txt", text)
        self.assertIn("MAS_TOR1_OUT", text)


    def test_bun_bootstrap_verifies_checksum(self) -> None:
        text = self.read_script("update_npm_cli.sh")
        self.assertIn("SHASUMS256.txt", text)
        self.assertIn("install_bun_tarball", text)
        self.assertIn("config/bun_version.txt", text)

    def test_internet_apps_config_exists(self) -> None:
        cfg = REPO_ROOT / "config" / "internet_apps.txt"
        self.assertTrue(cfg.is_file(), "config/internet_apps.txt must exist")
        lines = [
            ln.split("#", 1)[0].strip()
            for ln in cfg.read_text(encoding="utf-8").splitlines()
            if ln.split("#", 1)[0].strip()
        ]
        self.assertGreater(len(lines), 10)

    def test_lib_internet_apps_sourced_by_orchestrators(self) -> None:
        for name in ("update_all.sh", "update_internet_apps.sh"):
            text = self.read_script(name)
            self.assertIn("lib/internet_apps.sh", text)

    def test_child_scripts_support_dry_run(self) -> None:
        for name in (
            "update_system.sh",
            "update_appstore.sh",
            "update_brew.sh",
            "update_npm_cli.sh",
            "update_internet_apps.sh",
        ):
            with self.subTest(script=name):
                text = self.read_script(name)
                self.assertIn("MAC_UPDATE_DRY_RUN", text)

    def test_migration_setup_loads_internet_apps_config(self) -> None:
        text = self.read_script("migration_setup.sh")
        self.assertIn("config/internet_apps.txt", text)
        self.assertNotIn("'ChatGPT Atlas',", text)

    def test_appstore_mas_upgrade_uses_sudo(self) -> None:
        text = self.read_script("update_appstore.sh")
        self.assertIn("sudo -v", text)
        self.assertIn("sudo -n env MAS_NO_AUTO_INDEX=1 mas upgrade", text)

    def test_appstore_dry_run_exits_before_mutations(self) -> None:
        text = self.read_script("update_appstore.sh")
        dry_run_exit = text.index('print_info "[DRY-RUN] Would run: sudo mas upgrade"')
        install_mas = text.index("if brew install mas; then")
        native_upgrade = text.index("sudo -n env MAS_NO_AUTO_INDEX=1 mas upgrade")
        self.assertLess(dry_run_exit, install_mas)
        self.assertLess(dry_run_exit, native_upgrade)

    def test_appstore_skips_sudo_when_native_queue_is_empty(self) -> None:
        text = self.read_script("update_appstore.sh")
        self.assertIn('if [ -z "$NATIVE_OUTDATED" ]; then', text)
        self.assertIn("sudo mas upgrade skipped", text)
        self.assertIn("mas outdated --accurate", text)
        self.assertIn("MAC_UPDATE_MAS_CHECK_TIMEOUT", text)
        self.assertIn("MAC_UPDATE_MAS_UPGRADE_TIMEOUT", text)
        self.assertIn('run_with_timeout "$MAS_UPGRADE_TIMEOUT"', text)

    def test_appstore_success_header_depends_on_final_exit_status(self) -> None:
        text = self.read_script("update_appstore.sh")
        final_block = text[text.rindex("# ── mas snapshot AFTER update") :]
        self.assertIn('if [ "$APPSTORE_EXIT" -eq 0 ]; then', final_block)
        self.assertIn("FINISHED WITH ERRORS OR PENDING UPDATES", final_block)
        self.assertIn('if [ "$APPSTORE_TOR2_BRANCH" = "no_updates" ]; then', final_block)

    def test_update_all_runs_reboot_capable_system_step_last(self) -> None:
        text = self.read_script("update_all.sh")
        postupdate = text.index("# STEP 5: Update APPLICATIONS.md and UPDATES.md")
        system = text.index("# FINAL MUTATING STEP: macOS system update")
        final_summary = text.index("# Final summary", system)
        self.assertLess(postupdate, system)
        self.assertLess(system, final_summary)
        self.assertIn('elif [ "$OVERALL_EXIT" -ne 0 ]; then', text[system:final_summary])

    def test_update_all_skips_system_after_each_failed_update_layer(self) -> None:
        layers = {
            "appstore": "update_appstore.sh",
            "npm": "update_npm_cli.sh",
            "brew": "update_brew.sh",
            "internet": "update_internet_apps.sh",
        }
        for selected, failing_script in layers.items():
            with self.subTest(layer=selected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copy2(REPO_ROOT / "update_all.sh", root / "update_all.sh")
                shutil.copy2(REPO_ROOT / "VERSION", root / "VERSION")
                shutil.copytree(REPO_ROOT / "lib", root / "lib")
                shutil.copytree(REPO_ROOT / "i18n", root / "i18n")

                marker = root / "system-ran"
                for script in layers.values():
                    body = "#!/usr/bin/env bash\nexit 9\n" if script == failing_script else "#!/usr/bin/env bash\nexit 0\n"
                    (root / script).write_text(body, encoding="utf-8")
                (root / "update_system.sh").write_text(
                    '#!/usr/bin/env bash\nprintf ran > "$SYSTEM_MARKER"\n',
                    encoding="utf-8",
                )

                mock_bin = root / "mock-bin"
                mock_bin.mkdir()
                (mock_bin / "uname").write_text("#!/bin/sh\necho arm64\n", encoding="utf-8")
                (mock_bin / "sw_vers").write_text(
                    "#!/bin/sh\n"
                    'case "$1" in\n'
                    "  -productVersion) echo 26.5.2 ;;\n"
                    "  -buildVersion) echo TESTBUILD ;;\n"
                    "  *) echo 'ProductName: macOS' ;;\n"
                    "esac\n",
                    encoding="utf-8",
                )
                for executable in [*layers.values(), "update_system.sh"]:
                    (root / executable).chmod(0o755)
                (mock_bin / "uname").chmod(0o755)
                (mock_bin / "sw_vers").chmod(0o755)

                args = [
                    "/bin/bash",
                    str(root / "update_all.sh"),
                    "--yes",
                    "--skip-prescan",
                    "--skip-postupdate",
                ]
                skip_flags = {
                    "appstore": "--skip-appstore",
                    "npm": "--skip-npm",
                    "brew": "--skip-brew",
                    "internet": "--skip-internet",
                }
                args.extend(flag for layer, flag in skip_flags.items() if layer != selected)
                env = os.environ.copy()
                env.update(
                    {
                        "PATH": f"{mock_bin}:/usr/bin:/bin",
                        "SYSTEM_MARKER": str(marker),
                        "MAC_LANG": "en",
                    }
                )
                result = subprocess.run(
                    args,
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertNotEqual(result.returncode, 0, msg=result.stdout + result.stderr)
                self.assertFalse(marker.exists(), msg=f"system ran after {selected} failed")
                self.assertIn("Skipping the final macOS update", result.stdout)

    def test_inventory_only_refresh_does_not_append_update_history(self) -> None:
        text = self.read_script("update_all.sh")
        inventory_guard = text.index("if os.environ.get('MAC_UPDATE_INVENTORY_ONLY') == '1':")
        history_builder = text.index("# ── Build UPDATES.md history entry", inventory_guard)
        self.assertLess(inventory_guard, history_builder)
        build = self.read_script("build_inventory.sh")
        self.assertIn("MAC_UPDATE_INVENTORY_ONLY=1", build)
        self.assertIn("UPDATES.md history intentionally unchanged", text)

    def test_prescan_recognizes_formatted_inventory_cells(self) -> None:
        text = self.read_script("update_all.sh")
        self.assertIn(r'(?:\*\*)?(?:\s+[^|]+)?\s*\|', text)
        self.assertIn("fields[1] == 'appstore_gui'", text)

    def test_internet_dmg_handlers_use_session_mount_helper(self) -> None:
        handlers = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("hdiutil attach", handlers)
        self.assertNotIn("/Volumes/", handlers)
        self.assertEqual(handlers.count('mount_verified_dmg "$TEMP_DMG"'), 6)
        self.assertEqual(handlers.count("detach_verified_dmg"), 6)

    def test_microsoft_updates_are_verified_and_teams_is_hybrid(self) -> None:
        handlers = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('MAU_VERIFY=$(run_with_timeout 60 "$MAU_CLI" --list', handlers)
        self.assertIn("iu_microsoft_teams()", handlers)
        self.assertIn("MAU_TEAMS21_VERIFIED", handlers)
        self.assertIn("TEAMS21", handlers)

    def test_provider_config_is_written_atomically_with_private_mode(self) -> None:
        text = (REPO_ROOT / "dev_sync" / "provider_setup.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("config_tmp=", text)
        self.assertIn('chmod 600 "$config_tmp"', text)
        self.assertIn('mv -f "$config_tmp" "$CONFIG_FILE"', text)

    def test_platform_requires_apple_silicon(self) -> None:
        text = (REPO_ROOT / "lib" / "platform.sh").read_text(encoding="utf-8")
        self.assertIn("mac_update_require_apple_silicon", text)
        self.assertIn("arm64", text)
        master = self.read_script("update_all.sh")
        self.assertIn("lib/platform.sh", master)
        self.assertIn("mac_update_require_supported_platform", master)
        self.assertIn("mac_update_require_macos_minimum 13", text)

    def test_internet_apps_config_has_handlers(self) -> None:
        cfg = REPO_ROOT / "config" / "internet_apps.txt"
        script = (
            self.read_script("update_internet_apps.sh")
            + (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(encoding="utf-8")
        )
        names = [
            ln.split("#", 1)[0].strip()
            for ln in cfg.read_text(encoding="utf-8").splitlines()
            if ln.split("#", 1)[0].strip()
        ]
        # Each config app must appear in handler script (name or alias)
        aliases = {
            "Firefox Developer Edition": "Firefox Dev",
            "Perplexity": "Perplexity",
            "Claude": "Claude",
            "Comet": "Comet",
            "Gemini": "Gemini",
            "OpenCode": "OpenCode",
            "zoom.us": "Zoom",
            "Microsoft Excel": "Microsoft",
            "Microsoft Word": "Microsoft",
            "Microsoft Outlook": "Microsoft",
            "Microsoft PowerPoint": "Microsoft",
            "Microsoft OneNote": "Microsoft",
            "Microsoft Teams": "Microsoft",
            "Visual Studio Code": "VS Code",
            "Ledger Live": "Ledger",
            "Ledger Wallet": "Ledger",
        }
        for name in names:
            needle = aliases.get(name, name)
            self.assertIn(
                needle,
                script,
                msg=f"config entry {name!r} has no handler marker in update_internet_apps.sh",
            )

    def test_internet_diag_on_session(self) -> None:
        text = self.read_script("update_internet_apps.sh")
        self.assertIn("internet_diag.txt", text)

    def test_internet_methods_registry_covers_config(self) -> None:
        cfg = REPO_ROOT / "config" / "internet_apps.txt"
        methods = REPO_ROOT / "config" / "internet_app_methods.txt"
        apps = [
            ln.split("#", 1)[0].strip()
            for ln in cfg.read_text(encoding="utf-8").splitlines()
            if ln.split("#", 1)[0].strip()
        ]
        registry = {}
        for ln in methods.read_text(encoding="utf-8").splitlines():
            ln = ln.split("#", 1)[0].strip()
            if not ln:
                continue
            parts = ln.split("|")
            self.assertGreaterEqual(len(parts), 3, msg=f"bad registry line: {ln!r}")
            registry[parts[0]] = parts[1]
        for app in apps:
            self.assertIn(app, registry, msg=f"missing method registry for {app!r}")
        office_apps = [a for a in apps if a.startswith("Microsoft ") and a != "Microsoft Teams"]
        self.assertTrue(office_apps)
        self.assertTrue(all(registry[a] == "msupdate" for a in office_apps))
        self.assertEqual(
            registry.get("Microsoft Teams"), "mau_fallback_self_update"
        )

    def test_internet_config_status_var_parity(self) -> None:
        """All 4 internet-app config sources must agree on STATUS_* variables.

        Adding a new internet app requires touching 4–5 places:
          1. config/internet_apps.txt (app name)
          2. config/internet_app_methods.txt (AppName|method|STATUS_VAR)
          3. config/internet_dispatch_order.txt (iu_* function name)
          4. update_internet_apps.sh (STATUS_* init + summary table + exit loop)
        This test validates they all agree, preventing silent omissions.
        """
        methods_path = REPO_ROOT / "config" / "internet_app_methods.txt"
        apps_path = REPO_ROOT / "config" / "internet_apps.txt"
        orchestrator = self.read_script("update_internet_apps.sh")

        # ── Parse methods config → set of unique STATUS_* var names ──
        methods_status_vars = set()
        methods_apps = []
        for ln in methods_path.read_text(encoding="utf-8").splitlines():
            ln = ln.split("#", 1)[0].strip()
            if not ln:
                continue
            parts = ln.split("|")
            self.assertGreaterEqual(
                len(parts), 3,
                msg=f"internet_app_methods.txt bad line (need 3 pipe fields): {ln!r}",
            )
            methods_apps.append(parts[0])
            methods_status_vars.add(parts[2])

        # ── Parse apps config ──
        config_apps = [
            ln.split("#", 1)[0].strip()
            for ln in apps_path.read_text(encoding="utf-8").splitlines()
            if ln.split("#", 1)[0].strip()
        ]

        # ── 1. apps.txt and methods.txt must list the same apps ──
        self.assertEqual(
            config_apps, methods_apps,
            msg="internet_apps.txt and internet_app_methods.txt app lists differ",
        )

        # ── 2. Every STATUS_* from methods config must be initialized ──
        #    in update_internet_apps.sh (the STATUS_XYZ="..." block)
        init_pattern = re.compile(r'^(STATUS_[A-Z0-9_]+)=', re.MULTILINE)
        initialized_vars = set(init_pattern.findall(orchestrator))
        for var in methods_status_vars:
            self.assertIn(
                var, initialized_vars,
                msg=f"STATUS var {var!r} from internet_app_methods.txt not initialized "
                    f"in update_internet_apps.sh",
            )

        # ── 3. Every initialized STATUS_* must appear in the summary table ──
        #    (the printf "%-32s %s" block referencing $STATUS_*)
        for var in initialized_vars:
            self.assertIn(
                f"${var}", orchestrator,
                msg=f"STATUS var {var!r} initialized but never referenced "
                    f"(missing from summary table?) in update_internet_apps.sh",
            )

        # ── 4. Every initialized STATUS_* must appear in the exit-code loop ──
        #    (the `for status in ... "$STATUS_*"` block at the bottom)
        exit_loop_match = re.search(
            r'for status in\b.*?^done', orchestrator,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(exit_loop_match, msg="exit-code loop not found")
        exit_loop_text = exit_loop_match.group(0)
        for var in initialized_vars:
            self.assertIn(
                f"${var}", exit_loop_text,
                msg=f"STATUS var {var!r} missing from exit-code for-loop "
                    f"in update_internet_apps.sh",
            )

        # ── 5. No orphaned STATUS_* in orchestrator not declared in methods ──
        for var in initialized_vars:
            self.assertIn(
                var, methods_status_vars,
                msg=f"STATUS var {var!r} initialized in update_internet_apps.sh "
                    f"but not declared in internet_app_methods.txt — orphaned?",
            )

    def test_i18n_lang_files_key_parity(self) -> None:
        langs = ["en", "pl", "de", "fr", "es", "it", "pt"]
        keys_by_lang = {}
        for lang in langs:
            text = (REPO_ROOT / "i18n" / f"lang_{lang}.sh").read_text(encoding="utf-8")
            keys = set(re.findall(r"^(L_[A-Z0-9_]+)=", text, re.MULTILINE))
            keys_by_lang[lang] = keys
        base = keys_by_lang["en"]
        for lang in langs[1:]:
            self.assertEqual(
                keys_by_lang[lang],
                base,
                msg=f"lang_{lang}.sh key set differs from lang_en.sh",
            )

    def test_i18n_loader_uses_set_a_not_manual_exports(self) -> None:
        """i18n/loader.sh must use set -a to auto-export lang variables.

        The old pattern had 151 hand-maintained export lines with many
        duplicates. set -a auto-exports every assignment during sourcing,
        so adding a new L_* key to lang_*.sh never requires touching
        loader.sh. Guard against regression to hand-maintained exports.
        """
        text = (REPO_ROOT / "i18n" / "loader.sh").read_text(encoding="utf-8")
        self.assertIn("set -a", text, msg="loader.sh must use set -a for auto-export")
        self.assertIn("set +a", text, msg="loader.sh must restore set +a after sourcing")
        # Regression guard: no more than 5 export lines (only MAC_LANG should remain)
        export_count = sum(1 for ln in text.splitlines() if ln.strip().startswith("export L_"))
        self.assertLessEqual(
            export_count, 5,
            msg=f"loader.sh has {export_count} 'export L_*' lines — use set -a instead",
        )

    def test_internet_registry_lib_exists(self) -> None:
        for name in (
            "lib/internet_registry.sh",
            "lib/internet_handlers.sh",
            "lib/internet_app_updates.sh",
            "config/internet_app_methods.txt",
            "config/internet_dispatch_order.txt",
        ):
            self.assertTrue((REPO_ROOT / name).is_file(), msg=f"missing {name}")

    def test_internet_dispatch_order_handlers_exist(self) -> None:
        order_path = REPO_ROOT / "config" / "internet_dispatch_order.txt"
        impl = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(encoding="utf-8")
        fns = [
            ln.split("#", 1)[0].strip()
            for ln in order_path.read_text(encoding="utf-8").splitlines()
            if ln.split("#", 1)[0].strip()
        ]
        self.assertGreater(len(fns), 20, msg="dispatch order should list handler functions")
        for fn in fns:
            self.assertIn(
                f"{fn}()",
                impl,
                msg=f"dispatch entry {fn!r} missing from lib/internet_app_updates.sh",
            )
        orchestrator = self.read_script("update_internet_apps.sh")
        self.assertIn("internet_dispatch_run_all", orchestrator)

    def test_brew_dry_run_before_update(self) -> None:
        text = self.read_script("update_brew.sh")
        dry_pos = text.find('MAC_UPDATE_DRY_RUN')
        update_pos = text.find("brew update")
        self.assertGreater(dry_pos, -1)
        self.assertGreater(update_pos, -1)
        # dry-run early exit must appear before first brew update
        early = text.find("[DRY-RUN] Would run: brew update")
        self.assertGreater(early, -1)
        self.assertLess(early, update_pos)

    def test_brew_asaf_filter_keeps_internal_blank_lines_in_warning_block(self) -> None:
        text = self.read_script("update_brew.sh")
        self.assertIn('in_dylib_block && /^(Warning:|Error:)/', text)
        self.assertNotIn('if ($0 == "") emit_dylib_block()', text)

    def test_skip_doctor_flag_consumed_by_update_brew(self) -> None:
        """--skip-doctor must be honoured in update_brew.sh, not just exported.

        The CLI flag MAC_UPDATE_SKIP_DOCTOR is exported by lib/cli.sh and set
        by build_inventory.sh, but was never read by the brew doctor block in
        update_brew.sh — making the flag a documented no-op. This test ensures
        the flag is actually consumed.
        """
        text = self.read_script("update_brew.sh")
        self.assertIn("MAC_UPDATE_SKIP_DOCTOR", text,
                       msg="update_brew.sh must read MAC_UPDATE_SKIP_DOCTOR")

    def test_cli_flags_all_consumed(self) -> None:
        """Every MAC_UPDATE_* flag exported by lib/cli.sh must be read somewhere.

        Catches the class of bug where a CLI flag is defined and documented
        but never actually checked by the consumer script (as happened with
        --skip-doctor / MAC_UPDATE_SKIP_DOCTOR). Scans all .sh files outside
        cli.sh for each flag name.
        """
        cli_text = (REPO_ROOT / "lib" / "cli.sh").read_text(encoding="utf-8")
        # Extract all MAC_UPDATE_* var names exported in cli.sh
        flags = set(re.findall(r'export (MAC_UPDATE_[A-Z_]+)=', cli_text))
        self.assertGreater(len(flags), 5, msg="Expected at least 6 CLI flags")

        # Gather all .sh file contents EXCEPT cli.sh itself
        all_sh_text = ""
        for sh_file in REPO_ROOT.rglob("*.sh"):
            if sh_file.name == "cli.sh":
                continue
            if ".git" in sh_file.parts:
                continue
            all_sh_text += sh_file.read_text(encoding="utf-8")

        for flag in flags:
            self.assertIn(
                flag, all_sh_text,
                msg=f"CLI flag {flag!r} is exported by lib/cli.sh but never "
                    f"read by any other .sh file — documented no-op?",
            )


    def test_version_file_present(self) -> None:
        version_path = REPO_ROOT / "VERSION"
        self.assertTrue(version_path.is_file())
        self.assertRegex(version_path.read_text(encoding="utf-8").strip(), r"^\d+\.\d+\.\d+$")

    def test_dev_sync_directory(self) -> None:
        self.assertTrue((REPO_ROOT / "dev_sync").is_dir())
        self.assertFalse((REPO_ROOT / "dev-sync").exists())

    def test_install_and_inventory_scripts_exist(self) -> None:
        for name in (
            "install.sh",
            "build_inventory.sh",
            "uninstall.sh",
            "scripts/report_update_coverage.sh",
        ):
            self.assertTrue((REPO_ROOT / name).is_file(), msg=f"missing {name}")

    def test_install_does_not_import_cloud_overlay(self) -> None:
        text = self.read_script("install.sh")
        self.assertIsNone(re.search(r"bash\s+.*dev-sync-import", text))
        self.assertIn("build_inventory.sh", text)
        self.assertIn("Never import private overlay on fresh install", text)


class InternetLibParserTests(unittest.TestCase):
    """Tests for lib/internet_apps.sh, internet_registry.sh, internet_handlers.sh,
    internet_i18n.sh, and github_release.sh — config parsers and dispatch helpers.

    These have zero test coverage per design specs. Static assertions plus
    bash-invoked functional tests where safe.
    """

    def read_lib(self, name: str) -> str:
        return (REPO_ROOT / "lib" / name).read_text(encoding="utf-8")

    # ── internet_registry.sh: registry loader ──────────────────────

    def test_registry_load_returns_1_on_missing_config(self) -> None:
        """internet_registry_load must return 1 when config file is missing."""
        text = self.read_lib("internet_registry.sh")
        self.assertIn('[ -f "$cfg" ] || return 1', text,
                       msg="internet_registry_load must return 1 on missing config")

    def test_registry_parse_uses_pipe_delimiter(self) -> None:
        """Registry parser must split on | (pipe) per config format."""
        text = self.read_lib("internet_registry.sh")
        # The parser uses ${line%%|*} and ${line#*|} to split fields
        self.assertIn('${line%%|*}', text)
        self.assertIn('${line#*|}', text)

    def test_registry_dispatch_validates_function_exists(self) -> None:
        """internet_dispatch_run_all must check function exists before calling."""
        text = self.read_lib("internet_registry.sh")
        self.assertIn('type "$fn"', text,
                       msg="dispatch must validate handler function exists via 'type'")

    def test_registry_dispatch_returns_1_on_missing_config(self) -> None:
        text = self.read_lib("internet_registry.sh")
        # The dispatch function should guard against missing config
        self.assertIn('[ -f "$cfg" ] || return 1', text)

    @unittest.skipUnless(
        __import__("shutil").which("bash"),
        "bash not available"
    )
    def test_registry_load_parses_valid_rows(self) -> None:
        """Functional test: internet_registry_load correctly parses pipe-delimited rows."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config"
            cfg.mkdir()
            (cfg / "internet_app_methods.txt").write_text(
                "# comment\n"
                "TestApp|github_dmg|STATUS_TEST\n"
                "OtherApp|silent_launch|STATUS_OTHER\n",
                encoding="utf-8",
            )
            import subprocess
            result = subprocess.run(
                [
                    "bash", "-c",
                    f'SCRIPT_DIR="{tmp}"; '
                    f'. "{REPO_ROOT}/lib/internet_registry.sh"; '
                    f'internet_registry_load; '
                    f'echo "${{#INTERNET_METHOD_APPS[@]}}"; '
                    f'echo "${{INTERNET_METHOD_APPS[0]}}|${{INTERNET_METHOD_TYPES[0]}}|${{INTERNET_METHOD_STATUS[0]}}"; '
                    f'echo "${{INTERNET_METHOD_APPS[1]}}|${{INTERNET_METHOD_TYPES[1]}}|${{INTERNET_METHOD_STATUS[1]}}"'
                ],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.strip().splitlines()
            self.assertEqual(lines[0], "2", msg="Should parse 2 rows")
            self.assertEqual(lines[1], "TestApp|github_dmg|STATUS_TEST")
            self.assertEqual(lines[2], "OtherApp|silent_launch|STATUS_OTHER")

    @unittest.skipUnless(
        __import__("shutil").which("bash"),
        "bash not available"
    )
    def test_registry_load_skips_comments_and_blanks(self) -> None:
        """Registry loader must skip # comments and blank lines."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config"
            cfg.mkdir()
            (cfg / "internet_app_methods.txt").write_text(
                "# header comment\n"
                "\n"
                "App1|method1|STATUS_1\n"
                "  # indented comment\n"
                "\n"
                "App2|method2|STATUS_2\n",
                encoding="utf-8",
            )
            import subprocess
            result = subprocess.run(
                [
                    "bash", "-c",
                    f'SCRIPT_DIR="{tmp}"; '
                    f'. "{REPO_ROOT}/lib/internet_registry.sh"; '
                    f'internet_registry_load; '
                    f'echo "${{#INTERNET_METHOD_APPS[@]}}"'
                ],
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(result.stdout.strip(), "2",
                             msg="Should parse only 2 data rows, skipping comments/blanks")

    def test_registry_load_validates_field_count(self) -> None:
        """Registry loader must validate pipe-delimited row has 3 fields."""
        text = self.read_lib("internet_registry.sh")
        self.assertIn("malformed row", text,
                       msg="internet_registry_load must warn on malformed rows")

    @unittest.skipUnless(
        __import__("shutil").which("bash"),
        "bash not available"
    )
    def test_registry_load_skips_malformed_rows(self) -> None:
        """Hardening: rows with fewer than 3 pipe fields must be skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config"
            cfg.mkdir()
            (cfg / "internet_app_methods.txt").write_text(
                "Good|github_dmg|STATUS_GOOD\n"
                "BadRow_no_pipes\n"
                "Also_Bad|only_one_pipe\n"
                "Fine|silent_launch|STATUS_FINE\n",
                encoding="utf-8",
            )
            import subprocess
            result = subprocess.run(
                [
                    "bash", "-c",
                    f'SCRIPT_DIR="{tmp}"; '
                    f'. "{REPO_ROOT}/lib/internet_registry.sh"; '
                    f'internet_registry_load; '
                    f'echo "${{#INTERNET_METHOD_APPS[@]}}"; '
                    f'echo "${{INTERNET_METHOD_APPS[0]}}"; '
                    f'echo "${{INTERNET_METHOD_APPS[1]}}"'
                ],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.strip().splitlines()
            self.assertEqual(lines[0], "2", msg="Should parse only 2 valid rows")
            self.assertEqual(lines[1], "Good")
            self.assertEqual(lines[2], "Fine")
            # Malformed rows should produce stderr warnings
            self.assertIn("malformed row", result.stderr)

    def test_handler_set_status_var_name_guard(self) -> None:
        """internet_handler_set_status must guard var_name against non-STATUS_* values."""
        text = self.read_lib("internet_handlers.sh")
        self.assertIn("STATUS_[A-Z0-9_]", text,
                       msg="set_status must validate var_name is STATUS_*")
        self.assertIn("invalid var_name", text,
                       msg="set_status must print error on invalid var_name")

    @unittest.skipUnless(
        __import__("shutil").which("bash"),
        "bash not available"
    )
    def test_handler_set_status_rejects_bad_var_name(self) -> None:
        """Hardening: set_status must reject var names that don't match STATUS_*."""
        import subprocess
        result = subprocess.run(
            [
                "bash", "-c",
                f'. "{REPO_ROOT}/lib/internet_handlers.sh"; '
                f'internet_handler_set_status "EVIL_VAR" "pwned"; '
                f'echo "exit=$?"'
            ],
            capture_output=True, text=True, timeout=5,
        )
        self.assertIn("invalid var_name", result.stderr)
        self.assertIn("exit=1", result.stdout)

    # ── internet_apps.sh: config loader ────────────────────────────

    def test_apps_load_returns_1_on_missing_config(self) -> None:
        text = self.read_lib("internet_apps.sh")
        self.assertIn('return 1', text,
                       msg="internet_apps_load_config must return 1 on missing config")

    @unittest.skipUnless(
        __import__("shutil").which("bash"),
        "bash not available"
    )
    def test_apps_load_parses_config(self) -> None:
        """Functional test: internet_apps_load_config parses app names."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config"
            cfg.mkdir()
            (cfg / "internet_apps.txt").write_text(
                "# comment\nGoogle Chrome\nFirefox Dev\n",
                encoding="utf-8",
            )
            import subprocess
            result = subprocess.run(
                [
                    "bash", "-c",
                    f'SCRIPT_DIR="{tmp}"; '
                    f'. "{REPO_ROOT}/lib/internet_apps.sh"; '
                    f'internet_apps_load_config; '
                    f'echo "${{#INTERNET_APPS_LIST[@]}}"; '
                    f'echo "${{INTERNET_APPS_LIST[0]}}"; '
                    f'echo "${{INTERNET_APPS_LIST[1]}}"'
                ],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.strip().splitlines()
            self.assertEqual(lines[0], "2")
            self.assertEqual(lines[1], "Google Chrome")
            self.assertEqual(lines[2], "Firefox Dev")

    def test_app_path_special_cases_covered_in_config(self) -> None:
        """Every special-case app in internet_app_path() must exist in internet_apps.txt."""
        lib_text = self.read_lib("internet_apps.sh")
        cfg_text = (REPO_ROOT / "config" / "internet_apps.txt").read_text(encoding="utf-8")
        # Extract the internet_app_path function body (between its case and esac)
        fn_match = re.search(
            r'internet_app_path\(\)\s*\{.*?case\s+"\$app_name"\s+in(.*?)esac',
            lib_text, re.DOTALL,
        )
        self.assertIsNotNone(fn_match, msg="internet_app_path case block not found")
        case_body = fn_match.group(1)
        # Extract quoted app names from case patterns like: "OpenCode")
        special_cases = re.findall(r'"([A-Z][^"]+)"\)', case_body)
        self.assertGreater(len(special_cases), 0, msg="Expected special-case apps")
        for app in special_cases:
            found = app in cfg_text or app.replace(" Live", "") in cfg_text
            self.assertTrue(
                found,
                msg=f"internet_app_path special case {app!r} not found in internet_apps.txt",
            )

    # ── internet_handlers.sh: eval safety ──────────────────────────

    def test_handler_set_status_uses_eval(self) -> None:
        """internet_handler_set_status uses eval — verify it's the expected pattern."""
        text = self.read_lib("internet_handlers.sh")
        self.assertIn("internet_handler_set_status", text)
        # The eval pattern should be: eval "${var_name}=\"${value}\""
        self.assertIn('eval "${var_name}', text,
                       msg="set_status must use eval with var_name")

    def test_handler_set_status_callers_use_safe_var_names(self) -> None:
        """All callers of internet_handler_set_status must pass STATUS_* literal var names.

        Since set_status uses eval, we verify that all call sites pass
        a STATUS_* variable name (safe constant), not user input.
        """
        # Combine all files that call internet_handler_set_status
        combined = ""
        for name in ("lib/internet_handlers.sh", "lib/internet_app_updates.sh",
                      "update_internet_apps.sh"):
            combined += (REPO_ROOT / name).read_text(encoding="utf-8")
        # Find all calls: internet_handler_set_status "VAR_NAME" ...
        calls = re.findall(
            r'internet_handler_set_status\s+"?(\$?\{?[A-Z_]+\}?)"?',
            combined,
        )
        # Every call must pass either a STATUS_* literal or a $status_var reference
        for call_arg in calls:
            clean = call_arg.strip('"${}')
            is_safe = (
                clean.startswith("STATUS_")
                or clean == "status_var"  # variable holding a STATUS_* name
                or clean.startswith("status")
            )
            self.assertTrue(
                is_safe,
                msg=f"internet_handler_set_status called with unsafe var: {call_arg!r}",
            )

    # ── internet_i18n.sh: printf helper ────────────────────────────

    def test_internet_msg_uses_printf(self) -> None:
        text = self.read_lib("internet_i18n.sh")
        self.assertIn('printf "$fmt"', text,
                       msg="internet_msg must use printf for format substitution")

    def test_diag_log_guards_session_dir(self) -> None:
        """internet_diag_log and internet_diag_section must check MAC_UPDATE_SESSION_DIR."""
        text = self.read_lib("internet_i18n.sh")
        # Both functions should guard with: [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]
        session_guards = text.count('MAC_UPDATE_SESSION_DIR')
        self.assertGreaterEqual(
            session_guards, 2,
            msg="Both diag functions must guard on MAC_UPDATE_SESSION_DIR",
        )

    # ── github_release.sh: curl safety ─────────────────────────────

    def test_github_latest_tag_curl_safety(self) -> None:
        """github_latest_tag must use --max-time and --retry for resilience."""
        text = self.read_lib("github_release.sh")
        self.assertIn("--max-time", text, msg="curl must have --max-time timeout")
        self.assertIn("--retry", text, msg="curl must have --retry for resilience")

    def test_github_latest_tag_fallback_on_error(self) -> None:
        """github_latest_tag must output '?' on any failure, never empty string."""
        text = self.read_lib("github_release.sh")
        self.assertIn('echo "${result:-?}"', text,
                       msg="Must fall back to '?' when result is empty")
        # Python parser must also handle exceptions gracefully
        self.assertIn("except Exception", text)

    # ── Config file format validation ──────────────────────────────

    def test_methods_config_all_rows_have_3_fields(self) -> None:
        """Every data row in internet_app_methods.txt must have exactly 3 pipe fields."""
        methods = REPO_ROOT / "config" / "internet_app_methods.txt"
        for i, ln in enumerate(methods.read_text(encoding="utf-8").splitlines(), 1):
            data = ln.split("#", 1)[0].strip()
            if not data:
                continue
            parts = data.split("|")
            self.assertEqual(
                len(parts), 3,
                msg=f"internet_app_methods.txt line {i}: expected 3 pipe-delimited "
                    f"fields, got {len(parts)}: {ln!r}",
            )

    def test_methods_config_status_vars_uppercase(self) -> None:
        """STATUS_* vars in methods config must be uppercase identifiers."""
        methods = REPO_ROOT / "config" / "internet_app_methods.txt"
        for ln in methods.read_text(encoding="utf-8").splitlines():
            data = ln.split("#", 1)[0].strip()
            if not data:
                continue
            parts = data.split("|")
            if len(parts) >= 3:
                self.assertRegex(
                    parts[2], r'^STATUS_[A-Z0-9_]+$',
                    msg=f"STATUS var must be uppercase: {parts[2]!r} in {ln!r}",
                )

    def test_dispatch_order_no_empty_lines_in_data(self) -> None:
        """internet_dispatch_order.txt should only have function names and blanks."""
        dispatch = REPO_ROOT / "config" / "internet_dispatch_order.txt"
        for ln in dispatch.read_text(encoding="utf-8").splitlines():
            data = ln.split("#", 1)[0].strip()
            if not data:
                continue
            self.assertRegex(
                data, r'^iu_[a-z0-9_]+$',
                msg=f"dispatch order entry must match iu_* pattern: {data!r}",
            )


if __name__ == "__main__":
    unittest.main()
