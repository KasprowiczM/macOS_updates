#!/usr/bin/env python3
"""Tests for Chromium updaters (Google Keystone, Comet, Omaha proof) (T5)."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class ChromiumUpdatersTests(unittest.TestCase):
    """Verify Google Keystone, Comet, and Omaha evaluation."""

    def test_gemini_configured_as_keystone(self) -> None:
        """Gemini must be configured with method 'keystone' in config/internet_app_methods.txt."""
        cfg = (REPO_ROOT / "config" / "internet_app_methods.txt").read_text(encoding="utf-8")
        found = False
        for line in cfg.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split("|")
            if parts[0] == "Gemini":
                self.assertEqual(parts[1], "keystone")
                self.assertEqual(parts[2], "STATUS_GEMINI")
                found = True
                break
        self.assertTrue(found, "Gemini not found in config/internet_app_methods.txt")

    def test_google_status_noupdate_is_current_vendor(self) -> None:
        """Omaha noupdate response evaluates to L_INTERNET_STATUS_VENDOR_NOUPDATE with verified=1."""
        fixture = (REPO_ROOT / "tests" / "fixtures" / "vendor_feeds" / "googleupdater.log").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = f"""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                app_version() {{ echo "1.116.5.889"; }}
                log_inc=$(cat <<'EOF'
{fixture}
EOF
)
                evaluate_omaha_status "Gemini" "/Applications/Gemini.app" "$log_inc" "com.google.geminimacos"
                echo "STATUS=$INTERNET_LAST_STATUS"
                echo "VERIFIED=$INTERNET_LAST_VERIFIED"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("STATUS=✅ Up to date (vendor updater: no update)", res.stdout)
            self.assertIn("VERIFIED=1", res.stdout)

    def test_chrome_rollout_hold_when_public_newer(self) -> None:
        """Chrome with noupdate but newer public version on VersionHistory triggers rollout hold."""
        omaha_log = (REPO_ROOT / "tests" / "fixtures" / "vendor_feeds" / "googleupdater.log").read_text(encoding="utf-8")
        vh_fixture = (REPO_ROOT / "tests" / "fixtures" / "vendor_feeds" / "versionhistory.json").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_curl = bin_dir / "curl"
            mock_curl.write_text(
                f"""#!/usr/bin/env bash
cat <<'EOF'
{vh_fixture}
EOF
""",
                encoding="utf-8",
            )
            mock_curl.chmod(mock_curl.stat().st_mode | stat.S_IEXEC)

            cmd = f"""
                export PATH="{bin_dir}:$PATH"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                app_version() {{ echo "153.0.8010.53"; }}
                log_inc=$(cat <<'EOF'
{omaha_log}
EOF
)
                evaluate_omaha_status "Google Chrome" "/Applications/Google Chrome.app" "$log_inc" "com.google.chrome"
                echo "STATUS=$INTERNET_LAST_STATUS"
                echo "VERIFIED=$INTERNET_LAST_VERIFIED"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("Vendor rollout: 153.0.8010.53 installed, 154.0.8037.58 public", res.stdout)
            self.assertIn("VERIFIED=1", res.stdout)

    def test_chrome_staged_rollout_when_no_omaha_response(self) -> None:
        """Chrome with no Omaha response and newer VersionHistory reports rollout hold without soft fail."""
        vh_fixture = (REPO_ROOT / "tests" / "fixtures" / "vendor_feeds" / "versionhistory.json").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_curl = bin_dir / "curl"
            mock_curl.write_text(
                f"""#!/usr/bin/env bash
