#!/usr/bin/env python3
"""Run-log follow-up 2026-11-10: HyperFrames / Superset / Open Design.

A hidden launch did not make these apps update (HyperFrames sat idle, Open
Design's launcher exited about a second after start, Superset only changed
after the toolkit quit it). HyperFrames and Superset now install direct-only
from their checksummed arm64 zip; Open Design is verify-only and is never
launched or quit. Any toolkit-launched app gets a minimum age before a quit.

Portable: no macOS tools are needed (fake bundles carry a real Info.plist that
lib/python/inventory.py reads with plistlib; zip extraction is stubbed).
"""
from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import isolate_host_tools, shell_env  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from vendor_feeds import evaluate_feed, version_compare  # noqa: E402

HF_SHA = "e54bb97e01045163b8846867d9de00d8d3ab925288100f637ed3c1e328fbecbd"
HF_FEED = {
    "build": "b891",
    "url": "https://static.heygen.ai/hyperframes-oss/desktop/HyperFrames-b891-aa4c36702.zip",
    "sha256": "78f7f55b186108a6c0013c8b457ed67b48f90f63f90fc389bdbba45910c0d8e7",
    "arm64": {
        "url": "https://static.heygen.ai/hyperframes-oss/desktop/HyperFrames-b891-aa4c36702-arm64.zip",
        "sha256": HF_SHA,
        "dmg": {"url": "https://static.heygen.ai/hyperframes-oss/desktop/Install-HyperFrames-arm64-b891.dmg",
                "sha256": "b06437e8b1d96c6a6054291af96043b64e94bd8ccfedf5092253ae37cf5e3e24"},
    },
    "x64": {"url": "https://static.heygen.ai/hyperframes-oss/desktop/HyperFrames-b891-aa4c36702-x64.zip",
            "sha256": "504f0121034fe702f03e7e149fd5267373b0db7fe2380a540cf3a191d50a12b6"},
}
SUPERSET_YML = """version: '2.0.8'
files:
  - url: 'Superset-2.0.8-arm64-mac.zip'
    sha512: 'u7hQNTQL6fRqyZA+MJFHerut2jNl7Qv+CB3ewL8fdeGwT3umKCMse2B5kPem+s5KtwCnpR/1hnB7tCgWzVIG1Q=='
    size: 240866657
  - url: 'Paradev-2.0.8-arm64.dmg'
    sha512: '3ueFDuAwrFbATC6hDCbEdtMvG+O6XydHvNMCa3dNGooSFKMep1R8/aAFOVRosmQU5geqdVLM5MUKvEEKm9cmdw=='
  - url: 'Superset-2.0.8-mac.zip'
    sha512: 'Cdlu7i9gHXlplHm+s2fFEXdxtgda4Rk49juda88A1yTHY+CoOKbHFxQ9qMuPpa0js/Y/oY4N4avJRXsSwXJlgg=='
path: 'Superset-2.0.8-arm64-mac.zip'
sha512: 'u7hQNTQL6fRqyZA+MJFHerut2jNl7Qv+CB3ewL8fdeGwT3umKCMse2B5kPem+s5KtwCnpR/1hnB7tCgWzVIG1Q=='
"""
SUPERSET_FEED_URL = "https://github.com/paradevai/paradev/releases/latest/download/latest-mac.yml"


def read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def make_bundle(parent: Path, name: str, info: dict) -> Path:
    app = parent / f"{name}.app"
    (app / "Contents").mkdir(parents=True, exist_ok=True)
    with open(app / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump(info, fh)
    return app


def hf_info(label: str) -> dict:
    return {"CFBundleIdentifier": "dev.hyperframes.desktop",
            "CFBundleShortVersionString": "0.1.0", "HFBuildLabel": label}


def run_bash(script: str, **env) -> subprocess.CompletedProcess:
    e = isolate_host_tools(shell_env(SCRIPT_DIR=str(REPO_ROOT), **env))
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=e)


