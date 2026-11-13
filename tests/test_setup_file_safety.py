"""Consent binds filesystem changes to the previewed regular file or absence."""
import importlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))


class SetupFileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('setup_safety'), 'Safe setup file operations are required')
        self.api = importlib.import_module('setup_safety')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'sudo_local'
        self.sudo = self.root / 'sudo'
        self.sudo.write_text('auth required original.so\n')
        self.desired = '# managed\nauth sufficient pam_tid.so\n'

    def apply(self, mode='install', expected=None):
        if expected is None:
            expected = self.api.fingerprint(self.target)
        return self.api.apply_pam(self.target, self.sudo, mode, expected, self.desired)

    def test_dangling_symlink_is_rejected(self):
        self.target.symlink_to(self.root / 'foreign')
        with self.assertRaises(ValueError):
            self.api.fingerprint(self.target)
        self.assertFalse((self.root / 'foreign').exists())

    def test_fifo_is_rejected_without_opening_it(self):
        os.mkfifo(self.target)
        with self.assertRaises(ValueError):
            self.api.fingerprint(self.target)

    def test_profile_prompt_time_symlink_swap_is_refused(self):
        self.target.write_text('old\n')
        token = self.api.fingerprint(self.target)
        foreign = self.root / 'foreign'
        foreign.write_text('unchanged\n')
        self.target.unlink()
        self.target.symlink_to(foreign)
        with self.assertRaises(ValueError):
            self.api.append_profile(self.target, 'new', token)
        self.assertEqual(foreign.read_text(), 'unchanged\n')

    def test_profile_prompt_time_content_change_is_refused(self):
        self.target.write_text('old\n')
        token = self.api.fingerprint(self.target)
        self.target.write_text('foreign\n')
        with self.assertRaises(ValueError):
            self.api.append_profile(self.target, 'new', token)
        self.assertEqual(self.target.read_text(), 'foreign\n')

    def test_profile_absence_is_bound_to_consent(self):
        token = self.api.fingerprint(self.target)
        self.target.write_text('appeared\n')
        with self.assertRaises(ValueError):
            self.api.append_profile(self.target, 'new', token)
        self.assertEqual(self.target.read_text(), 'appeared\n')

    def test_profile_append_preserves_content_and_mode(self):
        self.target.write_text('old')
        self.target.chmod(0o640)
        self.api.append_profile(self.target, 'new', self.api.fingerprint(self.target))
        self.assertEqual(self.target.read_text(), 'old\nnew\n')
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        self.api.append_profile(self.target, 'new', self.api.fingerprint(self.target))
        self.assertEqual(self.target.read_text(), 'old\nnew\n')

    def test_new_profile_is_private(self):
        self.api.append_profile(self.target, 'new', self.api.fingerprint(self.target))
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)

    def test_pam_created_while_prompt_waits_is_not_overwritten(self):
        token = self.api.fingerprint(self.target)
        self.target.write_text('foreign\n')
        with self.assertRaises(ValueError):
            self.apply(expected=token)
        self.assertEqual(self.target.read_text(), 'foreign\n')

    def test_pam_changed_while_prompt_waits_is_not_removed(self):
        self.target.write_text(self.desired)
        token = self.api.fingerprint(self.target)
        self.target.write_text('foreign\n')
        with self.assertRaises(ValueError):
            self.apply('uninstall', token)
        self.assertEqual(self.target.read_text(), 'foreign\n')

    def test_pam_backup_failure_prevents_creation(self):
        with mock.patch.object(self.api, '_backup', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.apply()
        self.assertFalse(self.target.exists())

    def test_pam_creation_is_exclusive_even_after_validation(self):
        original = os.link
        def create_foreign(source, destination):
            Path(destination).write_text('foreign\n')
            return original(source, destination)
        with mock.patch.object(self.api.os, 'link', side_effect=create_foreign):
            with self.assertRaises(FileExistsError):
                self.apply()
        self.assertEqual(self.target.read_text(), 'foreign\n')
        self.assertEqual(list(self.root.glob('*.stage.*')), [])

    def test_pam_install_and_uninstall_keep_backups(self):
        backup = Path(self.apply())
        self.assertEqual(backup.read_text(), self.sudo.read_text())
        self.assertEqual(self.target.read_text(), self.desired)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o444)
        removed_backup = Path(self.apply('uninstall'))
        self.assertNotEqual(backup, removed_backup)
        self.assertEqual(removed_backup.read_text(), self.desired)
        self.assertFalse(self.target.exists())