cat <<'EOF'
{vh_fixture}
EOF
""",
                encoding="utf-8",
            )
            mock_curl.chmod(mock_curl.stat().st_mode | stat.S_IEXEC)

            cmd = f"""
                export PATH="{bin_dir}:$PATH"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_status.sh"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                export MAC_UPDATE_GOOGLE_USER_LOG="/dev/null"
                export MAC_UPDATE_GOOGLE_SYS_LOG="/dev/null"
                app_version() {{ echo "153.0.8010.53"; }}
                evaluate_omaha_status "Google Chrome" "/Applications/Google Chrome.app" "" "com.google.chrome"
                echo "STATUS=$INTERNET_LAST_STATUS"
                echo "VERIFIED=$INTERNET_LAST_VERIFIED"
                code="$(internet_status_code "$INTERNET_LAST_STATUS")"
                echo "CODE=$code"
                INTERNET_SOFT_FAIL=0
                case "$code" in
                    behind|needs_restart|feed_stale)
                        INTERNET_SOFT_FAIL=1
                        ;;
                esac
                echo "SOFT_FAIL=$INTERNET_SOFT_FAIL"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("Vendor rollout: 153.0.8010.53 installed, 154.0.8037.58 public", res.stdout)
            self.assertIn("VERIFIED=1", res.stdout)
            self.assertIn("CODE=rollout_hold", res.stdout)
            self.assertIn("SOFT_FAIL=0", res.stdout)


    def test_chrome_installed_ge_public_when_no_omaha_response(self) -> None:
        """Chrome with no Omaha response but installed >= public VersionHistory reports current."""
        vh_fixture = (REPO_ROOT / "tests" / "fixtures" / "vendor_feeds" / "versionhistory.json").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_curl = bin_dir / "curl"
            mock_curl.write_text(
                f"""#!/usr/bin/env bash
cat <<'EOF'
{vh_fixture}
EOF
""",
                encoding="utf-8",
            )
            mock_curl.chmod(mock_curl.stat().st_mode | stat.S_IEXEC)

            cmd = f"""
                export PATH="{bin_dir}:$PATH"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_status.sh"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                export MAC_UPDATE_GOOGLE_USER_LOG="/dev/null"
                export MAC_UPDATE_GOOGLE_SYS_LOG="/dev/null"
                app_version() {{ echo "154.0.8037.58"; }}
                evaluate_omaha_status "Google Chrome" "/Applications/Google Chrome.app" "" "com.google.chrome"
                echo "STATUS=$INTERNET_LAST_STATUS"
                echo "VERIFIED=$INTERNET_LAST_VERIFIED"
                code="$(internet_status_code "$INTERNET_LAST_STATUS")"
                echo "CODE=$code"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("STATUS=✅ Up to date (154.0.8037.58, Google VersionHistory)", res.stdout)
            self.assertIn("VERIFIED=1", res.stdout)
            self.assertIn("CODE=current_verified", res.stdout)

    def test_google_no_response_is_unverified(self) -> None:
        """Empty or unrelated Omaha log with no VersionHistory results in L_INTERNET_STATUS_UPDATER_TRIGGERED and verified=0."""
        cmd = f"""
            source "{REPO_ROOT}/i18n/lang_en.sh"
            source "{REPO_ROOT}/lib/version.sh"
            source "{REPO_ROOT}/lib/internet_handlers.sh"
            _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
            curl() {{ return 1; }}
            export MAC_UPDATE_GOOGLE_USER_LOG="/dev/null"
            export MAC_UPDATE_GOOGLE_SYS_LOG="/dev/null"
            app_version() {{ echo "153.0.8010.53"; }}
            evaluate_omaha_status "Google Chrome" "/Applications/Google Chrome.app" "" "com.google.chrome"
            echo "STATUS=$INTERNET_LAST_STATUS"
            echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
        self.assertIn("STATUS=⏳ Vendor updater triggered (no response recorded)", res.stdout)
        self.assertIn("VERIFIED=0", res.stdout)

    def test_comet_uses_its_own_updater_log(self) -> None:
        """Comet updater triggers its own binary with --wake-all and reads its own updater.log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_comet_updater = bin_dir / "CometUpdater"
            log_file = Path(tmpdir) / "updater.log"

            # When CometUpdater is called with --wake-all, append Omaha response to its log
            mock_comet_updater.write_text(
                f"""#!/usr/bin/env bash
if [ "$1" = "--wake-all" ]; then
    cat >> "{log_file}" <<'EOF'
