"""Temporary installed metadata, approved plans and native command doubles."""
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib/python'))
import policy_runtime
from inventory_collect import read_bundle_static
from inventory_providers import read_brew_receipts
from source_resolver import resolve_target
from update_plan import build_plan
from user_policy import make_decision,record_decision
ROOT=Path(__file__).resolve().parents[1]

class PolicyFixture:
    def __enter__(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.state=self.root/'state';self.state.mkdir(mode=0o700)
        self.bin=self.root/'bin';self.bin.mkdir();self.session=self.root/'session';self.session.mkdir()
        self.log=self.root/'calls.jsonl';self.app=self.root/'Applications/Fixture.app';(self.app/'Contents').mkdir(parents=True)
        self.plist=self.app/'Contents/Info.plist'
        with self.plist.open('wb') as stream: plistlib.dump({'CFBundleIdentifier':'fixture.app','CFBundleName':'Fixture','CFBundleShortVersionString':'1.0.0'},stream)
        for name,body in [('ps','exit 0'),('uname','echo arm64'),('sw_vers','echo 26.0')]: self.shell(name,body)
        (self.bin/'python3').symlink_to(sys.executable)
        self.environ=patch.dict(os.environ,dict(HOME=str(self.root),MAC_UPDATE_STATE_DIR=str(self.state),MAC_UPDATE_SESSION_DIR=str(self.session),PATH=str(self.bin)+':/usr/bin:/bin',MAC_UPDATE_YES='1',MAC_UPDATE_NONINTERACTIVE='1',MAC_LANG='en',MAC_UPDATE_HOMEBREW_PREFIX=str(self.root/'unused-homebrew')),clear=False)
        self.environ.start();os.environ.pop('MAC_UPDATE_PLAN_PATH',None)
        return self
    def __exit__(self,*args): self.environ.stop();self.temp.cleanup()
    def shell(self,name,body):
        p=self.bin/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
    def python(self,path,body):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text('#!'+sys.executable+'\n'+body);path.chmod(0o755)
    def _log_source(self): return f"with open({str(self.log)!r},'a') as stream: stream.write(json.dumps(sys.argv[1:])+'\\n')\n"
    def calls(self): return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
    def results(self): return [json.loads(line) for line in (self.session/'action-results.jsonl').read_text().splitlines()]
    def approve(self,target,apps=None):
        snapshot=dict(snapshot_id='fixture-snapshot',profile_id='fixture-profile',generation=0,instances=apps or [],packages=[],sources={})
        if 'package_id' in target: snapshot['packages']=[target]
        else: snapshot['instances']=[target]
        records=snapshot['instances']+snapshot['packages']
        resolutions=[resolve_target(item,snapshot,{'recipes':[]}) for item in records]
        policies={'profile_id':'fixture-profile'}
        for item,res in zip(records,resolutions): policies=record_decision(make_decision(item,res,'allow_update_same_source','manager_update',policy_runtime.utc_now()),policies)
        policies['revision']=policy_runtime.load_policies().get('revision',0)+1
        policy_runtime.save_policies(policies)
        self.plan=build_plan(snapshot,resolutions,policies,policy_runtime.utc_now())
        self.path=self.root/(str(len(list(self.root.glob('plan*'))))+'plan.json');policy_runtime.save_plan(self.plan,str(self.path));os.environ['MAC_UPDATE_PLAN_PATH']=str(self.path)
    def cask(self,latest='2.0.0',extra_artifacts=None,orphan=False):
        self.prefix=self.root/'brew';receipt=self.prefix/'Caskroom/fixture/.metadata/1.0.0/20261113/Casks/fixture.json';receipt.parent.mkdir(parents=True)
        artifacts=[{'app':['Fixture.app']}]+(extra_artifacts or [])
        receipt.write_text(json.dumps(dict(token='fixture',artifacts=artifacts)))
        link=self.prefix/'Caskroom/fixture/1.0.0/Fixture.app';link.parent.mkdir(parents=True);link.symlink_to(self.app)
        data=dict(casks=[dict(token='fixture',version=latest,artifacts=artifacts)])
        script="import sys,json,pathlib,plistlib,os\n"+self._log_source()+f'''
if sys.argv[1]=='info': print({json.dumps(data)!r})
elif sys.argv[1]=='upgrade':
    receipt=pathlib.Path({str(receipt)!r}); newer=pathlib.Path({str(self.prefix)!r})/'Caskroom/fixture/.metadata/{latest}/20261114/Casks/fixture.json'
    newer.parent.mkdir(parents=True,exist_ok=True);newer.write_bytes(receipt.read_bytes())
    link=pathlib.Path({str(self.prefix)!r})/'Caskroom/fixture/{latest}/Fixture.app';link.parent.mkdir(parents=True,exist_ok=True)
    if not link.exists(): link.symlink_to({str(self.app)!r})
    p=pathlib.Path({str(self.plist)!r});data=plistlib.loads(p.read_bytes());data['CFBundleShortVersionString']={latest!r};p.write_bytes(plistlib.dumps(data))
else: sys.exit(1)
'''
        self.python(self.prefix/'bin/brew',script)
        package=dict(read_brew_receipts(str(self.prefix))['items'][0],package_id='cask1',prefix=str(self.prefix),presence='present',freshness='fresh',observed_at=policy_runtime.utc_now(),related_instance_ids=['app1'])
        app=dict(read_bundle_static(str(self.app))['items'][0],instance_id='app1',path=str(self.app),real_path=str(self.app),presence='present',freshness='fresh',scope='optional_root',parent_instance_id=None,observed_at=policy_runtime.utc_now())
        app['evidence'].extend(package['evidence']);self.approve(package,[app])
        if orphan: shutil.rmtree(self.app)
    def mas(self,outdated=None,mutates=True,sudo_mutates=True):
        receipt=self.app/'Contents/_MASReceipt/receipt';receipt.parent.mkdir();receipt.write_text('marker')
        row=dict(id=123,bundleID='fixture.app',name='Fixture',version='1.0.0')
        pending='123 Fixture (1.0.0 -> 2.0.0)' if outdated is None else outdated
        script="import sys,json,pathlib,plistlib,os\n"+self._log_source()+f'''
if sys.argv[1]=='list': print({json.dumps([row])!r})
elif sys.argv[1]=='outdated': print({pending!r})
elif sys.argv[1]=='upgrade':
    if sys.argv[2:]!=['123']: sys.exit(9)
    if {mutates!r} and ({sudo_mutates!r} or os.environ.get('FIXTURE_SUDO')!='1'):
        p=pathlib.Path({str(self.plist)!r});data=plistlib.loads(p.read_bytes());data['CFBundleShortVersionString']='2.0.0';p.write_bytes(plistlib.dumps(data))
else: sys.exit(1)
'''
        self.python(self.bin/'mas',script)
        self.shell('sudo','test "$1" = -n || exit 5; shift; export FIXTURE_SUDO=1; exec "$@"')
        app=dict(read_bundle_static(str(self.app))['items'][0],instance_id='mas1',path=str(self.app),real_path=str(self.app),presence='present',freshness='fresh',scope='optional_root',parent_instance_id=None,observed_at=policy_runtime.utc_now())
        app['evidence'].append(dict(kind='mas',store_id='123',bundle_id='fixture.app',path=str(self.app)));self.approve(app)
    def run(self,script): return subprocess.run(['/bin/bash',str(ROOT/script)],env=dict(os.environ),capture_output=True,text=True,timeout=15)
