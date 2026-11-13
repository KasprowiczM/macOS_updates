#!/usr/bin/env python3
"""tests/test_appstore_mas.py — Tests for mas account version gate and macOS 26.x messages."""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class AppStoreMasGateTests(unittest.TestCase):
    def test_mas5_does_not_call_account_and_no_macos26_warning(self):
        from tests._policy_fixtures import PolicyFixture
        with PolicyFixture() as fixture:
            fixture.mas(outdated='')
            result=fixture.run('update_appstore.sh')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue(any(c[0]=='list' for c in fixture.calls()))
            self.assertFalse(any(c[0]=='account' for c in fixture.calls()))
            self.assertNotIn('macOS 26',result.stdout+result.stderr)
            self.assertEqual(fixture.results()[-1]['status'],'current_verified')
    def test_unparseable_native_queue_never_runs_bare_upgrade(self):
        from tests._policy_fixtures import PolicyFixture
        with PolicyFixture() as fixture:
            fixture.mas(outdated='unexpected vendor diagnostic')
            result=fixture.run('update_appstore.sh')
            self.assertEqual(result.returncode,10,result.stdout+result.stderr)
            self.assertFalse(any(c[0]=='upgrade' for c in fixture.calls()))
            self.assertFalse(fixture.results()[-1]['verified'])
    def test_appstore_user_session_retry_diagnostics_and_soft_fail(self):
        from tests._policy_fixtures import PolicyFixture
        with PolicyFixture() as fixture:
            fixture.mas(mutates=False,sudo_mutates=False)
            result=fixture.run('update_appstore.sh')
            self.assertEqual(result.returncode,10,result.stdout+result.stderr)
            upgrades=[c for c in fixture.calls() if c[0]=='upgrade']
            self.assertEqual(upgrades,[['upgrade','123'],['upgrade','123']])
            outcome=fixture.results()[-1]
            self.assertEqual(outcome['name'],'Fixture')
            self.assertEqual(outcome['status'],'update_unverified')
            self.assertFalse(outcome['verified'])
            self.assertIn('TRACK 1 user-session retry',(fixture.session/'appstore_diag.txt').read_text())