[1:2:0923/094646.163000:VERBOSE2:components/update_client/request_sender.cc:200] {{"response":{{"apps":[{{"appid":"ai.perplexity.comet","status":"ok","ping":{{"status":"ok"}},"updatecheck":{{"status":"noupdate"}}}}]}}}}
EOF
    exit 0
fi
exit 1
""",
                encoding="utf-8",
            )
            mock_comet_updater.chmod(mock_comet_updater.stat().st_mode | stat.S_IEXEC)

            dummy_app = Path(tmpdir) / "Comet.app"
            dummy_app.mkdir()

            cmd = f"""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                run_with_timeout() {{ shift; "$@"; }}
                print_info() {{ :; }}
                print_step() {{ :; }}
                print_ok() {{ :; }}
                print_warn() {{ :; }}
                internet_msg() {{ printf "$@"; }}
                app_version() {{ echo "1.0.0"; }}
                MAC_UPDATE_OMAHA_WAIT=3
                internet_handler_chromium_updater "Comet" "{dummy_app}" "{mock_comet_updater}" "{log_file}" "ai.perplexity.comet"
                echo "STATUS=$INTERNET_LAST_STATUS"
                echo "VERIFIED=$INTERNET_LAST_VERIFIED"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("STATUS=✅ Up to date (vendor updater: no update)", res.stdout)
            self.assertIn("VERIFIED=1", res.stdout)


    def test_google_keystone_waits_for_specific_appid(self) -> None:
        """google_keystone_check does not terminate on another app's updatecheck."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_log = Path(tmpdir) / "updater.log"
            user_log.touch()
            mock_agent = Path(tmpdir) / "GoogleSoftwareUpdateAgent"
            mock_agent.write_text(f"""#!/usr/bin/env bash
# First write Drive response only
cat >> "$HOME/Library/Application Support/Google/GoogleUpdater/updater.log" <<'EOF'
{{"response":{{"apps":[{{"appid":"com.google.drivefs","status":"ok","ping":{{"status":"ok"}},"updatecheck":{{"status":"noupdate"}}}}]}}}}
EOF
exit 0
""", encoding="utf-8")
            mock_agent.chmod(mock_agent.stat().st_mode | stat.S_IEXEC)

            cmd = f"""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                _LIB_DIR="{REPO_ROOT}/lib"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                app_version() {{ echo "130.0.6723.69"; }}
                curl() {{ exit 1; }}
                print_info() {{ :; }}
                print_step() {{ :; }}
                print_ok() {{ :; }}
                print_warn() {{ :; }}
                internet_msg() {{ printf "$@"; }}
                # Mock HOME so user_log is picked up
                export HOME="{tmpdir}"
                export MAC_UPDATE_GOOGLE_SYS_UPDATER=""
                mkdir -p "$HOME/Library/Application Support/Google/GoogleUpdater"
                mv "{user_log}" "$HOME/Library/Application Support/Google/GoogleUpdater/updater.log"
                # Mock sleep: on 2nd sleep call, append Chrome updatecheck
                sleep_count=0
                sleep() {{
                    sleep_count=$((sleep_count + 1))
                    if [ "$sleep_count" -ge 2 ]; then
                        cat >> "$HOME/Library/Application Support/Google/GoogleUpdater/updater.log" <<'EOF'
{{"response":{{"apps":[{{"appid":"com.google.chrome","status":"ok","ping":{{"status":"ok"}},"updatecheck":{{"status":"noupdate"}}}}]}}}}
EOF
                    fi
                }}
                MAC_UPDATE_OMAHA_WAIT=10
                google_keystone_check "{mock_agent}" "com.google.chrome"
                evaluate_omaha_status "Google Chrome" "/Applications/Google Chrome.app" "$GOOGLE_OMAHA_INC" "com.google.chrome"
                echo "STATUS=$INTERNET_LAST_STATUS"
                echo "VERIFIED=$INTERNET_LAST_VERIFIED"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("STATUS=✅ Up to date (vendor updater: no update)", res.stdout)
            self.assertEqual(res.stdout.count("VERIFIED=1"), 1)

    def test_google_keystone_wakes_updater_only_once_per_session(self) -> None:
        """Three apps in one session wake the updater stub exactly once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            agent_calls = Path(tmpdir) / "agent_calls.log"
            user_log = Path(tmpdir) / "Library/Application Support/Google/GoogleUpdater/updater.log"
            user_log.parent.mkdir(parents=True)
            user_log.touch()

            mock_agent = Path(tmpdir) / "GoogleSoftwareUpdateAgent"
            mock_agent.write_text(f"""#!/usr/bin/env bash