class FeedTests(unittest.TestCase):
    def test_hyperframes_selects_arm64_zip_and_sha256(self) -> None:
        res = evaluate_feed("json", json.dumps(HF_FEED), "hyperframes_latest")
        self.assertEqual(res["version"], "b891")
        self.assertEqual(res["url"], HF_FEED["arm64"]["url"])
        self.assertEqual(res["checksum_kind"], "sha256hex")
        self.assertEqual(res["checksum"], HF_SHA)

    def test_hyperframes_without_arm64_checksum_stays_verify_only(self) -> None:
        for arm in (None, {"url": HF_FEED["arm64"]["url"]},
                    {"url": "http://static.heygen.ai/x-arm64.zip", "sha256": HF_SHA},
                    {"url": "https://static.heygen.ai/x-arm64.dmg", "sha256": HF_SHA},
                    {"url": HF_FEED["arm64"]["url"], "sha256": "not-hex"}):
            body = dict(HF_FEED)
            body.pop("arm64")
            if arm is not None:
                body["arm64"] = arm
            res = evaluate_feed("json", json.dumps(body), "hyperframes_latest")
            self.assertEqual(res["version"], "b891")
            self.assertIsNone(res["url"], msg=str(arm))
            self.assertIsNone(res["checksum"])

    def test_build_labels_compare_numerically(self) -> None:
        self.assertEqual(version_compare("b879", "b891"), -1)
        self.assertEqual(version_compare("b1000", "b891"), 1)
        self.assertEqual(version_compare("b891", "b891"), 0)
        out = run_bash(f'. "{REPO_ROOT}/lib/version.sh"; version_cmp b891 b879; version_cmp b891 b1000; version_cmp b891 b891')
        self.assertEqual(out.stdout.split(), ["newer", "older", "equal"], out.stderr)

    def test_superset_selects_arm64_zip_resolved_against_feed(self) -> None:
        res = evaluate_feed("yml", SUPERSET_YML, "-", base_url=SUPERSET_FEED_URL)
        self.assertEqual(res["version"], "2.0.8")
        self.assertEqual(res["url"], "https://github.com/paradevai/paradev/releases/latest/download/Superset-2.0.8-arm64-mac.zip")
        self.assertEqual(res["checksum_kind"], "sha512b64")


class ConfigTests(unittest.TestCase):
    def row(self, app: str) -> list[str]:
        return next(l for l in read("config/vendor_feeds.txt").splitlines() if l.startswith(app + "|")).split("|")

    def test_artifact_hosts_and_policies(self) -> None:
        self.assertEqual(self.row("HyperFrames")[4:6], ["zip", "static.heygen.ai"])
        self.assertEqual(self.row("Superset")[4:6], ["zip", "github.com"])
        self.assertEqual(self.row("Open Design")[4], "-")
        direct_first = [l.strip() for l in read("config/vendor_direct_first.txt").splitlines()
                        if l.strip() and not l.startswith("#")]
        self.assertIn("HyperFrames", direct_first)
        self.assertIn("Superset", direct_first)
        self.assertNotIn("Open Design", direct_first)
        out = run_bash(f'. "{REPO_ROOT}/lib/internet_handlers.sh" 2>/dev/null; '
                       'for a in HyperFrames Superset "Open Design" Cursor; do internet_launch_policy "$a"; done')
        self.assertEqual(out.stdout.split("\n")[:4], ["direct-only", "direct-only", "never-launch", "default"], out.stderr)

    def test_new_strings_exist_in_every_language_and_map_to_codes(self) -> None:
        for lang in ("en", "pl", "de", "es", "fr", "it", "pt"):
            text = read(f"i18n/lang_{lang}.sh")
            self.assertIn("L_INTERNET_STATUS_OPEN_TO_UPDATE_FMT=", text, lang)
            self.assertIn("L_INTERNET_STATUS_FEED_UNREACHABLE_NOLAUNCH=", text, lang)
            out = run_bash(
                f'. "{REPO_ROOT}/i18n/lang_{lang}.sh"; . "{REPO_ROOT}/lib/internet_status.sh"; '
                'internet_status_code "$(printf "$L_INTERNET_STATUS_OPEN_TO_UPDATE_FMT" 0.27.0 0.27.1)"; '
                'internet_status_code "$L_INTERNET_STATUS_FEED_UNREACHABLE_NOLAUNCH"; '
                'internet_status_code "$(printf "$L_INTERNET_STATUS_NEEDS_RESTART_FMT" 1 2)"')
            self.assertEqual(out.stdout.split(), ["behind", "feed_unreachable", "needs_restart"], f"{lang}: {out.stderr}")


