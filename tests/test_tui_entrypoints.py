import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib/python'))


class RoutingTests(unittest.TestCase):
    def route(self, args=(), tty=True, extra=None, module=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'lib/python').mkdir(parents=True)
            shutil.copy(ROOT / 'lib/platform.sh', root / 'lib/platform.sh')
            if module:
                (root / 'lib/python/terminal_app.py').write_text(
                    'def run(script_dir, initial_view="home"):\n print("VIEW=" + initial_view)\n return 7\n')
            env = os.environ.copy()
            env.update(TERM='xterm', MAC_UPDATE_NONINTERACTIVE='0', MAC_UPDATE_TUI_CHILD='0')
            env.update(extra or {})
            command = ['bash', '-c', '''[() { if [[ $1 == -t ]]; then return ${FAKE_TTY:-1}; fi; builtin [ "$@"; }
SCRIPT_DIR="$1"; shift
if [[ ${TEST_UNUSABLE_PYTHON:-0} = 1 ]]; then
    mac_update_tool_usable() { return 1; }
    python3() { echo PYTHON_WAS_INVOKED; return 1; }
fi
. "$1/lib/tui.sh"; shift
mac_update_tui_route home "$@"; rc=$?
printf 'RESULT=%s STARTED=%s ARGS=' "$rc" "$MAC_UPDATE_TUI_STARTED"
printf '<%s>' "${MAC_UPDATE_TUI_ARGS[@]}"
''', 'test', str(root), str(ROOT), *args]
            env['FAKE_TTY'] = '0' if tty else '1'
            result = subprocess.run(command, input='', capture_output=True, text=True, env=env, timeout=10)
            output = result.stdout + result.stderr
            return output

    def test_bare_tty_dispatches(self):
        output = self.route()
        self.assertIn('VIEW=home', output)
        self.assertIn('RESULT=7 STARTED=1', output)

    def test_flags_and_cli_remain_legacy(self):
        for args in [('--dry-run',), ('--cli', '--plan'), ('--cli', '--tui')]:
            with self.subTest(args=args):
                output = self.route(args)
                self.assertIn('STARTED=0', output)
                self.assertNotIn('VIEW=', output)

    def test_explicit_non_tty_fails(self):
        output = self.route(('--tui',), tty=False)
        self.assertIn('RESULT=2 STARTED=1', output)
        self.assertNotIn('\x1b', output)

    def test_explicit_tui_rejects_other_options(self):
        for flag in ('--dry-run', '--json-summary', '--non-interactive'):
            output = self.route(('--tui', flag))
            self.assertIn('RESULT=2 STARTED=1', output)
            self.assertIn('cannot be combined', output)
            self.assertNotIn('VIEW=', output)

    def test_unusable_python_never_runs_the_shim(self):
        for args, started in [(('--tui',), '1'), ((), '0')]:
            output = self.route(args, extra={'TEST_UNUSABLE_PYTHON': '1'})
            self.assertIn('STARTED=' + started, output)
            self.assertNotIn('PYTHON_WAS_INVOKED', output)
            if args:
                self.assertIn('RESULT=2', output)
            else:
                self.assertIn('Starting CLI', output)

    def test_explicit_unavailable_does_not_fall_back(self):
        for extra, module in [({'TERM': 'dumb'}, True), ({}, False)]:
            output = self.route(('--tui',), extra=extra, module=module)
            self.assertIn('RESULT=2 STARTED=1', output)
            self.assertNotIn('Starting CLI', output)

    def test_messages_cover_all_languages(self):
        for lang in ('en', 'pl', 'de', 'fr', 'es', 'it', 'pt'):
            for args, tty, extra in [(('--tui',), False, {}),
                                     (('--tui', '--dry-run'), True, {}),
                                     (('--tui',), True, {'TERM': 'dumb'}),
                                     ((), True, {'TERM': 'dumb'})]:
                with self.subTest(lang=lang, args=args, extra=extra):
                    output = self.route(args, tty=tty, extra={**extra, 'MAC_UPDATE_LANG': lang})
                    self.assertIn('STARTED=', output)
                    if lang != 'en':
                        self.assertNotIn('Terminal interface unavailable', output)
                        self.assertNotIn('A terminal is required', output)
                        self.assertNotIn('cannot be combined', output)

    def test_child_and_dumb_terminal_fall_back(self):
        self.assertIn('STARTED=0', self.route(extra={'MAC_UPDATE_TUI_CHILD': '1'}))
        output = self.route(extra={'TERM': 'dumb'})
        self.assertIn('unavailable', output)
        self.assertIn('STARTED=0', output)


class MissingHelperTests(unittest.TestCase):
    def test_entrypoints_fail_closed_when_tui_helper_is_missing(self):
        for script, flag in (('update_all.sh', '--doctor'),
                             ('setup.sh', '--inspect'),
                             ('build_inventory.sh', '--dry-run')):
            with self.subTest(script=script), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'lib').mkdir()
                shutil.copy(ROOT / script, root / script)
                env = os.environ.copy()
                env['MAC_UPDATE_TUI_CHILD'] = '1'
                result = subprocess.run(['/bin/bash', str(root / script), flag],
                                        stdin=subprocess.DEVNULL, capture_output=True,
                                        text=True, env=env, timeout=5)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse((root / 'logs').exists())
                self.assertFalse((root / 'APPLICATIONS.md').exists())


class PreferencesTests(unittest.TestCase):
    def test_missing_saved_inventory_fails_without_host_execution(self):
        module = importlib.import_module('plan_orchestration')
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {'MAC_UPDATE_STATE_DIR': tmp}), \
             patch('subprocess.run', side_effect=AssertionError('host execution')), \
             patch('subprocess.Popen', side_effect=AssertionError('host execution')):
            self.assertEqual(module.main('/unused', 'preferences'), 10)

    def test_preferences_does_not_enter_pipeline_and_records_only_choices(self):
        module = importlib.import_module('plan_orchestration')
        plan = {'actions': []}
        with patch.object(module, 'build_preferences_plan', return_value=plan), \
             patch.object(module, 'apply_filters', return_value=plan), \
             patch.object(module, 'review_choices', return_value={}), \
             patch.object(module, 'record_plan_decisions') as record, \
             patch.object(module, 'prepare_run') as prepare:
            self.assertEqual(module.main('/unused', 'preferences'), 0)
            record.assert_not_called()
            prepare.assert_not_called()
        with patch.object(module, 'build_preferences_plan', return_value=plan), \
             patch.object(module, 'apply_filters', return_value=plan), \
             patch.object(module, 'review_choices', return_value={'x': 'reset'}), \
             patch.object(module, 'record_plan_decisions') as record:
            self.assertEqual(module.main('/unused', 'preferences'), 0)
            record.assert_called_once_with(plan, {'x': 'reset'})


if __name__ == '__main__':
    unittest.main()
