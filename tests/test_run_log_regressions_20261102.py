"""Regressions for the 2026-11-02 run log.

Covers: GROUP 3 rows written with an architecture marker ("HyperFrames [arm64]")
being deleted as uninstalled on the next run; Open Design / HyperFrames /
Superset handled by their native updaters with the vendor feed as truth (and
the version their updater actually ships); KeePassXC's same-version rebuild
2.8.0-1 (macOS 27.2 unlock crash) plus the publisher .DIGEST check.
"""
from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import shell_env  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from inventory import (  # noqa: E402
    app_exists,
    open_design_payload_version,
    strip_inventory_markers,
    vendor_installed_version,
)
from vendor_feeds import (  # noqa: E402
    digest_for,
    dmg_package_revision,
    evaluate_feed,
    version_compare,
)

LANGS = ("en", "pl", "es", "it", "pt", "de", "fr")


def read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def make_bundle(root: Path, name: str, info: dict) -> Path:
    app = root / f"{name}.app"
    (app / "Contents").mkdir(parents=True)
    with open(app / "Contents" / "Info.plist", "wb") as handle:
        plistlib.dump(info, handle)
    return app


def make_od_launcher(home: Path, launch_path: Path, version: str) -> None:
    ns = (home / "Library" / "Application Support" / "Open Design" / "launcher"
          / "channels" / "stable" / "namespaces" / "release-stable")
    ns.mkdir(parents=True)
    (ns / "install.json").write_text(json.dumps({"launchPath": str(launch_path)}))
    (ns / "runtime.json").write_text(json.dumps({"active": {"generation": 4, "version": version}}))


class InventoryMarkerTests(unittest.TestCase):
    def test_markers_are_not_part_of_the_bundle_name(self) -> None:
        self.assertEqual(strip_inventory_markers("HyperFrames [arm64]"), "HyperFrames")
        self.assertEqual(strip_inventory_markers("Superset [arm64] 🆕"), "Superset")
        self.assertEqual(strip_inventory_markers("Fixture Intel App [x86_64-only]"), "Fixture Intel App")

    def test_marked_row_of_an_installed_app_is_not_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "HyperFrames.app").mkdir()
            self.assertTrue(app_exists("HyperFrames [arm64]", aliases={}, app_dirs=(tmp,)))
            self.assertFalse(app_exists("Superset [arm64]", aliases={}, app_dirs=(tmp,)))


NEW_SECTION_MD = """## GRUPA 3 — Internet

### 🆕 Nowo wykryte aplikacje (do skategoryzowania)

| Nazwa | Wersja | Strona aktualizacji |
|-------|-----------|---------------------|
| Open Design | 0.21.1 | — |
> **Uwaga:** Powyższe aplikacje zostały automatycznie wykryte.

### ☁️ Przechowywanie w chmurze

## GRUPA 4 — CLI i Homebrew 🍺

### 4a. Formulae — Narzędzia kluczowe i CLI ⭐

| Pakiet | Wersja | Opis |
|--------|--------|------|
| awk | 20260426 | GNU awk |

### 4b. Formulae — Biblioteki
"""


class NewSectionInsertTests(unittest.TestCase):
    def test_rows_stay_in_the_new_section_without_a_blank_line_before_the_note(self) -> None:
        from inventory import append_rows_to_new_section

        out = append_rows_to_new_section(NEW_SECTION_MD, "| HyperFrames [arm64] | 🆕 | — |\n")
        self.assertIn("| Open Design | 0.21.1 | — |\n| HyperFrames [arm64] | 🆕 | — |\n> **Uwaga:**", out)
        group4 = out[out.index("## GRUPA 4"):]
        self.assertNotIn("HyperFrames", group4)

    def test_empty_table_receives_rows_after_the_separator(self) -> None:
        from inventory import append_rows_to_new_section

        md = NEW_SECTION_MD.replace("| Open Design | 0.21.1 | — |\n", "")
        out = append_rows_to_new_section(md, "| Superset [arm64] | 🆕 | — |\n")
        self.assertIn("|-------|-----------|---------------------|\n| Superset [arm64] | 🆕 | — |\n> **Uwaga:**", out)

    def test_missing_section_returns_none(self) -> None:
        from inventory import append_rows_to_new_section

        self.assertIsNone(append_rows_to_new_section("## GRUPA 3\n\n| a | b | c |\n", "| x | y | z |\n"))

    def test_prescan_dedups_on_table_rows_not_free_text(self) -> None:
        text = read("update_all.sh")
        self.assertIn("unhandled_dedup = [a for a in unhandled if not row_exists(content, a)]", text)
        self.assertNotIn("pattern_nowe", text)


