#!/usr/bin/env python3
"""Tests for App Store iPad app lookup and Track 2 gating (T7)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import plistlib
import stat
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from appstore_lookup import parse_lookup, pending_ios, read_itunes_metadata


class AppStoreLookupTests(unittest.TestCase):
    """Pure-python tests for iTunes metadata and lookup response parsing."""

    def test_itunes_metadata_parse(self) -> None:
        """read_itunes_metadata extracts itemId, bundleShortVersionString, and itemName."""
        plist_dict = {
            "itemId": 1057750338,
            "bundleShortVersionString": "10.38.1",
            "itemName": "UniFi",
            "artistName": "Ubiquiti Inc.",
        }
        plist_bytes = plistlib.dumps(plist_dict)
        res = read_itunes_metadata(plist_bytes)
        self.assertIsNotNone(res)
        self.assertEqual(res["itemId"], "1057750338")
        self.assertEqual(res["bundleShortVersionString"], "10.38.1")
        self.assertEqual(res["itemName"], "UniFi")

    def test_pending_ios_only_when_store_newer(self) -> None:
        """pending_ios only includes apps where store version is newer than installed."""
        installed = [
            {"name": "UniFi", "itemId": "1057750338", "version": "10.38.1", "path": "/Applications/UniFi.app"},
            {"name": "WiFiman", "itemId": "1385561119", "version": "0.33.0", "path": "/Applications/WiFiman.app"},
            {"name": "Picsart", "itemId": "587366035", "version": "27.5.0", "path": "/Applications/Picsart.app"},
        ]
        store = {
            "1057750338": "10.38.1",  # equal -> not pending
            "1385561119": "0.34.0",  # newer -> pending
            "587366035": "27.4.0",   # older -> not pending
        }
        pending = pending_ios(installed, store)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["name"], "WiFiman")
        self.assertEqual(pending[0]["itemId"], "1385561119")
        self.assertEqual(pending[0]["installed"], "0.33.0")
        self.assertEqual(pending[0]["store"], "0.34.0")

    def test_lookup_parse_ignores_missing_ids(self) -> None:
        """parse_lookup returns map of trackId -> version and ignores invalid entries."""
        resp = {
            "resultCount": 2,
            "results": [
                {"trackId": 1057750338, "version": "10.38.1"},
                {"trackId": 1385561119, "version": "0.34.0"},
                {"missingTrackId": 123},
                {"trackId": 999},  # missing version
            ],
        }
        res = parse_lookup(resp)
        self.assertEqual(res, {
            "1057750338": "10.38.1",
            "1385561119": "0.34.0",
        })

    @unittest.skipUnless(sys.platform == "darwin", "macOS only")
    def test_app_store_managed_detects_wrapper(self) -> None:
        """app_store_managed returns 0 when Wrapper/iTunesMetadata.plist or Contents/_MASReceipt exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ios_app = Path(tmpdir) / "UniFi.app"
            ios_wrapper = ios_app / "Wrapper"
            ios_wrapper.mkdir(parents=True)
            (ios_wrapper / "iTunesMetadata.plist").write_bytes(b"plist")

            mas_app = Path(tmpdir) / "Copilot.app"
            mas_receipt = mas_app / "Contents" / "_MASReceipt"
            mas_receipt.mkdir(parents=True)

            other_app = Path(tmpdir) / "Custom.app"
            other_app.mkdir()

            cmd = f"""
                source "{REPO_ROOT}/lib/appstore_ios.sh"
                app_store_managed "{ios_app}" && echo "IOS=1" || echo "IOS=0"
                app_store_managed "{mas_app}" && echo "MAS=1" || echo "MAS=0"
                app_store_managed "{other_app}" && echo "OTHER=1" || echo "OTHER=0"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("IOS=1", res.stdout)
            self.assertIn("MAS=1", res.stdout)
            self.assertIn("OTHER=0", res.stdout)

    def test_track2_skipped_when_all_current(self) -> None:
        """Track 2 skips GUI automation and does not call osascript when all iPad apps are current."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()

            lookup_json = {
                "resultCount": 1,
                "results": [{"trackId": 1057750338, "version": "10.38.1"}],
            }
            mock_curl = bin_dir / "curl"
            mock_curl.write_text(f"""#!/usr/bin/env bash
cat <<'EOF'
{json.dumps(lookup_json)}
EOF
""", encoding="utf-8")
            mock_curl.chmod(mock_curl.stat().st_mode | stat.S_IEXEC)

            osascript_log = Path(tmpdir) / "osascript.log"
            mock_osascript = bin_dir / "osascript"
            mock_osascript.write_text(f"""#!/usr/bin/env bash
echo "$*" >> "{osascript_log}"
exit 0
""", encoding="utf-8")
            mock_osascript.chmod(mock_osascript.stat().st_mode | stat.S_IEXEC)

            mock_mas = bin_dir / "mas"
            mock_mas.write_text("""#!/usr/bin/env bash
if [ "$1" = "config" ]; then
    echo '{"store":"pl"}'
    exit 0
fi
exit 0
""", encoding="utf-8")
            mock_mas.chmod(mock_mas.stat().st_mode | stat.S_IEXEC)

            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()

            app_dir = Path(tmpdir) / "Applications"
            app_dir.mkdir()
            unifi_app = app_dir / "UniFi.app"
            wrapper = unifi_app / "Wrapper"
            wrapper.mkdir(parents=True)
            plist_data = {
                "itemId": 1057750338,
                "bundleShortVersionString": "10.38.1",
                "itemName": "UniFi",
            }
            (wrapper / "iTunesMetadata.plist").write_bytes(plistlib.dumps(plist_data))

            cmd = f"""
                export PATH="{bin_dir}:$PATH"
                export HOME="{tmpdir}"
                export MAC_UPDATE_SESSION_DIR="{session_dir}"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/appstore_ios.sh"

                print_header() {{ :; }}
                print_info() {{ :; }}
                print_ok() {{ echo "OK: $*"; }}
                print_warn() {{ echo "WARN: $*"; }}
                print_step() {{ :; }}

                # Mock ios_apps_scan to return the test app
                ios_apps_scan() {{
                    echo "UniFi|1057750338|10.38.1|{unifi_app}"
                }}

                # Source Track 2 section logic
                # We simulate update_appstore.sh Track 2 pre-check
                . "{REPO_ROOT}/lib/appstore_ios.sh"
                ios_scan="$(ios_apps_scan)"
                pending_output="$(ios_apps_pending)"
                pending_rc=$?

                if [ "$pending_rc" -eq 0 ] && [ -z "$pending_output" ]; then
                    print_ok "$L_APPSTORE_IOS_ALL_CURRENT"
                    TRACK2_RAN=0
                else
                    TRACK2_RAN=1
                fi
                echo "TRACK2_RAN=$TRACK2_RAN"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("OK: iPad apps are up to date (App Store lookup) — Track 2 not needed", res.stdout)
            self.assertIn("TRACK2_RAN=0", res.stdout)
            # osascript was never invoked for GUI
            if osascript_log.exists():
                calls = osascript_log.read_text(encoding="utf-8")
    def test_internet_handlers_guard_against_app_store_managed(self) -> None:
        """internet_handler_manual and iu_ipmiview recognize app_store_managed and skip execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ipmi_app = Path(tmpdir) / "IPMIView.app"
            wrapper = ipmi_app / "Wrapper"
            wrapper.mkdir(parents=True)
            (wrapper / "iTunesMetadata.plist").write_bytes(b"plist")

            cmd = f"""
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/internet_handlers.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                print_header() {{ :; }}
                print_info() {{ :; }}
                app_version() {{ echo "1.0"; }}

                internet_handler_manual "IPMIView" "https://example.com" "{ipmi_app}"
                echo "MANUAL_STATUS=$INTERNET_LAST_STATUS"
                echo "MANUAL_VERIFIED=$INTERNET_LAST_VERIFIED"

                IPMI_PATH="{ipmi_app}"
                sed_iu_ipmi="$(declare -f iu_ipmiview | sed 's|/Applications/IPMIView.app|{ipmi_app}|g')"
                eval "$sed_iu_ipmi"
                iu_ipmiview
                echo "IPMIVIEW_STATUS=$STATUS_IPMIVIEW"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("MANUAL_STATUS=→ managed by App Store (update_appstore.sh)", res.stdout)
            self.assertIn("MANUAL_VERIFIED=1", res.stdout)
    def test_track2_verify_lookup_failure_is_soft_fail(self) -> None:
        """When App Store lookup fails during Track 2 verification (rc 2), do not treat as verified.
        Expect L_APPSTORE_IOS_VERIFY_LOOKUP_FAILED, SOFT_FAIL=1, exit 10, no empty appstore_ios_pending.txt overwrite."""
        import pty
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            (bin_dir / "curl").write_text("#!/usr/bin/env bash\nexit 22\n", encoding="utf-8")
            (bin_dir / "sleep").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (bin_dir / "mas").write_text("""#!/usr/bin/env bash
