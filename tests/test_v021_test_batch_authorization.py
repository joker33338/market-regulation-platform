"""TEST_BATCH授权契约：仅使用合成字节和本地清单，不发起HTTP。"""
import importlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import hashlib
from types import SimpleNamespace

from qa_core.document_parsing.dual_engine import DualEngineConfig,DualEngineRouter
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService


class TestBatchAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.path=self.root/'synthetic.pdf';self.path.write_bytes(b'%PDF synthetic authorized fixture')
        self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.manifest=self.root/'private-server-manifest.json'
        self.value=dict(version=1,batch_id='synthetic-batch',owner='alice',expires_at=time.time()+3600,revoked=False,
            entries=[dict(sha256=self.sha,source_qualified=True,sensitivity_confirmed=True,sensitive=False,
                          third_party_transfer_rights_confirmed=True,source_evidence='QA-created synthetic fixture')])
        self.save()
        self.task=dict(owner='alice',parse_options={'strategy':'remote','allow_cloud_fallback':True,'sensitive':False})
        self.file=dict(source_path=str(self.path),sha256=self.sha)

    def save(self):
        self.manifest.write_text(json.dumps(self.value),encoding='utf-8')

    def authorizer(self):
        try:module=importlib.import_module('qa_core.document_parsing.test_batch_authorization')
        except ModuleNotFoundError:self.fail('缺少已约定的服务端TEST_BATCH授权实现')
        return module.TrustedTestBatch(self.manifest,owner='alice',batch_id='synthetic-batch')

    def bound(self):
        authorizer=self.authorizer();authorizer.bind_task(self.task);return authorizer

    def router(self,authorizer):
        config=DualEngineConfig(enabled=True,cloud_enabled=True,environment='test',authorization_mode='TEST_BATCH')
        remote=MinerUConfig(enabled=True,mode='remote',provider='official',api_url='https://mineru.net/api',api_key='synthetic-token',result_dir=self.root)
        return DualEngineRouter(config,remote,batch_authorizer=authorizer)

    def test_valid_server_bound_batch_can_authorize(self):
        auth=self.bound();self.assertEqual(auth.authorize(self.task,self.file),(True,'TEST_BATCH:synthetic-batch'))
        self.assertEqual(self.task['authorization_context'],dict(mode='TEST_BATCH',owner='alice',batch_id='synthetic-batch'))

    def test_nonmember_hash_is_denied(self):
        auth=self.bound();p=self.root/'outside.pdf';p.write_bytes(b'unapproved')
        self.assertFalse(auth.authorize(self.task,dict(source_path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))[0])

    def test_real_bytes_change_invalidates_unchanged_declared_sha(self):
        auth=self.bound();self.path.write_bytes(b'changed bytes but caller kept old sha')
        self.assertFalse(auth.authorize(self.task,self.file)[0])

    def test_declared_sha_change_is_denied(self):
        auth=self.bound();self.file['sha256']='0'*64
        self.assertFalse(auth.authorize(self.task,self.file)[0])

    def test_expiry_is_reloaded_on_every_authorization(self):
        auth=self.bound();self.assertTrue(auth.authorize(self.task,self.file)[0])
        self.value['expires_at']=time.time()-1;self.save()
        self.assertFalse(auth.authorize(self.task,self.file)[0])

    def test_revocation_is_reloaded(self):
        auth=self.bound();self.value['revoked']=True;self.save()
        self.assertFalse(auth.authorize(self.task,self.file)[0])

    def test_sensitive_and_unknown_rights_are_denied(self):
        for field,bad in [('sensitive',True),('sensitivity_confirmed',False),('third_party_transfer_rights_confirmed',False),('source_qualified',False),('source_evidence','')]:
            with self.subTest(field=field):
                old=self.value['entries'][0][field];self.value['entries'][0][field]=bad;self.save()
                self.assertFalse(self.bound().authorize(self.task,self.file)[0])
                self.value['entries'][0][field]=old;self.save()

    def test_unknown_or_nonboolean_fields_are_not_truthy_grants(self):
        for field in ('sensitive','sensitivity_confirmed','third_party_transfer_rights_confirmed','source_qualified'):
            with self.subTest(field=field):
                original=self.value['entries'][0][field];self.value['entries'][0][field]='true';self.save()
                self.assertFalse(self.bound().authorize(self.task,self.file)[0])
                self.value['entries'][0][field]=original;self.save()

    def test_same_hash_http_copy_requires_server_binding(self):
        auth=self.authorizer();copy=self.root/'http-copy.pdf';copy.write_bytes(self.path.read_bytes())
        file=dict(source_path=str(copy),sha256=self.sha)
        self.assertFalse(auth.authorize(self.task,file)[0])
        auth.bind_task(self.task);self.assertTrue(auth.authorize(self.task,file)[0])

    def test_arbitrary_external_path_does_not_authorize_different_bytes(self):
        auth=self.bound();copy=self.root/'external-copy.pdf';copy.write_bytes(b'not approved content')
        self.assertFalse(auth.authorize(self.task,dict(source_path=str(copy),sha256=self.sha))[0])

    def test_forged_task_batch_id_or_owner_is_denied(self):
        auth=self.bound()
        self.task['authorization_context']['batch_id']='forged'
        self.assertFalse(auth.authorize(self.task,self.file)[0])
        self.task['authorization_context']['batch_id']='synthetic-batch';self.task['owner']='bob'
        self.assertFalse(auth.authorize(self.task,self.file)[0])

    def test_resume_does_not_rebind_another_batch(self):
        auth=self.bound();self.task['authorization_context']['batch_id']='old-bound-batch'
        with self.assertRaises((ValueError,RuntimeError)):auth.bind_task(self.task)
        self.assertEqual(self.task['authorization_context']['batch_id'],'old-bound-batch')

    def test_manifest_owner_and_id_tampering_is_denied(self):
        auth=self.bound()
        for field in ('owner','batch_id'):
            with self.subTest(field=field):
                old=self.value[field];self.value[field]='forged';self.save()
                self.assertFalse(auth.authorize(self.task,self.file)[0])
                self.value[field]=old;self.save()

    def test_duplicate_sha_entries_are_denied(self):
        auth=self.bound();self.value['entries'].append(dict(self.value['entries'][0]));self.save()
        self.assertFalse(auth.authorize(self.task,self.file)[0])

    def test_test_batch_router_requires_test_environment(self):
        with self.assertRaises(ValueError):DualEngineConfig(environment='production',authorization_mode='TEST_BATCH')

    def test_production_defaults_and_corpus_hard_deny_remain(self):
        cfg=DualEngineConfig(enabled=True,cloud_enabled=True)
        self.assertEqual(getattr(cfg,'environment','production'),'production')
        self.assertEqual(getattr(cfg,'authorization_mode','FILE_SHA'),'FILE_SHA')
        remote=MinerUConfig(enabled=True,mode='remote',provider='official',api_url='https://mineru.net/api',api_key='synthetic-token',result_dir=self.root)
        grants={'alice':{self.sha:dict(authorization_id='synthetic',expires_at=time.time()+3600)}}
        with patch.dict(os.environ,{'MARKET_REGULATION_TEST_CORPUS':str(self.root)}):
            allowed,reason=DualEngineRouter(cfg,remote,grants=grants).authorization(self.task,self.file)
        self.assertFalse(allowed);self.assertEqual(reason,'corpus_transfer_denied')

    def test_test_batch_overrides_corpus_deny_only_with_qualified_binding(self):
        auth=self.bound()
        with patch.dict(os.environ,{'MARKET_REGULATION_TEST_CORPUS':str(self.root)}):
            self.assertTrue(self.router(auth).authorization(self.task,self.file)[0])

    def test_client_sensitive_flag_cannot_be_weakened_by_manifest(self):
        auth=self.bound();self.task['parse_options']['sensitive']=True
        self.assertFalse(auth.authorize(self.task,self.file)[0])

    def test_batch_ledger_survives_new_authorizer_and_task_ids(self):
        auth=self.bound()
        for index in range(32):
            self.task['id']='synthetic-task-'+str(index)
            self.authorizer().reserve_request(self.task,self.file,'GET')
        with self.assertRaises((ValueError,RuntimeError,MinerUError)):
            self.authorizer().reserve_request(self.task,self.file,'GET')

    def test_batch_file_limit_is_not_reset_by_another_task(self):
        auth=self.bound();files=[]
        template=self.value['entries'][0]
        for index in range(4):
            p=self.root/('fixture-'+str(index)+'.pdf');p.write_bytes(('synthetic-'+str(index)).encode())
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            self.value['entries'].append({**template,'sha256':digest})
            files.append(dict(source_path=str(p),sha256=digest))
        self.save()
        for index,file in enumerate(files[:3]):
            self.task['id']='synthetic-task-'+str(index)
            auth.reserve_request(self.task,file,'GET')
        with self.assertRaises((ValueError,RuntimeError,MinerUError)):
            self.authorizer().reserve_request(self.task,files[3],'GET')


class HTTPOptionBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_parse_options_cannot_supply_batch_id(self):
        await self.reject_option('batch_id','synthetic-batch')

    async def test_http_parse_options_cannot_supply_manifest_path(self):
        await self.reject_option('manifest_path','untrusted.json')

    async def test_http_parse_options_cannot_supply_authorization_context(self):
        await self.reject_option('authorization_context',dict(mode='TEST_BATCH',owner='alice',batch_id='synthetic-batch'))

    async def reject_option(self,key,value):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'synthetic.pdf';p.write_bytes(b'%PDF synthetic')
            cfg=MinerUConfig(enabled=True,mode='local',result_dir=root)
            router=SimpleNamespace(config=SimpleNamespace(enabled=True))
            service=MinerUService(cfg,TaskRepository(root/'tasks.sqlite3'),dual_router=router)
            with self.assertRaises(MinerUError) as raised:
                await service.submit('alice','synthetic-request',[p],parse_options={'strategy':'remote',key:value})
            self.assertEqual(raised.exception.code,'invalid_parse_options')


if __name__=='__main__':unittest.main()