echo "called" >> "{agent_calls}"
cat >> "{user_log}" <<'EOF'
{{"response":{{"apps":[
  {{"appid":"com.google.chrome","status":"ok","ping":{{"status":"ok"}},"updatecheck":{{"status":"noupdate"}}}},
  {{"appid":"com.google.geminimacos","status":"ok","ping":{{"status":"ok"}},"updatecheck":{{"status":"noupdate"}}}},
  {{"appid":"com.google.drivefs","status":"ok","ping":{{"status":"ok"}},"updatecheck":{{"status":"noupdate"}}}}
]}}}}
EOF
exit 0
""", encoding="utf-8")
            mock_agent.chmod(mock_agent.stat().st_mode | stat.S_IEXEC)

            # In subshell 1: Chrome runs
            cmd_chrome = f"""
                export HOME="{tmpdir}"
                export MAC_UPDATE_SESSION_DIR="{session_dir}"
                export MAC_UPDATE_GOOGLE_SYS_UPDATER=""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                _LIB_DIR="{REPO_ROOT}/lib"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                google_keystone_check "{mock_agent}" "com.google.chrome"
            """
            subprocess.run(["bash", "-c", cmd_chrome], capture_output=True, text=True, check=True)

            # In subshell 2: Gemini runs
            cmd_gemini = f"""
                export HOME="{tmpdir}"
                export MAC_UPDATE_SESSION_DIR="{session_dir}"
                export MAC_UPDATE_GOOGLE_SYS_UPDATER=""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                _LIB_DIR="{REPO_ROOT}/lib"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                google_keystone_check "{mock_agent}" "com.google.geminimacos"
            """
            subprocess.run(["bash", "-c", cmd_gemini], capture_output=True, text=True, check=True)

            # In subshell 3: Drive runs
            cmd_drive = f"""
                export HOME="{tmpdir}"
                export MAC_UPDATE_SESSION_DIR="{session_dir}"
                export MAC_UPDATE_GOOGLE_SYS_UPDATER=""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                _LIB_DIR="{REPO_ROOT}/lib"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                google_keystone_check "{mock_agent}" "com.google.drivefs"
            """
            subprocess.run(["bash", "-c", cmd_drive], capture_output=True, text=True, check=True)

            calls = agent_calls.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(calls), 1, f"Expected agent to be called exactly once, got {len(calls)}")
            self.assertTrue((session_dir / "google_omaha_init.txt").exists(), "google_omaha_init.txt was not created")

    def test_omaha_read_increment_rotation_in_progress(self) -> None:
        """When log rotated while waiting (cur_size < init_size), read tail of .old + all of new."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "updater.log"
            old_file = Path(tmpdir) / "updater.log.old"
            # .old has 150 bytes; byte 101 onwards contains the status
            old_prefix = "A" * 100
            old_status = "STATUS_IN_OLD\n"
            old_file.write_text(old_prefix + old_status, encoding="utf-8")
            # new log has 20 bytes
            new_log = "NEW_HEADER_LINE\n"
            log_file.write_text(new_log, encoding="utf-8")

            cmd = f"""
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                omaha_read_increment "{log_file}" "100"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("STATUS_IN_OLD", res.stdout)
            self.assertIn("NEW_HEADER_LINE", res.stdout)

    def test_google_omaha_shared_deadline(self) -> None:
        """Three apps in one session have total sleep duration bounded by MAC_UPDATE_OMAHA_WAIT."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            sleep_log = Path(tmpdir) / "sleep.log"
            user_log = Path(tmpdir) / "Library/Application Support/Google/GoogleUpdater/updater.log"
            user_log.parent.mkdir(parents=True)
            user_log.touch()

            mock_agent = Path(tmpdir) / "GoogleSoftwareUpdateAgent"
            mock_agent.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            mock_agent.chmod(mock_agent.stat().st_mode | stat.S_IEXEC)

            cmd = f"""
                export HOME="{tmpdir}"
                export MAC_UPDATE_SESSION_DIR="{session_dir}"
                export MAC_UPDATE_GOOGLE_SYS_UPDATER=""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                _LIB_DIR="{REPO_ROOT}/lib"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                MAC_UPDATE_OMAHA_WAIT=4
                sim_now=$(/bin/date +%s)
                date() {{
                    if [ "$1" = "+%s" ]; then
                        echo "$sim_now"
                    else
                        command date "$@"
                    fi
                }}
                sleep() {{
                    echo "$1" >> "{sleep_log}"
                    sim_now=$(( sim_now + $1 ))
                }}
                google_keystone_check "{mock_agent}" "com.google.chrome"
                google_keystone_check "{mock_agent}" "com.google.geminimacos"
                google_keystone_check "{mock_agent}" "com.google.drivefs"
            """
            subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)

            durations = [int(x) for x in sleep_log.read_text(encoding="utf-8").strip().splitlines() if x.isdigit()]
            total_sleep = sum(durations)
            self.assertLessEqual(total_sleep, 4, f"Total sleep was {total_sleep}s, expected <= 4s")

    def test_google_updater_wake_all_priority_over_legacy_agent(self) -> None:
        """When GoogleUpdater exists, it is called with --wake-all and legacy agent is skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_updater = Path(tmpdir) / "Library/Application Support/Google/GoogleUpdater/Current/GoogleUpdater.app/Contents/MacOS/GoogleUpdater"
            user_updater.parent.mkdir(parents=True)
            updater_calls = Path(tmpdir) / "updater_calls.log"
            user_updater.write_text(f"""#!/usr/bin/env bash
