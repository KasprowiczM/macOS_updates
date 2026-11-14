"""Self-update tests use only local throw-away Git repositories."""
import os
import io
import json
import contextlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
import toolkit_update as update


def git(*args, cwd=None):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT='0', GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
    return subprocess.run(['git', *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


class ToolkitUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.remote = self.base / 'remote.git'
        self.repo = self.base / 'checkout'
        self.publisher = self.base / 'publisher'
        git('init', '--bare', '--initial-branch=main', str(self.remote))
        git('clone', str(self.remote), str(self.repo))
        (self.repo / 'VERSION').write_text('1.8.0\n')
        (self.repo / '.gitignore').write_text('.mac-update.lock\nprivate/\n')
        git('add', 'VERSION', '.gitignore', cwd=self.repo)
        git('commit', '-m', 'fixture', cwd=self.repo)
        git('--git-dir', str(self.remote), 'fetch', str(self.repo), 'main:refs/heads/main')
        git('clone', str(self.remote), str(self.publisher))
        (self.publisher / 'VERSION').write_text('1.8.1\n')
        (self.publisher / 'new.txt').write_text('fixture\n')
        git('add', 'VERSION', 'new.txt', cwd=self.publisher)
        git('commit', '-m', 'next', cwd=self.publisher)
        git('--git-dir', str(self.remote), 'fetch', str(self.publisher), 'main:refs/heads/main')
        self.state_patch = patch.dict(os.environ, {'MAC_UPDATE_STATE_DIR': str(self.base / 'state')})
        self.state_patch.start()
        self.remote_patch = patch.object(update, 'OFFICIAL_REMOTE', str(self.remote))
        self.remote_patch.start()

    def tearDown(self):
        self.remote_patch.stop()
        self.state_patch.stop()
        self.tmp.cleanup()

    def test_status_and_reason_labels_are_localized_and_keep_codes_out_of_display(self):
        from tui_i18n import LANGUAGES
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                self.assertNotEqual(update.toolkit_status_label('blocked', lang), 'blocked')
                self.assertNotIn('dirty_checkout', update.toolkit_reason_label('dirty_checkout', lang))
                self.assertTrue(update.toolkit_reason_label('unrecognized_failure', lang))
        self.assertNotEqual(update.toolkit_reason_label('dirty_checkout', 'pl'),
                            update.toolkit_reason_label('dirty_checkout', 'en'))

    def test_receipt_reader_rejects_unsafe_and_invalid_files(self):
        path = self.base / 'receipt.json'
        for payload in (b'{bad', b'x' * 65537, b'{"target_sha":"not-a-sha"}'):
            path.write_bytes(payload)
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                update.read_receipt(path)
        path.write_text(json.dumps({'target_sha': 'a' * 40}))
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            update.read_receipt(path)
        path.chmod(0o600)
        link = self.base / 'receipt-link'
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            update.read_receipt(link)
        fifo = self.base / 'receipt-fifo'
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(ValueError):
            update.read_receipt(fifo)
        self.assertEqual(update.read_receipt(path)['target_sha'], 'a' * 40)

    def test_toolkit_marker_and_json_output(self):
        for arguments, prefix in [(['--check'], '@@MAC_UPDATE_TOOLKIT '),
                                  (['--prepare'], '@@MAC_UPDATE_TOOLKIT '),
                                  (['--check', '--json'], '')]:
            out = io.StringIO()
            with patch.dict(os.environ, {'MAC_UPDATE_TUI_CHILD': '1'}), contextlib.redirect_stdout(out):
                self.assertEqual(update.main(self.repo, arguments), 0)
            line = out.getvalue().strip()
            self.assertTrue(line.startswith(prefix))
            value = json.loads(line[len(prefix):])
            self.assertIn(value['status'], ('available', 'ready'))
            self.assertEqual(len(out.getvalue().splitlines()), 1)

    def test_no_forbidden_git_commands_during_update(self):
        with patch.object(update, '_git', wraps=update._git) as invoked:
            review = update.prepare(self.repo)
            self.assertEqual(review['status'], 'ready', review)
            self.assertEqual(update.apply(self.repo, review['receipt'], True)['status'], 'updated')
        for call in invoked.call_args_list:
            args = call.args[0]
            self.assertFalse({'push', 'reset', 'stash'} & set(args), args)

    def test_preview_and_confirmed_fast_forward(self):
        before = git('rev-parse', 'HEAD', cwd=self.repo)
        review = update.prepare(self.repo)
        self.assertEqual(review['status'], 'ready', review)
        self.assertEqual(git('rev-parse', 'HEAD', cwd=self.repo), before)
        self.assertEqual(update.apply(self.repo, review['receipt'])['status'], 'blocked')
        result = update.apply(self.repo, review['receipt'], confirmed=True)
        self.assertEqual(result['status'], 'updated', result)
        self.assertTrue(result['restart_required'])
        self.assertEqual((self.repo / 'VERSION').read_text().strip(), '1.8.1')

    def test_dirty_or_untracked_checkout_is_blocked(self):
        (self.repo / 'VERSION').write_text('private edit\n')
        self.assertIn('dirty_checkout', update.check(self.repo)['reasons'])
        git('checkout', '--', 'VERSION', cwd=self.repo)
        (self.repo / 'local-code.py').write_text('private\n')
        self.assertIn('dirty_checkout', update.prepare(self.repo)['reasons'])

    def test_receipt_is_rechecked_and_lock_is_not_removed(self):
        review = update.prepare(self.repo)['receipt']
        (self.repo / 'new.txt').write_text('user data')
        self.assertEqual(update.apply(self.repo, review, confirmed=True)['status'], 'blocked')
        self.assertEqual((self.repo / 'new.txt').read_text(), 'user data')
        (self.repo / 'new.txt').unlink()
        lock = self.repo / '.mac-update.lock'
        lock.write_text('pid=999999\n')
        self.assertEqual(update.apply(self.repo, review, confirmed=True)['reasons'], ['run_lock_present'])
        self.assertTrue(lock.exists())

    def test_wrong_branch_remote_and_expired_receipt(self):
        review = update.prepare(self.repo)['receipt']
        with patch.object(update.time, 'time', return_value=review['created'] + update.RECEIPT_TTL + 1):
            self.assertEqual(update.apply(self.repo, review, True)['status'], 'blocked')
        git('checkout', '-b', 'other', cwd=self.repo)
        self.assertIn('branch_not_main', update.check(self.repo)['reasons'])
        git('checkout', 'main', cwd=self.repo)
        git('remote', 'set-url', 'origin', 'https://invalid.example/repo', cwd=self.repo)
        self.assertIn('untrusted_origin', update.check(self.repo)['reasons'])

    def test_new_remote_commit_invalidates_preview(self):
        review = update.prepare(self.repo)['receipt']
        (self.publisher / 'new.txt').write_text('new target\n')
        git('add', 'new.txt', cwd=self.publisher)
        git('commit', '-m', 'later', cwd=self.publisher)
        git('--git-dir', str(self.remote), 'fetch', str(self.publisher), 'main:refs/heads/main')
        self.assertIn('preview_changed', update.apply(self.repo, review, True)['reasons'])

    def test_divergent_history_and_untrusted_attributes_are_blocked(self):
        (self.repo / 'local').write_text('local')
        git('add', 'local', cwd=self.repo)
        git('commit', '-m', 'local divergence', cwd=self.repo)
        self.assertIn('not_fast_forward', update.prepare(self.repo)['reasons'])
        (self.repo / '.git/info/attributes').write_text('* filter=unsafe\n')
        self.assertIn('unsafe_git_attributes', update.check(self.repo)['reasons'])

    def test_git_timeout_kills_its_process_group(self):
        process = Mock(pid=12345)
        process.communicate.side_effect = [subprocess.TimeoutExpired('git', 30), (b'', b'')]
        with patch.object(update.subprocess, 'Popen', return_value=process) as spawn, \
             patch.object(update.os, 'killpg') as kill:
            with self.assertRaisesRegex(update.UpdateError, 'git_timeout'):
                update._git(['status'])
        self.assertTrue(spawn.call_args.kwargs['start_new_session'])
        kill.assert_called_once_with(12345, update.signal.SIGKILL)
        self.assertEqual(process.communicate.call_count, 2)

    def test_merge_failure_keeps_exclusive_recovery_lease(self):
        from update_scheduler import pending_sessions
        review = update.prepare(self.repo)['receipt']
        real_git = update._git
        def fail_merge(args, *pos, **kw):
            if args and args[0] == 'merge':
                raise update.UpdateError('git_timeout')
            return real_git(args, *pos, **kw)
        with patch.object(update, '_git', side_effect=fail_merge):
            self.assertEqual(update.apply(self.repo, review, True)['status'], 'failed')
        sessions = pending_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['status'], 'recovery_required')
        self.assertFalse((self.repo / '.mac-update.lock').exists())

    def test_active_scheduler_lease_prevents_apply(self):
        from update_scheduler import claim_action_resources
        review = update.prepare(self.repo)['receipt']
        lease = claim_action_resources({'action_id': 'fixture', 'resources': ['exclusive:fixture'],
                                        'scope_complete': False, 'parallel_safe': False})
        try:
            self.assertEqual(update.apply(self.repo, review, True)['status'], 'failed')
            self.assertFalse((self.repo / 'new.txt').exists())
        finally:
            lease.finish('done', helpers_complete=True)

    def test_ignored_collision_blocks_preview(self):
        (self.publisher / 'private').mkdir()
        (self.publisher / 'private/new').write_text('upstream\n')
        git('add', '-f', 'private/new', cwd=self.publisher)
        git('commit', '-m', 'colliding', cwd=self.publisher)
        git('--git-dir', str(self.remote), 'fetch', str(self.publisher), 'main:refs/heads/main')
        (self.repo / 'private').mkdir()
        (self.repo / 'private/new').write_text('local\n')
        self.assertIn('ignored_path_collision', update.prepare(self.repo)['reasons'])
        self.assertEqual((self.repo / 'private/new').read_text(), 'local\n')


if __name__ == '__main__':
    unittest.main()
