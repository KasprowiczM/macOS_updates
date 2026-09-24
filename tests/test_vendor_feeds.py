#!/usr/bin/env python3
"""tests/test_vendor_feeds.py — tests for vendor feeds parsing, version comparison and config."""

import json
import os
import shutil
import subprocess
import sys
import unittest

# Ensure lib/python is in PYTHONPATH
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_PYTHON = os.path.join(REPO_ROOT, "lib", "python")
if LIB_PYTHON not in sys.path:
    sys.path.insert(0, LIB_PYTHON)

from vendor_feeds import (
    JSON_SELECTORS,
    evaluate_feed,
    normalize_vendor_version,
    omaha_last_status,
    parse_config_line,
    parse_devolutions_productinfo,
    parse_electron_yml,
    parse_sparkle_appcast,
    select_antigravity_ide,
    select_claude_releases,
    select_cursor_update,
    select_proton_releases,
    select_tauri_latest,
    select_warp_channels,
    version_compare,
    version_history_public,
    version_key,
)


class TestVendorFeeds(unittest.TestCase):

    def setUp(self):
        self.fixtures_dir = os.path.join(REPO_ROOT, "tests", "fixtures", "vendor_feeds")

    def _read_fixture(self, filename: str) -> str:
        with open(os.path.join(self.fixtures_dir, filename), "r", encoding="utf-8") as f:
            return f.read()

    def test_normalize_warp_stable_suffix(self):
        self.assertEqual(
            normalize_vendor_version("v0.2026.09.16.08.27.stable_02"),
            "0.2026.09.16.08.27.02",
        )

    def test_normalize_cask_build_suffix(self):
        self.assertEqual(
            normalize_vendor_version("2.7032.0,6c468ab6ed862a68c9555cce34f11186c35f526d"),
            "2.7032.0",
        )

    def test_normalize_parenthesised_build(self):
        self.assertEqual(
            normalize_vendor_version("7.2.1 (88329)"),
            "7.2.1",
        )

    def test_version_compare_three_way(self):
        self.assertEqual(version_compare("1.2", "1.10"), -1)
        self.assertEqual(version_compare("1.2", "1.2"), 0)
        self.assertEqual(version_compare("1.10", "1.2"), 1)
        self.assertIsNone(version_compare("abc", "1.2"))
        self.assertIsNone(version_compare("1.2", "xyz"))

    def test_sparkle_picks_max_not_first(self):
        xml_text = self._read_fixture("rdm_ascending.xml")
        res = parse_sparkle_appcast(xml_text)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "2023.1.12.0")

    def test_sparkle_attribute_form(self):
        xml_text = self._read_fixture("docker_attr.xml")
        res = parse_sparkle_appcast(xml_text)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "4.92.0")

    def test_sparkle_element_form_and_url(self):
        xml_text = self._read_fixture("chatgpt_elements.xml")
        res = parse_sparkle_appcast(xml_text)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "26.917.62051")
        self.assertTrue(res["url"].endswith(".zip"))

    def test_sparkle_filters_beta_channel(self):
        xml_text = self._read_fixture("protonvpn_channels.xml")
        # default channels allows None or stable
        res = parse_sparkle_appcast(xml_text)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "6.5.1")

    def test_sparkle_respects_minimum_system_version(self):
        xml_text = self._read_fixture("chatgpt_elements.xml")
        # When os_version is "12.0" but item requires "13.0", item is skipped
        res = parse_sparkle_appcast(xml_text, os_version="12.0")
        self.assertIsNone(res)

    def test_sparkle_parse_error_returns_none(self):
        res = parse_sparkle_appcast("<invalid xml")
        self.assertIsNone(res)

    def test_select_claude_releases(self):
        data = json.loads(self._read_fixture("claude_releases.json"))
        res = select_claude_releases(data)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "2.7032.0")
        self.assertTrue(res["url"].endswith(".zip"))

    def test_select_cursor_update(self):
        data = json.loads(self._read_fixture("cursor_update.json"))
        res = select_cursor_update(data)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "3.21.18")
        self.assertTrue(res["url"].endswith(".zip"))

    def test_select_warp_channels(self):
        data = json.loads(self._read_fixture("warp_channels.json"))
        res = select_warp_channels(data)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "0.2026.09.16.08.27.02")
        self.assertIsNone(res["url"])

    def test_select_antigravity_ide_version_from_url(self):
        data = json.loads(self._read_fixture("antigravity_ide.json"))
        res = select_antigravity_ide(data)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "2.5.5")
        self.assertEqual(res["checksum_kind"], "sha256hex")
        self.assertEqual(res["checksum"], "33338ced")

    def test_select_tauri_latest(self):
        data = json.loads(self._read_fixture("tauri_latest.json"))
        res = select_tauri_latest(data)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "1.18.32")
        self.assertTrue(res["url"].endswith(".tar.gz"))

    def test_select_proton_releases_ignores_alpha(self):
        data = json.loads(self._read_fixture("proton_version.json"))
        res = select_proton_releases(data)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "1.14.0")
        self.assertEqual(res["checksum_kind"], "sha512hex")

    def test_parse_electron_yml_zip_and_sha512(self):
        text = self._read_fixture("antigravity.yml")
        res = parse_electron_yml(text)
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "2.16.0")
        self.assertTrue(res["url"].endswith(".zip"))
        self.assertEqual(res["checksum_kind"], "sha512b64")
        self.assertTrue(len(res["checksum"]) > 20)

    def test_parse_devolutions_productinfo(self):
        text = self._read_fixture("productinfo.htm")
        res = parse_devolutions_productinfo(text, "RDMMacbin")
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "2026.3.0.5")
        self.assertTrue(res["url"].endswith(".dmg"))
        self.assertEqual(res["checksum_kind"], "sha256hex")
        self.assertEqual(res["checksum"], "945B1D1F")

    def test_omaha_ignores_request_lines(self):
        req_line = '[1:2:0923/094646.062632:VERBOSE2:components/update_client/request_sender.cc:119] Sending Omaha request: {"request":{"apps":[{"appid":"com.google.chrome","updatecheck":{}}]}}'
        self.assertIsNone(omaha_last_status(req_line, "com.google.chrome"))

    def test_omaha_last_response_wins(self):
        log_text = self._read_fixture("googleupdater.log")
        status = omaha_last_status(log_text, "com.google.chrome")
        self.assertEqual(status, "noupdate")
        gemini_status = omaha_last_status(log_text, "com.google.geminimacos")
        self.assertEqual(gemini_status, "noupdate")

    def test_omaha_unknown_appid_none(self):
        log_text = self._read_fixture("googleupdater.log")
        self.assertIsNone(omaha_last_status(log_text, "com.google.nonexistent"))

    def test_version_history_public_prefers_full_rollout(self):
        data = json.loads(self._read_fixture("versionhistory.json"))
        ver = version_history_public(data)
        self.assertEqual(ver, "154.0.8037.58")

    def test_config_file_rows_are_valid(self):
        cfg_path = os.path.join(REPO_ROOT, "config", "vendor_feeds.txt")
        methods_path = os.path.join(REPO_ROOT, "config", "internet_app_methods.txt")
        with open(methods_path, "r", encoding="utf-8") as f:
            valid_apps = {line.split("|")[0].strip() for line in f if line.strip() and not line.startswith("#")}

        with open(cfg_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        valid_rows = 0
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            row = parse_config_line(line_str)
            self.assertIsNotNone(row, f"Row failed to parse: {line_str}")
            self.assertIn(row["app"], valid_apps, f"App not in internet_app_methods: {row['app']}")
            self.assertIn(row["kind"], {"sparkle", "json", "yml", "kv"})
            if row["kind"] == "json":
                self.assertIn(row["arg"], JSON_SELECTORS, f"Unknown json selector: {row['arg']}")
            if row["artifact"] != "-":
                self.assertNotEqual(row["host"], "-", f"Host must not be '-' when artifact != '-': {line_str}")
            valid_rows += 1
        self.assertGreaterEqual(valid_rows, 10)

    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_version_cmp_bash_wrapper(self):
        cmd = """
        SCRIPT_DIR="{REPO_ROOT}"
        . "{REPO_ROOT}/lib/version.sh"
        version_cmp "2.16.0" "2.15.1"
        version_cmp "2023.1.12.0" "2026.3.0.5"
        """.format(REPO_ROOT=REPO_ROOT)
        proc = subprocess.run(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(lines[0], "newer")
        self.assertEqual(lines[1], "older")

    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_vendor_feed_row_exact_match_with_metacharacters(self):
        cmd = f"""
        . "{REPO_ROOT}/lib/vendor_feeds.sh"
        tmp=$(mktemp)
        cat << "EOF" > "$tmp"
# Comment line
Foo+ (Beta)|json|https://example.com/foo|claude|-|example.com
OtherApp|sparkle|https://example.com/sparkle|-|dmg|example.com
EOF
        vendor_feed_config_path() {{ echo "$tmp"; }}

        row_found=$(vendor_feed_row "Foo+ (Beta)")
        rc_found=$?
        row_miss=$(vendor_feed_row "Foo" 2>/dev/null || true)
        rm -f "$tmp"
        echo "FOUND_RC=$rc_found"
        echo "FOUND_ROW=$row_found"
        echo "MISS_ROW=$row_miss"
        """
        proc = subprocess.run(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("FOUND_RC=0", proc.stdout)
        self.assertIn("FOUND_ROW=Foo+ (Beta)|json|https://example.com/foo|claude|-|example.com", proc.stdout)
        lines = [line.strip() for line in proc.stdout.splitlines()]
        self.assertIn("MISS_ROW=", lines)


if __name__ == "__main__":
    unittest.main()
