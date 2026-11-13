import copy
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'lib/python'))
import update_transaction as tx

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.tmp.name).resolve()
        self.dest=self.root/'apps'/'Example.app'; self.dest.mkdir(parents=True); (self.dest/'version').write_text('1')
        self.source=self.root/'source.app'; self.source.mkdir(); (self.source/'version').write_text('2')
        self.action={'action_id':'action-1','target':{'kind':'app','id':'instance'},'target_path':str(self.dest),'action_scope':'direct_update','adapter_id':'github_dmg','expected_target':{'bundle_id':'org.example','team_id':'TEAM','channel':'stable'}}
        self.current={'path':str(self.dest),'presence':'present','freshness':'fresh','running':False,'bundle_id':'org.example','team_id':'TEAM','channel':'stable'}
        self.journals=self.root/'state'/'transactions'; self.journals.mkdir(parents=True)
        self.journals.chmod(0o700); self.journals.parent.chmod(0o700)
        self.platform_patch=patch.object(tx,'sys_platform_darwin',return_value=False); self.platform_patch.start()
    def tearDown(self): self.platform_patch.stop(); self.tmp.cleanup()
    def observe(self,path):
        if not pathlib.Path(path).is_dir(): return {'good':False,'running':False}
        return {'good':True,'receipt_present':False,'running':False,'bundle_id':'org.example','team_id':'TEAM','version':(pathlib.Path(path)/'version').read_text(),'architectures':['arm64'],'minimum_os':'13.0','host_os':'26.0'}
    def run_tx(self, **kwargs):
        return tx.execute_transaction(self.action,str(self.source),str(self.journals),lambda:copy.deepcopy(self.current),lambda:True,self.observe,allowed_roots=[str(self.dest.parent)],**kwargs)
    def test_real_swap_and_private_journal(self):
        result=self.run_tx(); self.assertEqual(result['state'],'verified'); self.assertEqual((self.dest/'version').read_text(),'2')
        journal=pathlib.Path(result['journal_path']); self.assertEqual(journal.stat().st_mode & 0o777,0o600)
        self.assertEqual(json.loads(journal.read_text())['state'],'verified')
    def test_absolute_existing_destination_required(self):
        for path in ['Example.app',str(self.root/'missing.app')]:
            action=dict(self.action,target_path=path)
            with self.assertRaises(tx.TransactionDeferred): tx.prepare_transaction(action,self.current)
    def test_removed_during_download_never_reinstalled(self):
        shutil.rmtree(self.dest)
        with self.assertRaises(tx.TransactionDeferred): self.run_tx()
        self.assertFalse(self.dest.exists())
    def test_opened_during_staging_defers(self):
        def fault(phase,journal):
            if phase=='prepared': self.current['running']=True
        with self.assertRaises(tx.TransactionDeferred): self.run_tx(fault=fault)
        self.assertEqual((self.dest/'version').read_text(),'1')
    def test_removed_during_staging_never_reinstalled(self):
        def fault(phase,journal):
            if phase=='prepared': shutil.rmtree(self.dest)
        with self.assertRaises(tx.TransactionDeferred): self.run_tx(fault=fault)
        self.assertFalse(self.dest.exists())
    def test_unknown_signing_and_running_defer(self):
        for field,value in [('running',None),('team_id',None),('bundle_id','org.other')]:
            self.current[field]=value
            with self.assertRaises(tx.TransactionDeferred): self.run_tx()
            self.current= {'path':str(self.dest),'presence':'present','freshness':'fresh','running':False,'bundle_id':'org.example','team_id':'TEAM','channel':'stable'}
    def test_policy_checked_twice(self):
        guards=[]
        with self.assertRaises(tx.TransactionDeferred):
            tx.execute_transaction(self.action,str(self.source),str(self.journals),lambda:self.current,lambda:guards.append(1) or len(guards)==1,self.observe,allowed_roots=[str(self.dest.parent)])
        self.assertEqual(len(guards),2); self.assertEqual((self.dest/'version').read_text(),'1')
    def test_fault_each_transition_recovers_from_files(self):
        for phase in ['journal_created','prepared','backup_renamed','backed_up','swap_renamed','swapped','verified']:
            with self.subTest(phase=phase):
                (self.dest/'version').write_text('1')
                def fault(observed,journal):
                    if observed==phase: raise SystemExit('simulated SIGKILL')
                with self.assertRaises(SystemExit): self.run_tx(fault=fault)
                journal=max(self.journals.glob('*.json'),key=lambda p:p.stat().st_mtime_ns)
                result=tx.recover_journal(str(journal),self.observe,allowed_roots=[str(self.dest.parent)])
                self.assertIn(result['state'],['verified','rolled_back','prepared'])
                self.assertTrue(self.dest.exists())
    def test_only_good_backup_retained_on_unknown_destination(self):
        result=self.run_tx(); journal=json.loads(pathlib.Path(result['journal_path']).read_text())
        decision=tx.recover_transaction(journal,{'destination':{'good':None},'backup':{'good':True},'staging':{'good':False}})
        self.assertEqual(decision['state'],'recovery_required'); self.assertTrue(pathlib.Path(journal['backup']).exists())
    def test_non_newer_and_minimum_os_and_arch_rejected(self):
        original=self.observe
        for changes in [{'version':'1'},{'minimum_os':'99.0'},{'architectures':['x86_64']},{'good':None},{'team_id':'EVIL'}]:
            def observed(path):
                result=original(path)
                if pathlib.Path(path)!=self.dest: result.update(changes)
                return result
            with self.assertRaises(tx.TransactionDeferred):
                tx.execute_transaction(self.action,str(self.source),str(self.journals),lambda:self.current,lambda:True,observed,allowed_roots=[str(self.dest.parent)])

    def test_post_swap_known_bad_bundle_rolls_back_preserving_rejected(self):
        original=self.observe
        def observe(path):
            result=original(path)
            if pathlib.Path(path)==self.dest and result.get('version')=='2': result['good']=False
            return result
        with self.assertRaises(tx.TransactionDeferred):
            tx.execute_transaction(self.action,str(self.source),str(self.journals),lambda:self.current,lambda:True,observe,allowed_roots=[str(self.dest.parent)])
        self.assertEqual((self.dest/'version').read_text(),'1')
        self.assertEqual(len(list(self.dest.parent.glob('.macupd-stage-*/*.rejected-*'))),1)
    def test_symlink_target_never_followed(self):
        shutil.rmtree(self.dest); self.dest.symlink_to(self.source,target_is_directory=True)
        with self.assertRaises(tx.TransactionDeferred): self.run_tx()
        self.assertEqual((self.source/'version').read_text(),'2')
    def test_exclusive_rename_cannot_clobber_recreated_destination(self):
        recreated=self.root/'recreated.app'; recreated.mkdir()
        with self.assertRaises(FileExistsError): tx._rename_exclusive(str(self.source),str(recreated))
        self.assertTrue(self.source.exists()); self.assertTrue(recreated.exists())
    def test_generic_sparkle_transaction_refused(self):
        self.action['adapter_id']='sparkle_appcast'
        with self.assertRaises(tx.TransactionDeferred): self.run_tx()
    def test_candidate_store_receipt_never_crosses_source(self):
        original=self.observe
        def observe(path):
            result=original(path)
            result['receipt_present']=pathlib.Path(path)!=self.dest
            return result
        with self.assertRaises(tx.TransactionDeferred):
            tx.execute_transaction(self.action,str(self.source),str(self.journals),lambda:self.current,lambda:True,observe,allowed_roots=[str(self.dest.parent)])
    def test_startup_recovers_absent_target_without_any_new_action(self):
        def fault(phase,journal):
            if phase=='backed_up': raise SystemExit('simulated power loss')
        with self.assertRaises(SystemExit): self.run_tx(fault=fault)
        self.assertFalse(self.dest.exists())
        from contextlib import nullcontext
        recovered=tx.recover_pending_transactions(str(self.journals.parent),observe=self.observe,allowed_roots=[str(self.dest.parent)],lock=lambda *args:nullcontext())
        self.assertEqual(recovered[0]['state'],'rolled_back')
        self.assertEqual((self.dest/'version').read_text(),'1')