class NativeUpdaterVersionTests(unittest.TestCase):
    def test_open_design_reports_the_active_launcher_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = make_bundle(root, "Open Design", {
                "CFBundleIdentifier": "io.open-design.desktop",
                "CFBundleShortVersionString": "0.21.1",
            })
            make_od_launcher(root / "home", app, "0.26.1")
            self.assertEqual(vendor_installed_version(app, home=str(root / "home")), "0.26.1")

    def test_open_design_payload_of_another_installation_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = make_bundle(root, "Open Design", {"CFBundleIdentifier": "io.open-design.desktop"})
            make_od_launcher(root / "home", root / "elsewhere" / "Open Design.app", "0.26.1")
            self.assertIsNone(open_design_payload_version(app, home=str(root / "home")))

    def test_hyperframes_reports_its_build_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = make_bundle(Path(tmp), "HyperFrames", {
                "CFBundleIdentifier": "dev.hyperframes.desktop",
                "CFBundleShortVersionString": "0.1.0",
                "HFBuildLabel": "b637",
            })
            self.assertEqual(vendor_installed_version(app), "b637")

    def test_other_bundles_keep_their_bundle_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = make_bundle(Path(tmp), "Superset", {
                "CFBundleIdentifier": "com.superset.desktop",
                "CFBundleShortVersionString": "2.0.3",
            })
            self.assertIsNone(vendor_installed_version(app))

    def test_shell_app_version_uses_the_same_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hf = make_bundle(root, "HyperFrames", {
                "CFBundleIdentifier": "dev.hyperframes.desktop",
                "CFBundleShortVersionString": "0.1.0",
                "HFBuildLabel": "b637",
            })
            od = make_bundle(root, "Open Design", {
                "CFBundleIdentifier": "io.open-design.desktop",
                "CFBundleShortVersionString": "0.21.1",
            })
            make_od_launcher(root / "home", od, "0.26.1")
            out = subprocess.run(
                ["bash", "-c", '. lib/version.sh; app_version "$1"; app_version "$2"', "_", str(hf), str(od)],
                cwd=REPO_ROOT, capture_output=True, text=True, check=True,
                env=shell_env(HOME=str(root / "home")),
            ).stdout.split()
            self.assertEqual(out, ["b637", "0.26.1"])
            # Snapshots (UPDATES.md, run summary, inventory) use the same reader.
            snap = subprocess.run(
                ["bash", "-c", '. lib/version.sh; . lib/internet_apps.sh; internet_app_snapshot_version "$1"',
                 "_", str(hf)],
                cwd=REPO_ROOT, capture_output=True, text=True, check=True,
                env=shell_env(HOME=str(root / "home"), SCRIPT_DIR=str(REPO_ROOT)),
            ).stdout.strip()
            self.assertEqual(snap, "b637")


class VendorFeedTests(unittest.TestCase):
    def test_open_design_metadata(self) -> None:
        body = json.dumps({"releaseVersion": "0.26.1", "stableVersion": "0.26.1", "channel": "stable",
                           "dryRun": False, "platforms": {"mac": {"enabled": True}}})
        self.assertEqual(evaluate_feed("json", body, "open_design_metadata")["version"], "0.26.1")
        dry = json.dumps({"releaseVersion": "9.9.9", "dryRun": True})
        self.assertIsNone(evaluate_feed("json", dry, "open_design_metadata"))

    def test_hyperframes_latest(self) -> None:
        body = json.dumps({"build": "b656", "sha": "3393b1d", "arm64": {"url": "https://x/y.zip"}})
        res = evaluate_feed("json", body, "hyperframes_latest")
        self.assertEqual(res["version"], "b656")
        self.assertIsNone(res["url"])
        self.assertEqual(version_compare("b656", "b637"), 1)
        self.assertIsNone(evaluate_feed("json", json.dumps({"build": "latest"}), "hyperframes_latest"))

    def test_feeds_are_verify_only_and_methods_are_native(self) -> None:
        feeds = read("config/vendor_feeds.txt")
        methods = read("config/internet_app_methods.txt")
        for app in ("Open Design", "HyperFrames", "Superset"):
            row = next(line for line in feeds.splitlines() if line.startswith(app + "|"))
            self.assertEqual(row.split("|")[4], "-", msg=f"{app} must not install from the vendor")
            self.assertIn(f"{app}|silent_launch|", methods)
            self.assertIn(app, read("config/internet_apps.txt").splitlines())

    def test_handlers_are_dispatched_and_summarized(self) -> None:
        order = read("config/internet_dispatch_order.txt").split()
        handlers = read("lib/internet_app_updates.sh")
        main = read("update_internet_apps.sh")
        for handler, status in (("iu_opendesign", "STATUS_OPENDESIGN"),
                                ("iu_hyperframes", "STATUS_HYPERFRAMES"),
                                ("iu_superset", "STATUS_SUPERSET")):
            self.assertIn(handler, order)
            self.assertRegex(handlers, rf"{handler}\(\) \{{\n    internet_dispatch_silent_launch ")
            self.assertIn(f'{status}="$L_INTERNET_STATUS_SKIPPED"', main)
            self.assertEqual(main.count(f'"${status}"'), 2, msg=f"{status}: summary row + failure scan")


RELEASE = {
    "tag_name": "2.8.0",
    "assets": [
        {"name": "KeePassXC-2.8.0-arm64.dmg", "updated_at": "2026-10-21T20:45:50Z"},
        {"name": "KeePassXC-2.8.0-1-arm64.dmg", "updated_at": "2026-10-23T22:32:33Z"},
        {"name": "KeePassXC-2.8.0-1-arm64.dmg.DIGEST", "updated_at": "2026-10-23T22:32:34Z"},
        {"name": "KeePassXC-2.8.0-1-x86_64.dmg", "updated_at": "2026-10-23T22:33:00Z"},
    ],
}