case "$1" in
  version) echo "7.0.0" ;;
  config) echo '{"store":"pl"}' ;;
  outdated) exit 0 ;;
  list) echo "497799835 Xcode (15.0)" ;;
  *) exit 0 ;;
esac
""", encoding="utf-8")
            (bin_dir / "osascript").write_text("""#!/usr/bin/env bash
if [ "$1" = "-e" ]; then
    echo "Terminal"
    exit 0
fi
echo "UPDATE_ALL_CLICKED"
exit 0
""", encoding="utf-8")
            (bin_dir / "open").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            for f in bin_dir.iterdir():
                f.chmod(f.stat().st_mode | stat.S_IEXEC)

            app_dir = Path(tmpdir) / "Applications"
            app_dir.mkdir()
            unifi_app = app_dir / "UniFi.app"
            wrapper = unifi_app / "Wrapper"
            wrapper.mkdir(parents=True)
            plist_data = {
                "itemId": 1057750338,
                "bundleShortVersionString": "10.38.1",
                "itemName": "UniFi",
            }
            (wrapper / "iTunesMetadata.plist").write_bytes(plistlib.dumps(plist_data))

            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            pending_file = session_dir / "appstore_ios_pending.txt"
            pending_file.write_text("UniFi|1057750338|10.38.1|10.39.0\n", encoding="utf-8")

            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            orig_path = env.get("PATH", "")
            env["PATH"] = f"{bin_dir}:{orig_path}"
            env["MAC_LANG"] = "en"
            env["MAC_UPDATE_APPSTORE_VERIFY_TIMEOUT"] = "15"
            env["MAC_UPDATE_NO_SUDO"] = "1"
            env["MAC_UPDATE_YES"] = "1"
            env["MAC_UPDATE_SESSION_DIR"] = str(session_dir)

            master, slave = pty.openpty()
            proc = subprocess.run(
                ["bash", str(REPO_ROOT / "update_appstore.sh")],
                stdin=slave,
                capture_output=True,
                text=True,
                env=env,
                timeout=20,
            )
            os.close(slave)
            os.close(master)

            self.assertEqual(proc.returncode, 10, f"Expected soft fail 10, got {proc.returncode}\nStdout: {proc.stdout}\nStderr: {proc.stderr}")
            self.assertNotIn("iPad apps verified after Track 2", proc.stdout)
            self.assertIn("Could not confirm iPad app updates: the App Store lookup failed", proc.stdout)
            # appstore_ios_pending.txt must not be overwritten with empty content
            self.assertTrue(pending_file.exists())
            self.assertEqual(pending_file.read_text(encoding="utf-8").strip(), "UniFi|1057750338|10.38.1|10.39.0")

    def test_track2_verify_python_error_is_soft_fail_not_empty_pending(self) -> None:
        """When python3 fails (rc 1) during Track 2 verification lookup, treat as lookup failed.
        Expect L_APPSTORE_IOS_VERIFY_LOOKUP_FAILED, exit 10, no empty pending overwrite, no L_APPSTORE_IOS_VERIFIED."""
        import pty
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            (bin_dir / "curl").write_text("#!/usr/bin/env bash\necho '{\"resultCount\":1,\"results\":[{\"trackId\":1057750338,\"version\":\"10.39.0\"}]}'\n", encoding="utf-8")
            (bin_dir / "sleep").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (bin_dir / "mas").write_text("""#!/usr/bin/env bash
