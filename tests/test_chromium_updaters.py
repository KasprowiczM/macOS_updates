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

    def test_google_no_response_is_unverified(self) -> None:
        """Empty or unrelated Omaha log results in L_INTERNET_STATUS_UPDATER_TRIGGERED and verified=0."""
        cmd = f"""
            source "{REPO_ROOT}/i18n/lang_en.sh"
            source "{REPO_ROOT}/lib/version.sh"
            source "{REPO_ROOT}/lib/internet_handlers.sh"
            _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
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


if __name__ == "__main__":
    unittest.main()