echo "$@" >> "{updater_calls}"
exit 0
""", encoding="utf-8")
            user_updater.chmod(user_updater.stat().st_mode | stat.S_IEXEC)

            mock_agent = Path(tmpdir) / "GoogleSoftwareUpdateAgent"
            agent_calls = Path(tmpdir) / "agent_calls.log"
            mock_agent.write_text(f"""#!/usr/bin/env bash
echo "legacy called" >> "{agent_calls}"
exit 0
""", encoding="utf-8")
            mock_agent.chmod(mock_agent.stat().st_mode | stat.S_IEXEC)

            cmd = f"""
                export HOME="{tmpdir}"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                _LIB_DIR="{REPO_ROOT}/lib"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                MAC_UPDATE_OMAHA_WAIT=0
                google_keystone_check "{mock_agent}" "com.google.chrome"
            """
            subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)

            self.assertTrue(updater_calls.exists(), "GoogleUpdater was not called")
            self.assertIn("--wake-all", updater_calls.read_text(encoding="utf-8"))
            self.assertFalse(agent_calls.exists(), "Legacy agent should not have been called when GoogleUpdater exists")

    def test_chrome_versionhistory_precheck_skips_updater(self) -> None:
        """When Chrome installed >= VersionHistory public version, updater is not triggered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chrome_app = Path(tmpdir) / "Google Chrome.app"
            chrome_app.mkdir()
            updater_calls = Path(tmpdir) / "updater.log"

            vh_fixture = (REPO_ROOT / "tests" / "fixtures" / "vendor_feeds" / "versionhistory.json").read_text(encoding="utf-8")
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_curl = bin_dir / "curl"
            mock_curl.write_text(f"""#!/usr/bin/env bash
cat <<'EOF'
{vh_fixture}
EOF
""", encoding="utf-8")
            mock_curl.chmod(mock_curl.stat().st_mode | stat.S_IEXEC)

            cmd = f"""
                export PATH="{bin_dir}:$PATH"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_apps.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                _LIB_DIR="{REPO_ROOT}/lib"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                print_header() {{ :; }}
                print_info() {{ :; }}
                print_step() {{ :; }}
                print_ok() {{ :; }}
                print_warn() {{ :; }}
                internet_msg() {{ printf "$@"; }}
                app_version() {{ echo "154.0.8037.58"; }}
                google_keystone_check() {{ echo "CALLED" >> "{updater_calls}"; return 0; }}

                STATUS_CHROME=""
                iu_google_chrome
                echo "STATUS_CHROME=$STATUS_CHROME"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("STATUS_CHROME=✅ Up to date (154.0.8037.58, Google VersionHistory)", res.stdout)
            self.assertFalse(updater_calls.exists(), "Keystone/Omaha updater should not have been called")

    def test_omaha_recent_proof_recent_noupdate(self) -> None:
        """When no response in window, but updater.log has noupdate within max age, report recent check."""
        import datetime
        now = datetime.datetime.now()
        two_hours_ago = now - datetime.timedelta(hours=2)
        prefix = f"[{1}:{2}:{two_hours_ago.strftime('%m%d/%H%M%S')}.100000:VERBOSE2:test.cc:100]"
        log_line = f'{prefix} {{"response":{{"apps":[{{"appid":"com.google.chrome","status":"ok","updatecheck":{{"status":"noupdate"}}}}]}}}}'

        with tempfile.TemporaryDirectory() as tmpdir:
            user_log = Path(tmpdir) / "updater.log"
            user_log.write_text(log_line + "\n", encoding="utf-8")

            cmd = f"""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                export MAC_UPDATE_GOOGLE_USER_LOG="{user_log}"
                export MAC_UPDATE_GOOGLE_SYS_LOG="/dev/null"
                export MAC_UPDATE_OMAHA_MAX_AGE_H=6
                app_version() {{ echo "153.0.8010.53"; }}
                evaluate_omaha_status "Google Chrome" "/Applications/Google Chrome.app" "" "com.google.chrome"
                echo "STATUS=$INTERNET_LAST_STATUS"
                echo "VERIFIED=$INTERNET_LAST_VERIFIED"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            expected_time = two_hours_ago.strftime("%H:%M")
            self.assertIn(f"STATUS=✅ Up to date (Google updater check at {expected_time})", res.stdout)
            self.assertIn("VERIFIED=1", res.stdout)

    def test_omaha_recent_proof_stale_noupdate_is_unverified(self) -> None:
        """When noupdate is older than max age, report unverified triggered status."""
        import datetime
        now = datetime.datetime.now()
        eight_hours_ago = now - datetime.timedelta(hours=8)
        prefix = f"[{1}:{2}:{eight_hours_ago.strftime('%m%d/%H%M%S')}.100000:VERBOSE2:test.cc:100]"
        log_line = f'{prefix} {{"response":{{"apps":[{{"appid":"com.google.chrome","status":"ok","updatecheck":{{"status":"noupdate"}}}}]}}}}'

        with tempfile.TemporaryDirectory() as tmpdir:
            user_log = Path(tmpdir) / "updater.log"
            user_log.write_text(log_line + "\n", encoding="utf-8")

            cmd = f"""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                curl() {{ return 1; }}
                export MAC_UPDATE_GOOGLE_USER_LOG="{user_log}"
                export MAC_UPDATE_GOOGLE_SYS_LOG="/dev/null"
                export MAC_UPDATE_OMAHA_MAX_AGE_H=6
                app_version() {{ echo "153.0.8010.53"; }}
                evaluate_omaha_status "Google Chrome" "/Applications/Google Chrome.app" "" "com.google.chrome"
                echo "STATUS=$INTERNET_LAST_STATUS"
                echo "VERIFIED=$INTERNET_LAST_VERIFIED"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("STATUS=⏳ Vendor updater triggered (no response recorded)", res.stdout)
            self.assertIn("VERIFIED=0", res.stdout)


if __name__ == "__main__":
    unittest.main()
