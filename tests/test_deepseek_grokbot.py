"""DeepSeek Harness and Grok Bot: verify-only vendor feeds, native updaters install.

Evidence (2026-11-09): DeepSeek's own electron-updater feed is
<generic url>/nightly-mac.yml (latest-mac.yml answers 404); Grok Bot ships
Cursor's Squirrel.Mac client, product "sand", at api2.cursor.sh/updates.
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import shell_env  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from vendor_feeds import evaluate_feed, version_compare  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "vendor_feeds"
APPS = (
    ("DeepSeek Harness", "iu_deepseek_harness", "STATUS_DEEPSEEK"),
    ("Grok Bot", "iu_grok_bot", "STATUS_GROKBOT"),
)


def read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


class FeedParsingTests(unittest.TestCase):
    def test_deepseek_folded_scalars_parse(self) -> None:
        res = evaluate_feed("yml", (FIXTURES / "deepseek_nightly-mac.yml").read_text(), "-")
        self.assertEqual(res["version"], "0.2.2-rc.1")
        self.assertEqual(
            res["url"],
            "https://download.deepseek.com/dsh-desk/bin/mac-arm64/deepseek-harness-0.2.2-rc.1-mac-arm64.zip",
        )
        self.assertEqual(res["checksum_kind"], "sha512b64")
        self.assertTrue(res["checksum"].endswith("=="))

    def test_plain_yml_scalars_still_parse(self) -> None:
        text = "version: 1.2.3\nfiles:\n  - url: App-1.2.3-arm64.zip\n    sha512: abc=\npath: App-1.2.3-arm64.zip\nsha512: abc=\n"
        res = evaluate_feed("yml", text, "-", base_url="https://h.example/dir/")
        self.assertEqual(res["version"], "1.2.3")
        self.assertTrue(res["url"].endswith("App-1.2.3-arm64.zip"))
        self.assertEqual(res["checksum"], "abc=")

    def test_grok_bot_squirrel_json(self) -> None:
        body = '{"url":"https://downloads.cursor.com/grokbot/stable/darwin-arm64/0.79.3/Grok_Bot_0.79.3.zip","name":"0.79.3"}'
        res = evaluate_feed("json", body, "cursor_update")
        self.assertEqual(res["version"], "0.79.3")
        self.assertIsNone(evaluate_feed("json", "{}", "cursor_update"))

    def test_prerelease_ordering(self) -> None:
        order = ["0.2.2-rc.1", "0.2.2-rc.2", "0.2.2-rc.10", "0.2.2", "0.2.3-rc.1"]
        for lower, higher in zip(order, order[1:]):
            self.assertEqual(version_compare(lower, higher), -1, (lower, higher))
            self.assertEqual(version_compare(higher, lower), 1, (higher, lower))
        self.assertEqual(version_compare("0.2.2-rc.1", "0.2.2-rc.1"), 0)
        self.assertEqual(version_compare("0.2.2-beta.5", "0.2.2-rc.1"), -1)

    def test_shell_and_python_relations_agree(self) -> None:
        pairs = [("0.2.2-rc.1", "0.2.2-rc.1", "current"), ("0.2.2-rc.2", "0.2.2-rc.1", "newer"),
                 ("0.2.2", "0.2.2-rc.1", "newer"), ("0.2.2-rc.3", "0.2.2", "current"),
                 ("0.79.4", "0.79.3", "newer"), ("0.79.3", "0.79.3", "current")]
        for remote, local, expected in pairs:
            out = subprocess.run(
                ["bash", "-c", '. lib/version.sh; internet_version_relation "$1" "$2"', "_", remote, local],
                cwd=REPO_ROOT, capture_output=True, text=True, check=True, env=shell_env(),
            ).stdout.strip()
            self.assertEqual(out, expected, (remote, local))


class RegistrationTests(unittest.TestCase):
    def test_feeds_are_verify_only_and_methods_are_native(self) -> None:
        feeds = read("config/vendor_feeds.txt")
        methods = read("config/internet_app_methods.txt")
        for app, _handler, status in APPS:
            row = next(line for line in feeds.splitlines() if line.startswith(app + "|"))
            self.assertEqual(row.split("|")[4:6], ["-", "-"], msg=f"{app} must not install from the vendor")
            self.assertIn(f"{app}|silent_launch|{status}", methods)
            self.assertIn(app, read("config/internet_apps.txt").splitlines())
            self.assertNotIn("brew_cask", next(l for l in methods.splitlines() if l.startswith(app + "|")))

    def test_handlers_dispatched_and_summarized_in_ai_group(self) -> None:
        order = read("config/internet_dispatch_order.txt").split()
        handlers = read("lib/internet_app_updates.sh")
        main = read("update_internet_apps.sh")
        ai = main[main.index("$L_INTERNET_SECTION_AI"):main.index("$L_INTERNET_SECTION_VPN")]
        for app, handler, status in APPS:
            self.assertIn(handler, order)
            self.assertRegex(handlers, rf"{handler}\(\) \{{\n    internet_dispatch_silent_launch ")
            self.assertIn(f'{status}="$L_INTERNET_STATUS_SKIPPED"', main)
            self.assertEqual(main.count(f'"${status}"'), 2, msg=f"{status}: summary row + failure scan")
            self.assertIn(f'"${status}"', ai)

    def test_dji_assistant_is_retired(self) -> None:
        for rel in ("config/internet_apps.txt", "config/internet_app_methods.txt",
                    "config/internet_dispatch_order.txt", "lib/internet_app_updates.sh",
                    "update_internet_apps.sh", "scripts/report_update_coverage.sh", "lib/internet_apps.sh"):
            self.assertNotIn("DJI", read(rel), rel)
            self.assertNotIn("dji_assistant", read(rel), rel)


class DispatchTests(unittest.TestCase):
    """Fake bundle + stubbed feed fetch/launch: no network, no real app."""

    def run_handler(self, app: str, handler: str, status: str, installed: str | None, feed: str,
                    running: bool = False, dry_run: bool = False) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / f"{app}.app"
            if installed is not None:
                (bundle / "Contents").mkdir(parents=True)
                with open(bundle / "Contents" / "Info.plist", "wb") as fh:
                    plistlib.dump({"CFBundleIdentifier": "test.fixture." + handler,
                                   "CFBundleShortVersionString": installed}, fh)
            (root / "feed").write_text(feed, encoding="utf-8")
            # app_version() reads the bundle with macOS `defaults`; stub it (plistlib)
            # so the handlers see the fixture version on Linux CI too.
            stubs = root / "stubbin"
            stubs.mkdir()
            (stubs / "defaults").write_text(
                "#!/usr/bin/env python3\nimport plistlib, sys\n"
                "a = sys.argv[1:]\n"
                "if len(a) != 3 or a[0] != 'read': sys.exit(1)\n"
                "try:\n"
                "    with open(a[1] + '.plist', 'rb') as fh: v = plistlib.load(fh)[a[2]]\n"
                "except Exception: sys.exit(1)\n"
                "print(v)\n", encoding="utf-8")
            (stubs / "defaults").chmod(0o755)
            launched = root / "launched.log"
            script = f'''
export SCRIPT_DIR="{REPO_ROOT}" MAC_LANG=en MAC_UPDATE_SESSION_DIR="{root}"
export MAC_UPDATE_FEED_STATE_FILE="{root}/feed_state.json" MAC_UPDATE_STAGE_WAIT=0
{"export MAC_UPDATE_DRY_RUN=1" if dry_run else ""}
. lib/platform.sh; . lib/ui.sh; . lib/version.sh; . lib/proc.sh; . lib/vendor_feeds.sh
. lib/internet_apps.sh; . lib/internet_registry.sh; . lib/internet_handlers.sh
. lib/internet_i18n.sh; . lib/internet_status.sh; . i18n/loader.sh
print_header() {{ echo "HEADER $1"; }}
capture_app_path() {{ echo "{bundle}"; }}
vendor_feed_fetch() {{ cp "{root}/feed" "$3"; }}
silent_launch_app() {{ echo "$1" >> "{launched}"; return 0; }}
internet_app_is_running() {{ {"return 0" if running else "return 1"}; }}
. lib/internet_app_updates.sh
{status}="$L_INTERNET_STATUS_SKIPPED"
{handler}
echo "STATUS=${{{status}}}"
'''
            res = subprocess.run(["bash", "-c", script], cwd=REPO_ROOT, capture_output=True, text=True,
                                 env=shell_env(HOME=str(root), PATH=f"{stubs}:{os.environ['PATH']}"), timeout=60)
            self.assertEqual(res.returncode, 0, res.stderr)
            log = launched.read_text() if launched.exists() else ""
            return res.stdout, log

    DEEPSEEK_FEED = (FIXTURES / "deepseek_nightly-mac.yml").read_text()
    GROK_FEED = '{"url":"https://downloads.cursor.com/grokbot/stable/darwin-arm64/0.79.3/Grok_Bot_0.79.3.zip","name":"0.79.3"}'

    def test_not_installed_is_skipped_silently(self) -> None:
        # Generic dispatcher with an app name that cannot exist in /Applications (the
        # handlers' fallback path is fixed there), so the test never sees a real bundle.
        name = "Fixture Absent App"
        out, launched = self.run_handler(
            name, 'internet_dispatch_silent_launch "H" "Fixture Absent App" STATUS_ABSENT "Fixture Absent App"',
            "STATUS_ABSENT", None, "")
        self.assertIn("not installed", out.lower())
        self.assertIn("STATUS=", out)
        self.assertEqual(launched, "")

    def test_current_is_verified_without_launching(self) -> None:
        cases = (("DeepSeek Harness", "iu_deepseek_harness", "STATUS_DEEPSEEK", "0.2.2-rc.1", self.DEEPSEEK_FEED),
                 ("Grok Bot", "iu_grok_bot", "STATUS_GROKBOT", "0.79.3", self.GROK_FEED))
        for app, handler, status, installed, feed in cases:
            out, launched = self.run_handler(app, handler, status, installed, feed)
            self.assertIn("vendor feed", out)
            self.assertIn(installed, out)
            self.assertEqual(launched, "", app)

    def test_behind_is_reported_without_installing_in_dry_run(self) -> None:
        out, launched = self.run_handler("DeepSeek Harness", "iu_deepseek_harness", "STATUS_DEEPSEEK",
                                         "0.2.1", self.DEEPSEEK_FEED, dry_run=True)
        self.assertIn("0.2.2-rc.1", out)
        self.assertEqual(launched, "")

    def test_running_app_is_never_launched_or_replaced(self) -> None:
        out, launched = self.run_handler("Grok Bot", "iu_grok_bot", "STATUS_GROKBOT", "0.78.0",
                                         self.GROK_FEED, running=True)
        self.assertEqual(launched, "")
        self.assertIn("0.79.3", out)


if __name__ == "__main__":
    unittest.main()
