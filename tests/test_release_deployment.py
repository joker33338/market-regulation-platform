"""部署工具增量测试：临时SQLite与Docker替身，不触碰实际容器。"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('release_deploy',Path(__file__).resolve().parents[1]/'scripts/deploy_release.py')
deploy=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(deploy)


class ReleaseDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.state=self.root/'state';(self.state/'parsing').mkdir(parents=True)
        with contextlib.closing(sqlite3.connect(self.state/'parsing/tasks.sqlite3')) as c, c:c.execute('CREATE TABLE parse_tasks(status text)');c.execute("INSERT INTO parse_tasks VALUES('completed')")
        self.runtime=self.root/'runtime.json';self.runtime.write_text(json.dumps({'PARSING_API_TOKENS_JSON':'{}','PARSING_RESULT_PG_DSN':'synthetic'}))
        self.revision='a'*40;self.calls=[];self.containers={deploy.NAME:{'Id':'old','Image':'old-image','Mounts':[{'Destination':dst,'Source':str(self.state if dst=='/state' else self.runtime if dst=='/private/runtime.json' else self.root/'models' if dst=='/models' else self.state/'logs'),'Type':'bind','RW':dst in ('/state','/app/reports')} for dst in ('/state','/models','/private/runtime.json','/app/reports')],'HostConfig':{'Tmpfs':{'/tmp':'rw,size=64m'}},'Config':{'Labels':{}},'NetworkSettings':{'Networks':{'synthetic-network':{}}},'State':{'Status':'running','Health':{'Status':'healthy'}}}}
        self.image={'Id':'new-image','Config':{'Labels':{'org.opencontainers.image.revision':self.revision,'cn.market-regulation.frontend.revision':self.revision}}};self.fail=False
        self.enterContext(patch.object(deploy,'ROOT',self.root));self.enterContext(patch.object(deploy.time,'sleep'))
        self.enterContext(patch.object(deploy,'command',side_effect=self.command));self.enterContext(patch.object(deploy.subprocess,'run',side_effect=self.fake_run))

    def command(self,*args):
        self.calls.append(args)
        if args[:2]==('image','inspect'):return json.dumps([self.image]).encode()
        if args[0]=='inspect':return json.dumps([self.containers[args[1]]]).encode()
        if args[0]=='stop':self.containers[args[-1]]['State']['Status']='exited'
        if args[0]=='rename':self.containers[args[2]]=self.containers.pop(args[1])
        if args[0]=='start':self.containers[args[1]]['State']['Status']='running'
        if args[0]=='run':
            if self.fail:raise RuntimeError('合成启动失败')
            self.containers[deploy.NAME]={'Id':'new','Image':'new-image','State':{'Status':'running','Health':{'Status':'healthy'}}}
        return b''

    def fake_run(self,args,**kwargs):
        if args[0]=='git':return subprocess.CompletedProcess(args,0,b'',b'')
        if args[:2]==['docker','inspect']:
            current=self.containers.get(args[2]);return subprocess.CompletedProcess(args,0 if current else 1,json.dumps([current]).encode() if current else b'',b'')
        raise AssertionError('意外外部操作')

    def execute(self,apply=False):
        args=['deploy','--image','synthetic-image','--revision',self.revision]+(['--apply'] if apply else [])
        with patch('sys.argv',args),contextlib.redirect_stdout(io.StringIO()):deploy.main()

    def test_preflight_does_not_stop_or_create(self):
        self.execute();self.assertEqual(self.containers[deploy.NAME]['Id'],'old');self.assertFalse(any(x[0] in ('stop','run') for x in self.calls))

    def test_revision_mismatch_fails_before_stop(self):
        self.image['Config']['Labels']['org.opencontainers.image.revision']='b'*40
        with self.assertRaises(RuntimeError):self.execute(True)
        self.assertFalse(any(x[0]=='stop' for x in self.calls))

    def test_active_task_blocks_switch(self):
        with contextlib.closing(sqlite3.connect(self.state/'parsing/tasks.sqlite3')) as c, c:c.execute("INSERT INTO parse_tasks VALUES('running')")
        with self.assertRaises(RuntimeError):self.execute(True)
        self.assertFalse(any(x[0]=='stop' for x in self.calls))

    def test_failed_launch_restores_old_container(self):
        self.fail=True
        with self.assertRaises(RuntimeError):self.execute(True)
        self.assertEqual(self.containers[deploy.NAME]['Id'],'old');self.assertEqual(self.containers[deploy.NAME]['State']['Status'],'running')

    def test_success_preserves_old_container_and_tasks(self):
        self.execute(True)
        self.assertEqual(self.containers[deploy.NAME]['Id'],'new');self.assertTrue(any(x['Id']=='old' for x in self.containers.values()))
        args=next(x for x in self.calls if x[0]=='run');self.assertIn('--read-only',args);self.assertIn('--health-cmd',args)
        with contextlib.closing(sqlite3.connect(self.state/'parsing/tasks.sqlite3')) as c, c:self.assertEqual(c.execute('SELECT status FROM parse_tasks').fetchall(),[('completed',)])
