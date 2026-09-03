"""Regression tests for the defects found in the 2026-08-26 run log.

Each test pins one root cause that made a step report a warning on every run:

  * codex-cli timed out (exit 124) because the vendor installer prompted on
    /dev/tty and was never told to stay non-interactive;
  * Ledger's checksum could never match because the DMG was verified against
    the ZIP's digest;
  * brave-browser was skipped forever by a downgrade guard that compared two
    different version schemes;
  * an auto-appended "🆕" row in APPLICATIONS.md never matched its own app
    again, so the prescan re-reported it as new on every run.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from inventory import norm_name  # noqa: E402


def version_relation(installed: str, candidate: str) -> str:
    """Call app_vs_package_version_relation from lib/version.sh."""
    script = (
        f'source "{REPO_ROOT}/lib/version.sh"; '
        f'app_vs_package_version_relation "{installed}" "{candidate}"'
    )
    out = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


class NativeInstallerNonInteractiveTest(unittest.TestCase):
    """codex's installer blocks on `Start Codex now?` unless told otherwise."""

    def setUp(self) -> None:
        self.source = (REPO_ROOT / "update_npm_cli.sh").read_text(encoding="utf-8")

    def test_codex_gets_the_non_interactive_switch(self) -> None:
        self.assertIn("CODEX_NON_INTERACTIVE=1", self.source)

    def test_native_installer_env_is_applied_to_the_run(self) -> None:
        self.assertRegex(self.source, r"env \$installer_env sh -c")

    def test_installer_stdin_is_detached(self) -> None:
        # T2 (v1.4.4) changed bootstrap to `sh -s latest` — match either form.
        self.assertTrue(
            '| sh\" </dev/null' in self.source
            or '| sh -s latest\" </dev/null' in self.source,
            "Bootstrap sh invocation must redirect stdin away from terminal",
        )

    def test_timeout_exceeds_the_vendor_asset_timeout(self) -> None:
        """The codex installer allows 300s for the release download alone."""
        match = re.search(
            r"^native_installer_timeout\(\) \{.*?^\}", self.source, re.M | re.S
        )
        self.assertIsNotNone(match, "native_installer_timeout() not found")
        with tempfile.NamedTemporaryFile(
            "w", suffix=".sh", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(match.group(0) + "\nnative_installer_timeout\n")
            path = handle.name
        try:
            out = subprocess.run(
                ["bash", path], capture_output=True, text=True, check=True
            )
        finally:
            os.unlink(path)
        self.assertGreater(int(out.stdout.strip()), 300)

    def test_no_native_installer_runs_under_the_old_120s_cap(self) -> None:
        self.assertNotIn("run_with_timeout 120 sh -c", self.source)


class LedgerChecksumPairingTest(unittest.TestCase):
    """The digest must come from the same manifest entry as the download."""

    MANIFEST = (
        "version: 4.17.1\n"
        "files:\n"
        "  - url: ledger-live-desktop-4.17.1-mac.zip\n"
        "    sha512: ZIPDIGEST==\n"
        "    size: 291356343\n"
        "  - url: ledger-live-desktop-4.17.1-mac.dmg\n"
        "    sha512: DMGDIGEST==\n"
        "    size: 299979713\n"
        "path: ledger-live-desktop-4.17.1-mac.zip\n"
        "sha512: ZIPDIGEST==\n"
    )

    def test_parser_pairs_the_dmg_with_its_own_digest(self) -> None:
        entries = re.findall(
            r"-\s+url:\s*(\S+)\s*\n\s+sha512:\s*(\S+)", self.MANIFEST
        )
        dmg = [(u, d) for u, d in entries if u.endswith(".dmg")]
        self.assertEqual(dmg, [("ledger-live-desktop-4.17.1-mac.dmg", "DMGDIGEST==")])

    def test_handler_no_longer_takes_the_first_sha512_in_the_document(self) -> None:
        source = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("re.search(r'sha512:", source)
        self.assertIn("LEDGER_ASSET", source)

    def test_guessed_filename_clears_the_digest(self) -> None:
        """No manifest entry means no digest to check the guess against."""
        source = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(
            encoding="utf-8"
        )
        guess_block = source[source.index('LEDGER_DMG_FILE="ledger-live-desktop-') :]
        self.assertIn('LEDGER_SHA512=""', guess_block[:400])


class CaskVersionSchemeTest(unittest.TestCase):
    """Brave ships the Chromium major in front of the cask's own version."""

    def test_brave_bundle_version_equals_its_cask_version(self) -> None:
        self.assertEqual(version_relation("151.1.93.138", "1.93.138.0"), "current")

    def test_a_real_brave_downgrade_is_still_caught(self) -> None:
        self.assertEqual(version_relation("151.1.93.140", "1.93.138.0"), "newer")

    def test_ordinary_same_scheme_pairs_are_untouched(self) -> None:
        self.assertEqual(version_relation("4.15.0", "4.17.1"), "current")
        self.assertEqual(version_relation("4.18.0", "4.17.1"), "newer")
        self.assertEqual(version_relation("1.2", "1.2.0.0"), "current")

    def test_unparseable_versions_are_reported_as_unknown(self) -> None:
        self.assertEqual(version_relation("nieznana", "1.2.3"), "unknown")

    def test_guard_prefers_homebrews_own_installed_record(self) -> None:
        source = (REPO_ROOT / "update_brew.sh").read_text(encoding="utf-8")
        self.assertIn("cask_recorded_ver", source)
        self.assertIn("app_vs_package_version_relation", source)


class InventoryMarkerTest(unittest.TestCase):
    """A row the toolkit wrote itself must keep matching its application."""

    def test_new_marker_does_not_change_identity(self) -> None:
        self.assertEqual(norm_name("GarageBand 🆕"), norm_name("GarageBand"))

    def test_ordinary_names_are_unchanged(self) -> None:
        self.assertEqual(norm_name("Visual Studio Code"), "visualstudiocode")
        self.assertEqual(norm_name("Antigravity IDE"), "antigravityide")
        self.assertEqual(norm_name("Ledger Live"), "ledgerlive")

    def test_prescan_does_not_shadow_the_canonical_normalizer(self) -> None:
        source = (REPO_ROOT / "update_all.sh").read_text(encoding="utf-8")
        self.assertNotIn("def norm_name(s):", source)


class MauDeferralVerificationTest(unittest.TestCase):
    """A release is only real once the live domain says so."""

    def setUp(self) -> None:
        self.source = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(
            encoding="utf-8"
        )

    def test_removals_are_measured_against_the_live_domain(self) -> None:
        self.assertIn("still_present", self.source)
        self.assertIn("verified_removed", self.source)

    def test_unreleased_deferrals_are_reported_not_claimed_as_cleared(self) -> None:
        self.assertIn("L_INTERNET_MS_DEFERRALS_NOT_RELEASED_FMT", self.source)

    def test_every_language_defines_the_new_keys(self) -> None:
        keys = (
            "L_INTERNET_MS_DEFERRALS_NOT_RELEASED_FMT",
            "L_BREW_CASK_VERSION_SCHEME_INFO_FMT",
            "L_INTERNET_FEED_NOT_MACHINE_READABLE_FMT",
        )
        for lang in sorted((REPO_ROOT / "i18n").glob("lang_*.sh")):
            text = lang.read_text(encoding="utf-8")
            for key in keys:
                self.assertIn(f"{key}=", text, f"{key} missing from {lang.name}")


if __name__ == "__main__":
    unittest.main()