class HandlerDecisionTests(unittest.TestCase):
    """internet_handler_vendor_truth with the real launch policy and version reader."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mac_update_20261110_"))
        self.log = self.tmp / "actions"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def probe(self, app: str, bid: str, row: str | None, installed: Path, *, running: bool = False,
              direct_rc: int = 0, new_info: dict | None = None, env: dict | None = None,
              lookup_rc: int = 0) -> tuple[str, list[str]]:
        newplist = self.tmp / "new.plist"
        if new_info is not None:
            with open(newplist, "wb") as fh:
                plistlib.dump(new_info, fh)
        lookup = f'echo "{row}"' if row else f"return {lookup_rc}"
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"
        print_info() {{ :; }}; print_warn() {{ :; }}; print_step() {{ :; }}; print_ok() {{ :; }}
        internet_diag_log() {{ :; }}
        internet_app_bundle_id() {{ echo {bid}; }}
        internet_app_is_running() {{ return {0 if running else 1}; }}
        vendor_feed_lookup() {{ {lookup}; }}
        vendor_feed_state_record() {{ :; }}
        vendor_feed_state_cached_proof() {{ return 1; }}
        silent_launch_app() {{ echo launch >> "{self.log}"; return 0; }}
        internet_app_quit_gracefully() {{ echo quit >> "{self.log}"; }}
        sleep() {{ echo wait >> "{self.log}"; }}
        vendor_direct_install() {{
            echo "direct $*" >> "{self.log}"
            if [ {direct_rc} -eq 0 ] && [ -f "{newplist}" ]; then cp "{newplist}" "{installed}/Contents/Info.plist"; fi
            return {direct_rc}
        }}
        internet_handler_vendor_truth "{app}" "{installed}" "{app}"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "CODE=$(. "{REPO_ROOT}/lib/internet_status.sh"; internet_status_code "$INTERNET_LAST_STATUS")"
        """
        out = run_bash(script, HOME=str(self.tmp / "home"), **(env or {}))
        self.assertEqual(out.returncode, 0, out.stderr)
        actions = self.log.read_text().splitlines() if self.log.exists() else []
        return out.stdout, actions

    HF_ROW = ("b891|https://static.heygen.ai/hyperframes-oss/desktop/HyperFrames-b891-aa4c36702-arm64.zip"
              f"|sha256hex|{HF_SHA}|zip|static.heygen.ai|eligible")
    SS_ROW = ("2.0.8|https://github.com/paradevai/paradev/releases/latest/download/Superset-2.0.8-arm64-mac.zip"
              "|sha512b64|u7hQ==|zip|github.com|eligible")

    def test_hyperframes_installs_direct_without_launch_and_verifies_build_label(self) -> None:
        app = make_bundle(self.tmp, "HyperFrames", hf_info("b879"))
        out, actions = self.probe("HyperFrames", "dev.hyperframes.desktop", self.HF_ROW, app,
                                  new_info=hf_info("b891"))
        self.assertEqual(len(actions), 1, actions)
        self.assertTrue(actions[0].startswith(f"direct {app} https://static.heygen.ai/"), actions)
        self.assertIn(f"zip sha256hex {HF_SHA} static.heygen.ai b891", actions[0])
        self.assertIn("STATUS=✅ Updated to b891", out)
        self.assertIn("CODE=updated", out)

    def test_hyperframes_direct_install_that_lands_nothing_is_not_updated(self) -> None:
        app = make_bundle(self.tmp, "HyperFrames", hf_info("b879"))
        out, actions = self.probe("HyperFrames", "dev.hyperframes.desktop", self.HF_ROW, app)
        self.assertEqual([a.split()[0] for a in actions], ["direct"])
        self.assertIn("CODE=behind", out)

    def test_direct_only_download_failure_never_launches(self) -> None:
        app = make_bundle(self.tmp, "HyperFrames", hf_info("b879"))
        out, actions = self.probe("HyperFrames", "dev.hyperframes.desktop", self.HF_ROW, app, direct_rc=1)
        self.assertEqual([a.split()[0] for a in actions], ["direct"])
        self.assertNotIn("launch", actions)
        self.assertIn("CODE=error_soft", out)

    def test_running_app_is_not_downloaded(self) -> None:
        for name, bid, row, info in (
                ("HyperFrames", "dev.hyperframes.desktop", self.HF_ROW, hf_info("b879")),
                ("Superset", "com.superset.desktop", self.SS_ROW,
                 {"CFBundleIdentifier": "com.superset.desktop", "CFBundleShortVersionString": "2.0.7"})):
            app = make_bundle(self.tmp / name, name, info)
            # A `defaults` stub keeps the installed version readable on Linux CI.
            out, actions = self.probe(name, bid, row, app, running=True,
                                      env={"PATH": self._defaults_stub() + ":" + os.environ.get("PATH", "")})
            self.assertEqual(actions, [], name)
            self.assertIn("CODE=needs_restart", out, name)

    def test_superset_installs_direct_without_launch(self) -> None:
        info = {"CFBundleIdentifier": "com.superset.desktop", "CFBundleShortVersionString": "2.0.7"}
        app = make_bundle(self.tmp, "Superset", info)
        out, actions = self.probe("Superset", "com.superset.desktop", self.SS_ROW, app,
                                  new_info=dict(info, CFBundleShortVersionString="2.0.8"),
                                  env={"PATH": self._defaults_stub() + ":" + os.environ.get("PATH", "")})
        self.assertEqual(len(actions), 1, actions)
        self.assertIn("zip sha512b64 u7hQ== github.com 2.0.8", actions[0])
        self.assertIn("CODE=updated", out)

    def test_direct_only_with_direct_installs_disabled_is_reported_not_launched(self) -> None:
        app = make_bundle(self.tmp, "HyperFrames", hf_info("b879"))
        out, actions = self.probe("HyperFrames", "dev.hyperframes.desktop", self.HF_ROW, app,
                                  env={"MAC_UPDATE_VENDOR_DIRECT": "0"})
        self.assertEqual(actions, [])
        self.assertIn("Open the app to update: b879 → b891", out)

    def test_open_design_behind_is_never_launched_or_quit(self) -> None:
        app = make_bundle(self.tmp, "Open Design", {"CFBundleIdentifier": "io.open-design.desktop",
                                                     "CFBundleShortVersionString": "0.21.1"})
        ns = self.tmp / "home/Library/Application Support/Open Design/launcher/channels/stable/namespaces/release-stable"
        (ns / "state").mkdir(parents=True)
        (ns / "install.json").write_text(json.dumps({"launchPath": str(app)}))
        (ns / "runtime.json").write_text(json.dumps({"active": {"generation": 5, "version": "0.27.0"},
                                                     "lastSuccessful": {"generation": 5, "version": "0.27.0"}}))
        (ns / "state" / "attempt.json").write_text(json.dumps({"generation": 5, "version": "0.27.0"}))
        row = "0.27.1|-|-|-|-|-|eligible"
        out, actions = self.probe("Open Design", "io.open-design.desktop", row, app)
        self.assertEqual(actions, [])
        self.assertIn("Open the app to update: 0.27.0 → 0.27.1", out)
        self.assertIn("CODE=behind", out)
        # The toolkit never writes the vendor's launcher state.
        self.assertTrue((ns / "state" / "attempt.json").exists())

    def test_no_launch_apps_get_no_fallback_launch_on_feed_failure(self) -> None:
        for name in ("Open Design", "HyperFrames", "Superset"):
            app = make_bundle(self.tmp / name.replace(" ", ""), name, {"CFBundleIdentifier": "x.y"})
            out, actions = self.probe(name, "x.y", None, app, lookup_rc=2)
            self.assertEqual(actions, [], name)
            self.assertIn("CODE=feed_unreachable", out, name)
            self.assertIn("app not launched", out, name)

    def _defaults_stub(self) -> str:
        d = self.tmp / "bin"
        d.mkdir(exist_ok=True)
        # `defaults read <bundle>/Contents/Info <key>` from the fake plist (CI has no defaults).
        (d / "defaults").write_text(
            "#!/bin/bash\n"
            '[ "$1" = read ] || exit 1\n'
            'exec python3 -I -c \'import plistlib,sys\nd=plistlib.load(open(sys.argv[1]+".plist","rb"))\n'
            'v=d.get(sys.argv[2])\nsys.exit(1) if v is None else print(v)\' "$2" "$3"\n',
            encoding="utf-8")
        (d / "defaults").chmod(0o755)
        return str(d)


