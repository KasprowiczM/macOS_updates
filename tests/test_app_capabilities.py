"""New updater signals produce review proposals, never execution authority."""
import json
import os
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
from app_capabilities import detect_capabilities, propose_recipe, redact_proposal, proposal_preview_id, export_proposal
from inventory_collect import Providers, collect_snapshot


class CapabilityTests(unittest.TestCase):
    def test_framework_metadata_is_probable_not_ownership(self):
        for framework in ('sparkle', 'electron_updater', 'squirrel', 'keystone'):
            instance = dict(instance_id='local', bundle_id='org.example.app', path='/fixture/homes/private/App.app', evidence=[dict(kind='framework', name=framework)])
            with patch('subprocess.run', side_effect=AssertionError('execution denied')), patch('socket.create_connection', side_effect=AssertionError('network denied')):
                found = detect_capabilities(instance, {})
                self.assertEqual(found[0]['evidence_grade'], 'probable')
                self.assertFalse(found[0]['network_allowed'])
                self.assertFalse(found[0]['launch_allowed'])
                proposal = propose_recipe(instance, found)
                self.assertTrue(proposal['review_required'])
                self.assertFalse(proposal['executable'])
                self.assertEqual(proposal['verification_state'], 'unreviewed')

    def test_no_feed_is_manual_normal_not_error(self):
        caps = detect_capabilities(dict(evidence=[]), {})
        self.assertEqual(caps, [])
        proposal = propose_recipe(dict(bundle_id='org.example.manual', name='Launcher Agent'), caps)
        self.assertEqual(proposal['suggested_action'], 'manual')
        self.assertFalse(proposal['error'])

    def test_redaction_is_allowlist_and_removes_nested_private_fields(self):
        proposal = propose_recipe(dict(instance_id='local-secret', path='/fixture/homes/alice/App.app', name='alice secret', bundle_id='org.example.app', team_id='ABCD123456'),
                                  detect_capabilities({}, {'SUFeedURL':'https://alice:pass@updates.example/a?token=SECRET#ACCOUNT'}))
        proposal.update(receipt='/fixture/homes/alice/receipt', debug={'token':'SECRET'}, query='ACCOUNT')
        public = redact_proposal(proposal)
        text = json.dumps(public)
        for private in ('alice', 'SECRET', 'ACCOUNT', '/Users', 'receipt', 'local-secret', '?token', 'pass@'):
            self.assertNotIn(private, text)
        self.assertIn('org.example.app', text)
        self.assertIn('ABCD123456', text)
        self.assertIn('synthetic', text)
        self.assertFalse(public['executable'])
        self.assertEqual(public['verification_state'], 'unreviewed')

    def test_export_requires_exact_preview_acceptance_and_never_writes_config(self):
        proposal = propose_recipe(dict(bundle_id='org.example.app'), [])
        with self.assertRaises(ValueError):
            export_proposal(proposal, None)
        with self.assertRaises(ValueError):
            export_proposal(proposal, 'wrong')
        public = export_proposal(proposal, proposal_preview_id(proposal))
        self.assertEqual(public, redact_proposal(proposal))
        changed = dict(proposal, bundle_id='org.example.changed')
        with self.assertRaises(ValueError):
            export_proposal(changed, proposal_preview_id(proposal))

    def test_all_recipe_contract_cases_remain_unreviewed(self):
        proposal = propose_recipe(dict(bundle_id='org.example.app'), [])
        self.assertEqual(set(proposal['required_contract_cases']), {'absent','current','newer','older_feed_regression','offline','bad_signature','wrong_identity','wrong_arch_min_os','running','source_conflict'})
        self.assertEqual(proposal['completed_contract_cases'], [])

    def test_untrusted_ids_and_url_do_not_become_public_recipe_identity(self):
        proposal = propose_recipe(dict(bundle_id='https://x?token=secret', team_id='/fixture/homes/private'), [])
        redacted = redact_proposal(proposal)
        self.assertEqual(redacted['bundle_ids'], [])
        self.assertEqual(redacted['team_ids'], [])

    def test_static_collector_recognizes_squirrel_without_launch(self):
        with tempfile.TemporaryDirectory() as root:
            contents = Path(root) / 'Agent.app/Contents'
            contents.mkdir(parents=True)
            (contents / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'org.example.agent'}))
            (contents / 'Frameworks/Squirrel.framework').mkdir(parents=True)
            snapshot = collect_snapshot([root], Providers(), None)
            caps = detect_capabilities(snapshot['instances'][0], {})
            self.assertEqual(caps[0]['kind'], 'squirrel')

    def test_scripts_preview_export_and_static_scan_are_read_only(self):
        import subprocess
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as root:
            root = Path(root).resolve()
            contents = root / 'apps/Private Agent.app/Contents'
            contents.mkdir(parents=True)
            (contents / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleName':'Private Agent', 'CFBundleIdentifier':'org.example.agent','SUFeedURL':'https://user:secret@private.example/?token=SECRET'}))
            env = dict(os.environ, HOME=str(root),MAC_UPDATE_APP_DIRS=str(root/'apps'),MAC_UPDATE_STATE_DIR=str(root/'state'),MAC_UPDATE_BREW_PREFIXES='',MAC_UPDATE_CLI_PREFIXES='',MAC_LANG='en')
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            tool_log = root / 'unexpected'
            for tool in ('mas','brew','curl','open','osascript','sudo'):
                path = bin_dir / tool
                path.write_text('#!/bin/sh\nprintf unexpected >> "$DENIED_TOOLS_LOG"\nexit 1\n')
                path.chmod(0o755)
            # mas list is a bounded read-only observation; it is unavailable here.
            (bin_dir / 'mas').write_text('#!/bin/sh\nexit 1\n')
            env.update(PATH=str(bin_dir)+os.pathsep+env['PATH'],DENIED_TOOLS_LOG=str(tool_log))
            def run(script,*args):
                return subprocess.run(['bash',str(repo/'scripts'/script),*args],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
            scan = run('scan_update_feeds.sh','--json')
            self.assertEqual(scan.returncode,0,scan.stdout+scan.stderr)
            self.assertEqual(json.loads(scan.stdout)['possible_updaters'],1)
            self.assertNotIn('SECRET',scan.stdout)
            preview = run('scaffold_internet_app.sh',str(contents.parent),'--json')
            self.assertEqual(preview.returncode,0,preview.stdout+preview.stderr)
            data = json.loads(preview.stdout)
            self.assertNotIn(str(root),preview.stdout)
            refused = run('scaffold_internet_app.sh',str(contents.parent),'--json','--export')
            self.assertEqual(refused.returncode,10)
            exported = run('scaffold_internet_app.sh',str(contents.parent),'--json','--export','--accept',data['preview_id'])
            self.assertEqual(exported.returncode,0,exported.stdout+exported.stderr)
            self.assertFalse(json.loads(exported.stdout)['proposal']['executable'])
            for locale in ('en','pl','es','it','pt','de','fr'):
                env['MAC_UPDATE_LANG']=locale
                coverage = run('report_update_coverage.sh')
                self.assertEqual(coverage.returncode,0,coverage.stdout+coverage.stderr)
                self.assertIn('Private Agent',coverage.stdout)
                self.assertNotIn('SECRET',coverage.stdout)
            self.assertFalse(tool_log.exists())
            self.assertFalse((root/'state').exists())
