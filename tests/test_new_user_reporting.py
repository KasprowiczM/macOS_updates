"""New Mac reporting uses observed installations, never catalog membership."""
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib/python'))
from inventory_sync import legend_rows
from _env import shell_env, isolate_host_tools


class NewUserReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.apps = self.base / 'Applications'
        self.apps.mkdir()
        mocks = self.base / 'bin'
        mocks.mkdir()
        (mocks / 'defaults').write_text('#!/bin/sh\nexit 1\n')
        (mocks / 'defaults').chmod(0o755)
        self.env = isolate_host_tools(shell_env(MAC_LANG='en', MAC_UPDATE_APP_DIRS=self.apps,
                                               MAC_UPDATE_MAU_APP=self.base / 'MAU.app',
                                               PATH=str(mocks) + ':' + os.environ['PATH']))

    def app(self, name, receipt=False):
        contents = self.apps / (name + '.app') / 'Contents'
        contents.mkdir(parents=True)
        with (contents / 'Info.plist').open('wb') as stream:
            plistlib.dump({'CFBundleIdentifier': 'example.' + name,
                          'CFBundleShortVersionString': '1.0'}, stream)
        if receipt:
            (contents / '_MASReceipt').mkdir()
            (contents / '_MASReceipt/receipt').write_text('fixture')

    def shell(self, body):
        prelude = f'SCRIPT_DIR={str(ROOT)!r}\n. "$SCRIPT_DIR/i18n/loader.sh"\n. "$SCRIPT_DIR/lib/internet_apps.sh"\n. "$SCRIPT_DIR/lib/internet_registry.sh"\n. "$SCRIPT_DIR/lib/internet_status.sh"\n'
        prelude += """. "$SCRIPT_DIR/lib/appstore_ios.sh"
internet_app_path() { printf '%s/%s.app\\n' "$MAC_UPDATE_APP_DIRS" "$1"; }
"""
        return subprocess.run(['bash', '-c', prelude + body], env=self.env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)

    def test_empty_inventory_legend_does_not_claim_catalog(self):
        rows = legend_rows(['Ghost|silent_launch|STATUS_GHOST'], set(), set(), [], [], [])
        self.assertNotIn('Ghost', repr(rows))

    def dispatch(self):
        # Replace every action handler AFTER sourcing. A call is observable but inert.
        return self.shell('''
print_warn() { echo "WARNING:$*"; }
while IFS= read -r fn; do
  case "$fn" in iu_*) eval "$fn() { echo CALLED:$fn; }" ;; esac
done < "$SCRIPT_DIR/config/internet_dispatch_order.txt"
internet_dispatch_run_all
''')

    def test_empty_mac_dispatches_no_app_handlers(self):
        result = self.dispatch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('CALLED:', result.stdout)

    def test_unknown_app_does_not_dispatch_catalog(self):
        self.app('UnknownFixture')
        self.assertNotIn('CALLED:', self.dispatch().stdout)

    def test_installed_app_is_dispatched(self):
        self.app('Claude')
        self.assertEqual(self.dispatch().stdout.strip(), 'CALLED:iu_claude')

    def test_mau_special_location_keeps_suite_dispatch(self):
        Path(self.env['MAC_UPDATE_MAU_APP']).mkdir()
        self.assertEqual(self.dispatch().stdout.strip(), 'CALLED:iu_microsoft_365')

    def validate_casks(self, available=True):
        text = (ROOT / 'update_internet_apps.sh').read_text()
        block = text.split('# ── Validate brew_cask entries exist in Homebrew ──', 1)[1].split('# ── Cask Oracle', 1)[0]
        return self.shell('STATUS_CAPCUT="$L_INTERNET_STATUS_MANAGED_BREW"\n'
                          'brew_cask_versions() { return ' + ('0' if available else '1') + '; }\n'
                          + block + '\nprintf "code=%s\\n" "$(internet_status_code "$STATUS_CAPCUT")"\n')

    def test_absent_capcut_does_not_warn_about_cask(self):
        result = self.validate_casks()
        self.assertNotIn('error_soft', result.stdout)

    def test_appstore_capcut_remains_appstore_without_cask(self):
        self.app('CapCut', receipt=True)
        self.assertIn('code=managed_appstore', self.validate_casks().stdout)

    def test_manual_capcut_offers_source_choice_without_claiming_brew(self):
        self.app('CapCut')
        self.assertIn('code=source_unmanaged', self.validate_casks().stdout)

    def test_brew_query_failure_is_source_unavailable(self):
        self.app('CapCut')
        self.assertIn('code=source_unavailable', self.validate_casks(False).stdout)

    def coverage(self, *args):
        return subprocess.run(['bash', str(ROOT / 'scripts/report_update_coverage.sh'), *args],
                              env=self.env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=25)

    def test_default_coverage_hides_uninstalled_catalog_names(self):
        result = self.coverage()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('CapCut', result.stdout)
        self.assertNotIn('Claude', result.stdout)
        self.assertIn('47', result.stdout)

    def test_explicit_catalog_can_show_supported_names(self):
        self.assertIn('CapCut', self.coverage('--show-supported').stdout)

    def test_manual_capcut_coverage_does_not_claim_manager(self):
        self.app('CapCut')
        report = json.loads(self.coverage('--json').stdout)
        rows = [r for group in report['classifications'].values() for r in group]
        self.assertEqual(rows[0]['managed_by'], 'source_unmanaged')

    def test_coverage_recognizes_observed_brew_cask(self):
        self.app('CapCut')
        brew = self.base / 'bin/brew'
        brew.write_text("""#!/bin/sh
case "$*" in
  'list --cask -1') echo capcut ;;
  'info --cask --json=v2 capcut') echo '{"casks":[{"token":"capcut","artifacts":[{"app":["CapCut.app"]}]}]}' ;;
  *) exit 96 ;;
esac
""")
        brew.chmod(0o755)
        report = json.loads(self.coverage('--json').stdout)
        rows = [r for group in report['classifications'].values() for r in group]
        self.assertEqual(rows[0]['managed_by'], 'homebrew_cask:capcut')

    def pipeline(self, kind='absent', brew_available=True):
        # Execute the actual orchestrator and internet step in a disposable repo.
        # All other update stages are explicitly skipped. The fake bundles and
        # command log never share paths with installed applications.
        repo = self.base / 'repo'
        repo.mkdir()
        for directory in ('lib', 'config', 'i18n', 'scripts'):
            shutil.copytree(ROOT / directory, repo / directory,
                            ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('update_all.sh', 'update_internet_apps.sh', 'VERSION'):
            shutil.copy2(ROOT / name, repo / name)
        with (repo / 'lib/internet_apps.sh').open('a') as stream:
            stream.write("\ninternet_app_path() { printf '%s/%s.app\\n' \"$MAC_UPDATE_APP_DIRS\" \"$1\"; }\n")
        with (repo / 'lib/preflight.sh').open('a') as stream:
            stream.write('\npreflight_run_cheap() { return 0; }\n')
        if kind != 'absent':
            self.app('CapCut', receipt=kind == 'mas')
        mocks = self.base / 'bin'
        programs = {
            'uname': 'echo arm64', 'sw_vers': 'echo 27.0',
            'pgrep': 'exit 1', 'mdls': 'echo 1.0',
            'defaults': 'echo 1.0',
            'brew': 'echo "$*" >> "$COMMAND_LOG"; case "$*" in *install*|*upgrade*|*adopt*) exit 96;; esac; exit ' + ('0' if brew_available else '1'),
        }
        for name, body in programs.items():
            path = mocks / name
            path.write_text('#!/bin/sh\n' + body + '\n')
            path.chmod(0o755)
        env = dict(self.env, HOME=str(self.base), MAC_UPDATE_HOMEBREW_PREFIX=str(self.base / 'no-brew'),
                   MAC_UPDATE_NO_CAFFEINATE='1', MAC_UPDATE_NO_SUDO='1', MAC_UPDATE_INTERNET_SETTLE_SECONDS='0',
                   MAC_UPDATE_ROSETTA_DIR=str(self.base / 'no-rosetta'), COMMAND_LOG=str(self.base / 'commands'))
        result = subprocess.run(['bash', str(repo / 'update_all.sh'), '-y', '--non-interactive',
                                 '--skip-prescan', '--skip-appstore', '--skip-npm', '--skip-brew',
                                 '--skip-postupdate', '--skip-system'], cwd=repo, env=env,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
        reports = list((repo / 'logs').glob('run_summary_*.json'))
        self.assertTrue(reports, result.stdout + result.stderr)
        report = json.loads(reports[0].read_text())
        calls = (self.base / 'commands').read_text() if (self.base / 'commands').exists() else ''
        self.assertNotRegex(calls, r'install|upgrade|adopt')
        return result, report

    def test_full_pipeline_empty_mac_is_clean(self):
        result, report = self.pipeline()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(report['degraded'], report)
        self.assertNotIn('cask_missing', json.dumps(report))
        self.assertNotIn('CapCut', result.stdout)
        self.assertNotIn('Claude', result.stdout)

    def test_full_pipeline_mas_capcut_is_not_brew_error(self):
        result, report = self.pipeline('mas')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(report['degraded'], report)
        self.assertIn('App Store', result.stdout)
        self.assertNotIn('cask_missing', json.dumps(report))

    def test_full_pipeline_manual_capcut_suggests_source(self):
        result, report = self.pipeline('manual')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Source not confirmed', result.stdout)
        self.assertNotIn('cask_missing', json.dumps(report))

    def test_full_pipeline_brew_failure_is_soft_and_explicit(self):
        result, report = self.pipeline('manual', brew_available=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report['degraded'], report)
        self.assertIn('Source unavailable', result.stdout)
        self.assertNotIn('cask_missing', json.dumps(report))


if __name__ == '__main__':
    unittest.main()
