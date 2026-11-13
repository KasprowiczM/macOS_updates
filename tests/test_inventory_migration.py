import copy
import hashlib
import json
import os
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib', 'python'))
from inventory_collect import Providers, collect_snapshot, source_result
from inventory_store import StoreError, load_snapshot
from inventory_migration import prepare_migration, commit_migration, recover_migration, rebuild_inventory
from inventory_render import render_inventory


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.realpath(self.tmp.name)
        self.apps = os.path.join(self.root, 'apps')
        os.mkdir(self.apps)
        self.state = os.path.join(self.root, 'state')
        self.report = os.path.join(self.root, 'APPLICATIONS.md')
        self.original = b'# Old inventory\r\n\r\nKeep my personal note.\r\n| Ghost | 1234567 |\r\n'
        with open(self.report, 'wb') as f:
            f.write(self.original)
        self.snapshot = collect_snapshot([self.apps], Providers(), None)

    def read(self, path):
        with open(path, 'rb') as f:
            return f.read()

    def proposal(self):
        return prepare_migration(self.original, self.snapshot)

    def test_prepare_preserves_exact_bytes_as_orphan_without_consent(self):
        proposal = self.proposal()
        self.assertEqual(proposal['original_sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(proposal['notes']['orphans'][0]['text'], self.original.decode())
        self.assertEqual(proposal['summary']['consents_created'], 0)
        self.assertEqual(proposal['snapshot']['instances'], [])
        self.assertFalse(os.path.exists(self.state))

    def test_commit_backup_generation_and_idempotent_rebuild(self):
        proposal = self.proposal()
        saved = commit_migration(proposal, self.state, self.report)
        self.assertEqual(saved['generation'], 1)
        backup = os.path.join(self.state, 'migration', proposal['proposal_id'] + '.original')
        self.assertEqual(self.read(backup), self.original)
        notes = json.loads(self.read(os.path.join(self.state, 'inventory-notes.json')))
        self.assertIn('personal note', notes['orphans'][0]['text'])
        report = self.read(self.report)
        self.assertNotIn('| Ghost |', report.decode().split('## Preserved notes')[0])
        second = collect_snapshot([self.apps], Providers(), saved)
        rebuild_inventory(second, self.state, self.report)
        self.assertEqual(load_snapshot(self.state)['generation'], 2)
        self.assertIn('personal note', self.read(self.report).decode())
        self.assertFalse(os.path.exists(os.path.join(self.state, '.migration-journal.json')))

    def test_manual_change_blocks_commit_and_rebuild(self):
        proposal = self.proposal()
        changed = self.original + b'hand edit\n'
        with open(self.report, 'wb') as f:
            f.write(changed)
        with self.assertRaises(StoreError):
            commit_migration(proposal, self.state, self.report)
        self.assertEqual(self.read(self.report), changed)
        self.assertIsNone(load_snapshot(self.state))
        with open(self.report, 'wb') as f:
            f.write(self.original)
        first = commit_migration(proposal, self.state, self.report)
        with open(self.report, 'ab') as f:
            f.write(b'new note')
        with self.assertRaises(StoreError):
            rebuild_inventory(collect_snapshot([self.apps], Providers(), first), self.state, self.report)
        self.assertTrue(self.read(self.report).endswith(b'new note'))

    def test_invalid_schema_partial_and_space_fail_before_report_write(self):
        for mode in ('schema', 'partial', 'space', 'permissions'):
            with self.subTest(mode=mode):
                proposal = self.proposal()
                if mode == 'schema':
                    proposal['snapshot']['schema_version'] = 9
                if mode == 'partial':
                    proposal['snapshot']['sources']['filesystem:' + self.apps] = source_result('partial')
                if mode == 'permissions':
                    os.chmod(self.report, 0o400)
                with patch('inventory_migration.shutil.disk_usage') as usage:
                    usage.return_value.free = 0 if mode == 'space' else 10**10
                    with self.assertRaises(StoreError):
                        commit_migration(proposal, self.state, self.report)
                os.chmod(self.report, 0o600)
                self.assertEqual(self.read(self.report), self.original)

    def test_crash_after_every_durable_write_recovers_original(self):
        labels = []
        with patch('inventory_migration._checkpoint', side_effect=labels.append):
            commit_migration(self.proposal(), self.state, self.report)
        self.assertGreater(len(labels), 6)
        for index, label in enumerate(labels):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                state = os.path.join(os.path.realpath(tmp), 'state')
                report = os.path.join(os.path.realpath(tmp), 'APPLICATIONS.md')
                with open(report, 'wb') as f:
                    f.write(self.original)
                count = [0]
                def crash(point):
                    count[0] += 1
                    if count[0] == index + 1:
                        raise SystemExit('simulated SIGTERM')
                with patch('inventory_migration._checkpoint', side_effect=crash):
                    with self.assertRaises(SystemExit):
                        commit_migration(self.proposal(), state, report)
                recover_migration(state, report)
                if label == 'committed':
                    self.assertEqual(load_snapshot(state)['generation'], 1)
                else:
                    self.assertEqual(self.read(report), self.original)
                    self.assertIsNone(load_snapshot(state))

    def test_pre_replace_report_cas_preserves_racing_human_edit(self):
        def edit(label):
            if label == 'before_report_replace':
                with open(self.report, 'ab') as f:
                    f.write(b'racing note')
        with patch('inventory_migration._checkpoint', side_effect=edit):
            with self.assertRaises(StoreError):
                commit_migration(self.proposal(), self.state, self.report)
        self.assertEqual(self.read(self.report), self.original + b'racing note')
        self.assertIsNone(load_snapshot(self.state))

    def test_fresh_report_has_only_observed_membership(self):
        os.unlink(self.report)
        rebuild_inventory(self.snapshot, self.state, self.report)
        self.assertIn('Local inventory', self.read(self.report).decode())
        self.assertEqual(load_snapshot(self.state)['instances'], [])

    def test_unknown_and_empty_both_keep_notes(self):
        saved = commit_migration(self.proposal(), self.state, self.report)
        for status in ('partial', 'ok'):
            next_snapshot = collect_snapshot([self.apps], Providers(), saved)
            if status == 'partial':
                next_snapshot['sources']['filesystem:' + self.apps] = source_result('partial')
            saved = rebuild_inventory(next_snapshot, self.state, self.report)
            self.assertIn('personal note', self.read(self.report).decode())

    def test_second_generation_crash_restores_bytes_and_policy(self):
        first = commit_migration(self.proposal(), self.state, self.report)
        report_before = self.read(self.report)
        inventory_before = self.read(os.path.join(self.state, 'inventory.json'))
        policy = b'{"schema_version":1,"profile_id":"' + first['profile_id'].encode() + b'","revision":4,"decisions":[]}'
        policy_path = os.path.join(self.state, 'policy.json')
        with open(policy_path, 'wb') as f:
            f.write(policy)
        os.chmod(policy_path, 0o600)
        def crash(label):
            if label == 'report':
                raise SystemExit('crash')
        with patch('inventory_migration._checkpoint', side_effect=crash):
            with self.assertRaises(SystemExit):
                rebuild_inventory(collect_snapshot([self.apps], Providers(), first), self.state, self.report)
        recover_migration(self.state, self.report)
        self.assertEqual(self.read(self.report), report_before)
        self.assertEqual(self.read(os.path.join(self.state, 'inventory.json')), inventory_before)
        self.assertEqual(self.read(policy_path), policy)

    def test_corrupt_and_future_state_fail_closed(self):
        commit_migration(self.proposal(), self.state, self.report)
        before = self.read(self.report)
        for name, data in (('inventory.json', b'{broken'), ('inventory.json', b'{"schema_version":7}'),
                           ('.migration-journal.json', b'{incomplete'),
                           ('.migration-journal.json', b'{"schema_version":9}'),
                           ('inventory-notes.json', b'{"schema_version":9}')):
            path = os.path.join(self.state, name)
            old = self.read(path) if os.path.exists(path) else None
            with open(path, 'wb') as f:
                f.write(data)
            os.chmod(path, 0o600)
            with self.assertRaises(StoreError):
                commit_migration(self.proposal(), self.state, self.report)
            self.assertEqual(self.read(self.report), before)
            if old is None:
                os.unlink(path)
            else:
                with open(path, 'wb') as f:
                    f.write(old)

    def test_concurrent_writer_and_unsafe_files_rejected(self):
        import fcntl
        from inventory_store import locked_state
        with locked_state(self.state):
            with patch('inventory_store.LOCK_TIMEOUT_SECONDS', 0):
                with self.assertRaises(StoreError):
                    commit_migration(self.proposal(), self.state, self.report)
        self.assertEqual(self.read(self.report), self.original)
        os.unlink(self.report)
        os.mkfifo(self.report, 0o600)
        with self.assertRaises(StoreError):
            commit_migration(self.proposal(), self.state, self.report)
        os.unlink(self.report)
        target = os.path.join(self.root, 'target')
        with open(target, 'wb') as f:
            f.write(self.original)
        os.symlink(target, self.report)
        with self.assertRaises(StoreError):
            commit_migration(self.proposal(), self.state, self.report)
        self.assertEqual(self.read(target), self.original)

    def test_human_edit_after_crash_survives_recovery_and_blocks_rebuild(self):
        def crash(label):
            if label == 'report':
                raise SystemExit('crash')
        with patch('inventory_migration._checkpoint', side_effect=crash):
            with self.assertRaises(SystemExit):
                commit_migration(self.proposal(), self.state, self.report)
        with open(self.report, 'ab') as f:
            f.write(b'human after crash')
        modified = self.read(self.report)
        with self.assertRaises(StoreError):
            recover_migration(self.state, self.report)
        self.assertEqual(self.read(self.report), modified)
        self.assertIsNone(load_snapshot(self.state))
        with self.assertRaises(StoreError):
            rebuild_inventory(self.snapshot, self.state, self.report)

    def test_preview_accept_is_explicit_and_unattended_cannot_accept(self):
        from inventory_migration import builder_main
        import contextlib
        import io
        environment = {'MAC_UPDATE_STATE_DIR': self.state, 'MAC_UPDATE_REPORT_PATH': self.report, 'HOME': self.root}
        with patch.dict(os.environ, environment), patch('inventory_migration.collect_local_snapshot', return_value=self.snapshot), patch('app_recipes.load_recipes', return_value={'schema_version':1,'recipes':[]}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(builder_main(self.root, ['--dry-run']), 0)
            self.assertFalse(os.path.exists(self.state))
            self.assertEqual(builder_main(self.root, []), 10)
            self.assertEqual(builder_main(self.root, ['--migration', '--preview']), 0)
            pending = json.loads(self.read(os.path.join(self.state, 'migration', 'pending.json')))
            self.assertEqual(builder_main(self.root, ['--migration', '--accept', pending['proposal_id'], '-y']), 10)
            self.assertEqual(self.read(self.report), self.original)
            self.assertEqual(builder_main(self.root, ['--migration', '--accept', pending['proposal_id']]), 0)
            self.assertEqual(load_snapshot(self.state)['generation'], 1)

    def test_explicit_preview_imports_new_manual_note(self):
        from inventory_migration import preview_migration
        saved = commit_migration(self.proposal(), self.state, self.report)
        with open(self.report, 'ab') as f:
            f.write(b'new handwritten note')
        next_snapshot = collect_snapshot([self.apps], Providers(), saved)
        preview = preview_migration(next_snapshot, self.state, self.report)
        commit_migration(preview, self.state, self.report)
        self.assertIn('new handwritten note', self.read(self.report).decode())

    def test_snapshot_only_writer_cannot_desynchronize_active_generation(self):
        from inventory_store import save_snapshot
        first = commit_migration(self.proposal(), self.state, self.report)
        original = self.read(self.report)
        with self.assertRaises(StoreError):
            save_snapshot(self.state, collect_snapshot([self.apps], Providers(), first), 1)
        self.assertEqual(load_snapshot(self.state), first)
        self.assertEqual(self.read(self.report), original)

    def test_render_uses_shared_resolution_and_seven_languages(self):
        expected = {'en':'Local inventory', 'pl':'Lokalny inwentarz', 'es':'Inventario local',
                    'it':'Inventario locale', 'pt':'Inventário local', 'de':'Lokales Inventar', 'fr':'Inventaire local'}
        for locale, heading in expected.items():
            with self.subTest(locale=locale):
                rendered = render_inventory(self.snapshot, dict(schema_version=1, mapped=[], orphans=[]), locale)
                self.assertIn(heading, rendered)
                self.assertIn('Source' if locale == 'en' else 'source' if locale == 'fr' else {'pl':'Źródło','es':'Origen','it':'Origine','pt':'Origem','de':'Quelle'}[locale], rendered)
        app_path = os.path.join(self.apps, 'Unknown.app', 'Contents')
        os.makedirs(app_path)
        with open(os.path.join(app_path, 'Info.plist'), 'wb') as f:
            plistlib.dump({'CFBundleName':'Unknown', 'CFBundleIdentifier':'test.unknown'}, f)
        snapshot = collect_snapshot([self.apps], Providers(), None)
        rendered = render_inventory(snapshot, dict(schema_version=1, mapped=[], orphans=[]))
        self.assertIn('unknown', rendered)
        self.assertIn('inventory_only', rendered)
        self.assertIn('manual', rendered)

    def test_journal_embedded_unknown_schema_cannot_restore_state(self):
        def crash(label):
            if label == 'inventory.json':
                raise SystemExit('crash')
        with patch('inventory_migration._checkpoint', side_effect=crash):
            with self.assertRaises(SystemExit):
                commit_migration(self.proposal(), self.state, self.report)
        journal_path = os.path.join(self.state, '.migration-journal.json')
        journal = json.loads(self.read(journal_path))
        import base64
        journal['before']['inventory.json'] = base64.b64encode(b'{"schema_version":99}').decode()
        with open(journal_path, 'w') as f:
            json.dump(journal, f)
        inventory_before = self.read(os.path.join(self.state, 'inventory.json'))
        with self.assertRaises(StoreError):
            recover_migration(self.state, self.report)
        self.assertEqual(self.read(os.path.join(self.state, 'inventory.json')), inventory_before)
        self.assertEqual(self.read(self.report), self.original)

    def test_report_cannot_alias_private_state_files(self):
        os.mkdir(self.state, 0o700)
        path = os.path.join(self.state, 'inventory.json')
        proposal = prepare_migration(b'', self.snapshot)
        proposal['original_base64'] = None
        proposal['original_sha256'] = None
        with self.assertRaises(StoreError):
            commit_migration(proposal, self.state, path)
        self.assertFalse(os.path.exists(path))

    def test_sigterm_process_recovery_and_parallel_commit(self):
        import concurrent.futures
        import subprocess
        script = '''
import os, signal, sys
from inventory_migration import commit_migration, prepare_migration
from inventory_collect import collect_snapshot, Providers
import inventory_migration
root, apps, report = sys.argv[1:]
with open(report, 'rb') as f: proposal = prepare_migration(f.read(), collect_snapshot([apps], Providers(), None))
def checkpoint(label):
    if label == 'inventory-notes.json': os.kill(os.getpid(), signal.SIGTERM)
inventory_migration._checkpoint = checkpoint
commit_migration(proposal, root, report)
'''
        env = dict(os.environ, PYTHONPATH=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib', 'python')))
        process = subprocess.run([sys.executable, '-c', script, self.state, self.apps, self.report], env=env, capture_output=True, timeout=10)
        self.assertEqual(process.returncode, -15, process.stderr)
        recover_migration(self.state, self.report)
        self.assertEqual(self.read(self.report), self.original)
        self.assertIsNone(load_snapshot(self.state))
        proposal = self.proposal()
        def commit():
            try:
                commit_migration(proposal, self.state, self.report)
                return True
            except StoreError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: commit(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(load_snapshot(self.state)['generation'], 1)