class KeePassXCRebuildTests(unittest.TestCase):
    def test_highest_package_revision_is_selected(self) -> None:
        best = dmg_package_revision(RELEASE, "KeePassXC", "2.8.0", "arm64")
        self.assertEqual(best["name"], "KeePassXC-2.8.0-1-arm64.dmg")
        self.assertEqual(best["revision"], 1)
        self.assertEqual(best["updated_epoch"], 1792794753)

    def test_release_without_rebuild_has_revision_zero(self) -> None:
        release = {"assets": [{"name": "KeePassXC-2.7.12-arm64.dmg", "updated_at": "2026-03-10T01:16:42Z"}]}
        self.assertEqual(dmg_package_revision(release, "KeePassXC", "2.7.12", "arm64")["revision"], 0)

    def test_digest_lookup(self) -> None:
        text = "85f0e75e258ef513f0fc7f5bf470cad0943b7d7e8191b2171f9898ad32e62b9c  KeePassXC-2.8.0-1-arm64.dmg\n"
        self.assertEqual(digest_for(text, "KeePassXC-2.8.0-1-arm64.dmg"), text.split()[0])
        self.assertIsNone(digest_for(text, "KeePassXC-2.8.0-arm64.dmg"))
        self.assertIsNone(digest_for("", "KeePassXC-2.8.0-1-arm64.dmg"))

    def test_handler_verifies_digest_and_allows_equal_version_only_for_rebuild(self) -> None:
        body = re.search(r"\niu_keepassxc\(\) \{(.*?)\n\}\n", read("lib/internet_app_updates.sh"), re.S).group(1)
        self.assertNotIn("TODO(H5)", body)
        self.assertIn("keepassxc_digest_ok", body)
        self.assertIn("github_rebuild_asset", body)
        self.assertRegex(body, r'if \[ -n "\$KPX_REBUILD" \] && \[ "\$KPX_SOURCE_VER" = "\$VER" \]')

    def test_rebuild_decision_settles_after_one_install(self) -> None:
        """ditto keeps the DMG's creation time (22:02 UTC, before the 22:32 upload),
        so without the recorded revision every run would reinstall 2.8.0-1."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            (root / "release.json").write_text(json.dumps(RELEASE))
            curl = bindir / "curl"
            curl.write_text(
                '#!/bin/sh\nout=""; prev=""\nfor a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done\n'
                f'cat "{root / "release.json"}" > "$out"\nprintf 200\n')
            curl.chmod(0o755)
            # `stat -f %B` (bundle birth time) is BSD-only; GNU stat treats -f as
            # filesystem status. Stub it so the logic runs the same on Linux CI.
            stat = bindir / "stat"
            stat.write_text('#!/bin/sh\ncase "$*" in "-f %B"*) date +%s ;; *) exec /usr/bin/env -u PATH stat "$@" ;; esac\n')
            stat.chmod(0o755)
            app = root / "KeePassXC.app"
            app.mkdir()
            script = (
                '. lib/github_release.sh\n'
                'check() { github_rebuild_asset keepassxreboot/keepassxc 2.8.0 KeePassXC 2.8.0 arm64 "$1"; echo "|"; }\n'
                'check "$1"\n'
                'package_revision_record KeePassXC 2.8.0 1\n'
                'check "$1"\n'
                'package_revision_record KeePassXC 2.8.0 0\n'
                'check "$1"\n'
            )
            out = subprocess.run(
                ["bash", "-c", script, "_", str(app)],
                cwd=REPO_ROOT, capture_output=True, text=True, check=True,
                env=shell_env(PATH=f"{bindir}:{os.environ['PATH']}",
                              MAC_UPDATE_PACKAGE_REVISION_FILE=str(root / "state" / "rev.tsv")),
            ).stdout
            # Fresh bundle (created now, after the upload) and no record: current.
            # Recorded revision 1: current. Recorded revision 0: rebuild is newer.
            self.assertEqual([part.strip() for part in out.split("|")][:3],
                             ["", "", "KeePassXC-2.8.0-1-arm64.dmg"])
            self.assertEqual((root / "state" / "rev.tsv").read_text(), "KeePassXC|2.8.0|0\n")
            self.assertEqual((root / "state" / "rev.tsv").stat().st_mode & 0o777, 0o600)

    def test_new_strings_are_localized(self) -> None:
        for lang in LANGS:
            text = read(f"i18n/lang_{lang}.sh")
            for key in ("L_INTERNET_KEEPASSXC_REBUILD_FMT", "L_INTERNET_DIGEST_MISMATCH_FMT"):
                m = re.search(rf'^{key}="([^"]+)"$', text, re.M)
                self.assertIsNotNone(m, msg=f"{key} missing in {lang}")
                self.assertEqual(m.group(1).count("%s"), 2 if "REBUILD" in key else 1)


if __name__ == "__main__":
    unittest.main()