class VendorDirectBuildLabelTests(unittest.TestCase):
    """vendor_direct_install pre-copy check uses the same app_version for both bundles."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mac_update_vd_hf_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def install(self, installed_label: str, candidate_label: str, expected: str) -> tuple[str, bool]:
        installed = make_bundle(self.tmp / "installed", "HyperFrames", hf_info(installed_label))
        src = make_bundle(self.tmp / "src", "HyperFrames", hf_info(candidate_label))
        zpath = self.tmp / "hf.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            for p in src.rglob("*"):
                zf.write(p, p.relative_to(src.parent))
        sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
        copy_log = self.tmp / "copy.log"
        copy_log.unlink(missing_ok=True)
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        print_info() {{ :; }}; print_warn() {{ :; }}
        eval "real_$(declare -f app_version)"
        app_version() {{
            case "$1" in
                /Applications/HyperFrames.app) real_app_version "{installed}" ;;
                *) real_app_version "$1" ;;
            esac
        }}
        fetch_to_file() {{ cp "{zpath}" "$2"; }}
        ditto() {{ [ "$1" = -x ] && python3 -I -c 'import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$3" "$4"; }}
        internet_app_bundle_id() {{ echo dev.hyperframes.desktop; }}
        internet_app_is_running() {{ return 1; }}
        copy_verified_app() {{ real_app_version "$1" > "{copy_log}"; return 0; }}
        vendor_direct_install "/Applications/HyperFrames.app" "https://static.heygen.ai/x-arm64.zip" zip sha256hex "{sha}" static.heygen.ai "{expected}"
        echo "RC=$?"
        """
        out = run_bash(script)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout, copy_log.exists() and copy_log.read_text().strip() == candidate_label

    def test_newer_build_matching_feed_is_copied(self) -> None:
        out, copied = self.install("b879", "b891", "b891")
        self.assertIn("RC=0", out)
        self.assertTrue(copied)

    def test_four_digit_build_is_newer_than_three_digit(self) -> None:
        out, copied = self.install("b999", "b1000", "b1000")
        self.assertIn("RC=0", out)
        self.assertTrue(copied)

    def test_older_or_equal_build_is_refused(self) -> None:
        for installed, cand in (("b891", "b879"), ("b891", "b891")):
            out, copied = self.install(installed, cand, cand)
            self.assertIn("RC=1", out)
            self.assertFalse(copied)

    def test_build_older_than_feed_is_refused(self) -> None:
        out, copied = self.install("b879", "b891", "b1000")
        self.assertIn("RC=1", out)
        self.assertFalse(copied)