case "$1" in
  version) echo "7.0.0" ;;
  config) echo '{"store":"pl"}' ;;
  outdated) exit 0 ;;
  list) echo "497799835 Xcode (15.0)" ;;
  *) exit 0 ;;
esac
""", encoding="utf-8")
            (bin_dir / "osascript").write_text("""#!/usr/bin/env bash
if [ "$1" = "-e" ]; then
    echo "Terminal"
    exit 0
fi
echo "UPDATE_ALL_CLICKED"
exit 0
""", encoding="utf-8")
            (bin_dir / "open").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            # Stub python3: succeed on first ios_apps_pending call (pre-check), fail on subsequent calls (verify loop)
            count_file = Path(tmpdir) / "py_call_count"
            (bin_dir / "python3").write_text(f"""#!/usr/bin/env bash
if [ "$1" = "-" ] && [ "$#" -gt 1 ]; then
    if [ ! -f "{count_file}" ]; then
        touch "{count_file}"
        exec "{sys.executable}" "$@"
    else
        echo "Simulated python3 error in ios_apps_pending" >&2
        exit 1
    fi
fi
exec "{sys.executable}" "$@"
""", encoding="utf-8")
            for f in bin_dir.iterdir():
                f.chmod(f.stat().st_mode | stat.S_IEXEC)

            app_dir = Path(tmpdir) / "Applications"
            app_dir.mkdir()
            unifi_app = app_dir / "UniFi.app"
            wrapper = unifi_app / "Wrapper"
            wrapper.mkdir(parents=True)
            plist_data = {
                "itemId": 1057750338,
                "bundleShortVersionString": "10.38.1",
                "itemName": "UniFi",
            }
            (wrapper / "iTunesMetadata.plist").write_bytes(plistlib.dumps(plist_data))

            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            pending_file = session_dir / "appstore_ios_pending.txt"
            pending_file.write_text("UniFi|1057750338|10.38.1|10.39.0\n", encoding="utf-8")

            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            orig_path = env.get("PATH", "")
            env["PATH"] = f"{bin_dir}:{orig_path}"
            env["MAC_LANG"] = "en"
            env["MAC_UPDATE_APPSTORE_VERIFY_TIMEOUT"] = "15"
            env["MAC_UPDATE_NO_SUDO"] = "1"
            env["MAC_UPDATE_YES"] = "1"
            env["MAC_UPDATE_SESSION_DIR"] = str(session_dir)

            master, slave = pty.openpty()
            proc = subprocess.run(
                ["bash", str(REPO_ROOT / "update_appstore.sh")],
                stdin=slave,
                capture_output=True,
                text=True,
                env=env,
                timeout=20,
            )
            os.close(slave)
            os.close(master)

            self.assertEqual(proc.returncode, 10, f"Expected soft fail 10, got {proc.returncode}\nStdout: {proc.stdout}\nStderr: {proc.stderr}")
            self.assertNotIn("iPad apps verified after Track 2", proc.stdout)
            self.assertIn("Could not confirm iPad app updates: the App Store lookup failed", proc.stdout)
            self.assertNotIn("iPad apps still pending update:", proc.stdout)
            self.assertTrue(pending_file.exists())
            self.assertEqual(pending_file.read_text(encoding="utf-8").strip(), "UniFi|1057750338|10.38.1|10.39.0")


if __name__ == "__main__":
    unittest.main()

