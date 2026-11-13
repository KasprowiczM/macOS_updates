"""Coverage is a read-only view of the common resolver, never name ownership."""
import os
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
from inventory_collect import Providers, collect_snapshot, source_result
from source_resolver import resolve_snapshot
from coverage_report import build_coverage_report


class CoverageResolverTests(unittest.TestCase):
    def test_fifty_unknown_bundles_are_one_summary_and_no_errors(self):
        with tempfile.TemporaryDirectory() as root:
            for index in range(50):
                content = Path(root) / ('Agent' + str(index) + '.app') / 'Contents'
                content.mkdir(parents=True)
                (content / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleName':'Agent' + str(index), 'CFBundleIdentifier':'example.agent' + str(index), **({'SUFeedURL':'https://private/?token=secret'} if index < 12 else {})}))
            with patch('subprocess.run', side_effect=AssertionError('no native action')), patch('socket.create_connection', side_effect=AssertionError('no network')):
                snapshot = collect_snapshot([root], Providers(), None)
                report = build_coverage_report(snapshot, {'schema_version':1,'recipes':[]}, [], 'test')
            self.assertEqual(report['installed_unique_count'], 50)
            self.assertEqual(report['possible_updater_count'], 12)
            self.assertEqual(report['errors'], [])
            self.assertEqual(report['automatic_coverage_count'], 0)
            self.assertNotIn('token=secret', repr(report))

    def test_identical_display_name_does_not_select_manager_or_recipe(self):
        with tempfile.TemporaryDirectory() as root:
            contents = Path(root) / 'CapCut.app/Contents'
            contents.mkdir(parents=True)
            (contents / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleName':'CapCut','CFBundleIdentifier':'other.unrelated'}))
            snapshot = collect_snapshot([root], Providers(), None)
            report = build_coverage_report(snapshot, {'schema_version':1,'recipes':[]}, [dict(name='CapCut', adapter_id='brew_cask')], 'test')
            self.assertEqual(report['automatic_coverage_count'], 0)
            rows = [row for rows in report['classifications'].values() for row in rows]
            self.assertEqual(rows[0]['resolution'], resolve_snapshot(snapshot, {'schema_version':1,'recipes':[]})[0])
            self.assertEqual(rows[0]['managed_by'], 'source_unmanaged')

    def test_receipt_source_conflict_and_stale_use_common_resolver(self):
        with tempfile.TemporaryDirectory() as root:
            root = os.path.realpath(root)
            contents = Path(root) / 'CapCut.app/Contents'
            contents.mkdir(parents=True)
            (contents / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'org.example.capcut'}))
            (contents / '_MASReceipt').mkdir()
            (contents / '_MASReceipt/receipt').write_text('not exported')
            app = str(contents.parent)
            receipt = root + '/Cellar/tool/1/INSTALL_RECEIPT.json'
            item = dict(manager='homebrew', source_identity='formula:tool', installed_receipt=receipt,
                        evidence=[dict(kind='homebrew', token='tool', prefix=root, installed_receipt=receipt, artifact_path=app)])
            snapshot = collect_snapshot([root], Providers(list_brew=lambda p:source_result('ok',[item]),brew_prefixes=[root]), None)
            report = build_coverage_report(snapshot, {'schema_version':1,'recipes':[]}, [], 'test')
            self.assertEqual(report['source_conflict_count'], 1)
            self.assertEqual(report['automatic_coverage_count'], 0)
            self.assertEqual(report['classifications']['manual'][0]['resolution']['source'], 'conflict')
            self.assertEqual(len(report['package_classifications']), 1)

    def test_terminal_controls_in_metadata_are_not_printable_rows(self):
        from coverage_report import _display
        self.assertEqual(_display('Agent\x1b[2J\nInjected\u202e'), 'Agent [2J Injected ')