class StartupQuitRaceTests(unittest.TestCase):
    """A toolkit-launched app is never asked to quit before MAC_UPDATE_QUIT_MIN_AGE."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mac_update_quitage_"))
        self.session = self.tmp / "session"
        self.session.mkdir()
        self.log = self.tmp / "log"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def quit(self, launched_ago: int | None, min_age: str | None = None) -> list[str]:
        if launched_ago is not None:
            (self.session / "toolkit_launched_at.txt").write_text(
                f"com.other|1\ncom.test.app|{int(time.time()) - launched_ago}\n")
        running = self.tmp / "running"
        running.touch()
        env = {"MAC_UPDATE_SESSION_DIR": str(self.session)}
        if min_age is not None:
            env["MAC_UPDATE_QUIT_MIN_AGE"] = min_age
        script = f"""
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        internet_diag_log() {{ :; }}
        sleep() {{ echo "sleep $1" >> "{self.log}"; }}
        run_with_timeout() {{
            shift
            case "$*" in
                *"to quit"*) echo quit >> "{self.log}"; rm -f "{running}"; echo ;;
                *"is running"*) if [ -f "{running}" ]; then echo true; else echo false; fi ;;
            esac
        }}
        internet_app_quit_gracefully com.test.app; echo "RC=$?"
        """
        out = run_bash(script, **env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("RC=0", out.stdout)
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_fresh_launch_waits_before_first_quit(self) -> None:
        events = self.quit(launched_ago=3)
        self.assertEqual(events[-1], "quit")
        self.assertEqual(len(events), 2, events)
        waited = int(events[0].split()[1])
        self.assertTrue(26 <= waited <= 27, events)

    def test_old_launch_or_unknown_launch_quits_at_once(self) -> None:
        self.assertEqual(self.quit(launched_ago=120), ["quit"])
        self.log.unlink()
        (self.session / "toolkit_launched_at.txt").unlink()
        self.assertEqual(self.quit(launched_ago=None), ["quit"])

    def test_min_age_is_configurable_and_clamped(self) -> None:
        self.assertEqual(self.quit(launched_ago=3, min_age="0"), ["quit"])
        self.log.unlink()
        events = self.quit(launched_ago=0, min_age="9999")
        self.assertEqual(events, ["sleep 300", "quit"])

    def test_silent_launch_records_launch_time(self) -> None:
        script = f"""
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        eval "$(sed -n '/^silent_launch_app()/,/^}}/p' "{REPO_ROOT}/update_internet_apps.sh")"
        internet_app_running_state() {{ echo false; }}
        open() {{ :; }}
        silent_launch_app "Mock" "com.test.app"
        """
        out = run_bash(script, MAC_UPDATE_SESSION_DIR=str(self.session))
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = (self.session / "toolkit_launched_at.txt").read_text().split()
        self.assertEqual(len(rows), 1)
        bid, epoch = rows[0].split("|")
        self.assertEqual(bid, "com.test.app")
        self.assertLessEqual(abs(int(epoch) - time.time()), 60)


if __name__ == "__main__":
    unittest.main()
