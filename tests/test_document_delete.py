"""仅合成上传与临时状态验证删除；不调用正式服务或数据库。"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
import threading
import unittest
from unittest.mock import MagicMock, patch
from tests import test_frontend_api as fixtures


class DocumentDeleteTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.FrontendAPITests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.client=self.f.client;self.reader=self.f.reader
        self.records={'a'*32:dict(principal_id='document-admin',owner_id='alice',roles=['ADMIN'],
            review_owner_scopes=[],credential_status='active',document_delete_owner_scopes=['alice']),
            'b'*32:dict(principal_id='ordinary-bob',owner_id='bob',roles=['USER'],review_owner_scopes=[],credential_status='active')}
        self.f.app.state.auth_registry.replace(self.records)
        self.default_check=self.f.app.state.document_delete_references
        self.f.app.state.document_delete_references=lambda *args:False

    def upload(self,auth=None):
        r=self.client.post('/api/parse/files?file_name=synthetic.pdf',headers=auth or self.f.auth,content=self.f.data)
        self.assertEqual(r.status_code,201,r.text)
        return r.json()['file_id']

    def delete(self,fid,auth=None):
        return self.client.delete('/api/documents/'+fid,headers=auth or self.f.auth)

    def assert_visible(self,fid):
        self.assertEqual(self.client.get('/api/documents/'+fid,headers=self.f.auth).status_code,200)
        self.assertEqual(self.client.get('/api/parse/files/'+fid+'/source',headers=self.f.auth).content,self.f.data)

    def test_delete_filters_all_reads_and_retains_original(self):
        fid=self.upload();_,source=self.reader.upload('alice',fid)
        r=self.delete(fid);self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(r.json()['deleted']);self.assertIsNotNone(r.json()['deleted_at'])
        self.assertEqual(source.read_bytes(),self.f.data)
        self.assertNotIn(str(self.f.root),r.text)
        self.assertEqual(self.client.get('/api/documents',headers=self.f.auth).json()['total'],0)
        for route in ('/api/documents/'+fid,'/api/documents/'+fid+'/parse-history','/api/parse/files/'+fid+'/source'):
            self.assertEqual(self.client.get(route,headers=self.f.auth).status_code,404)
        self.assertEqual(self.client.head('/api/parse/files/'+fid+'/source',headers=self.f.auth).status_code,404)
        self.assertEqual(self.delete(fid).status_code,404)
        self.assertEqual(self.delete('f'*32).status_code,404)
        self.assertEqual(self.f.service.repository.owned_tasks('alice'),[])

    def test_auth_permissions_cross_owner_and_parameters(self):
        fid=self.upload();other=self.upload(self.f.other)
        self.assertEqual(self.client.delete('/api/documents/'+fid).status_code,401)
        self.assertEqual(self.delete(other).status_code,200)
        self.assertEqual(self.delete('bad-id').status_code,422)
        for roles,scopes in [(['USER'],['alice']),(['REVIEWER'],['alice'])]:
            self.records['a'*32].update(roles=roles,document_delete_owner_scopes=scopes)
            self.f.app.state.auth_registry.replace(self.records)
            self.assertEqual(self.delete(fid).status_code,403)
        self.assert_visible(fid)

    def test_active_and_terminal_history_protect_evidence(self):
        fid,task=self.f.upload_task()
        self.assertEqual(self.delete(fid).status_code,409)
        value=self.f.service.repository.get(task['task_id'],'alice')
        value['status']='failed';self.f.service.repository.save(value)
        r=self.delete(fid);self.assertEqual(r.status_code,409)
        self.assertEqual(r.json()['error']['code'],'document_evidence_protected')
        self.assert_visible(fid)

    def test_reference_or_failed_reference_query_does_not_delete(self):
        fid=self.upload()
        self.f.app.state.document_delete_references=lambda *args:True
        self.assertEqual(self.delete(fid).status_code,409);self.assert_visible(fid)
        def fail(*args): raise OSError('sensitive internal details')
        self.f.app.state.document_delete_references=fail
        r=self.delete(fid);self.assertEqual(r.status_code,503)
        self.assertNotIn('sensitive',r.text);self.assert_visible(fid)

    def test_real_reference_adapter_checks_pg_and_all_kb_revisions(self):
        fid=self.upload();review=MagicMock();review.deletion_references.return_value=False
        self.reader.review=review
        database=MagicMock();database.transaction.return_value=nullcontext();database.one.return_value={'found':1}
        self.reader.kb_factory=lambda:database
        self.f.app.state.document_delete_references=self.default_check
        self.assertEqual(self.delete(fid).status_code,409)
        self.assertIn('mr_document_versions',database.one.call_args.args[0])
        self.assertNotIn('ACTIVE',database.one.call_args.args[0])
        database.close.assert_called_once();self.assert_visible(fid)

    def test_atomic_move_failure_keeps_document_visible(self):
        fid=self.upload()
        metadata=self.reader.root('alice')/(fid+'.json')
        original=metadata.read_bytes()
        import os
        real=os.replace
        def replace(src,dst):
            if Path(src).name==fid+'.json': raise OSError('synthetic failure')
            return real(src,dst)
        with patch('qa_core.storage.document_lifecycle.os.replace',side_effect=replace):
            self.assertEqual(self.delete(fid).status_code,503)
        self.assert_visible(fid)
        self.assertEqual(metadata.read_bytes(),original)

    def test_archived_upload_cannot_be_reintroduced_by_ingestion(self):
        fid=self.upload();_,source=self.reader.upload('alice',fid)
        self.assertEqual(self.delete(fid).status_code,200)
        from qa_core.storage.database import Database
        database=Database.__new__(Database)
        database._save_revision_unlocked=MagicMock()
        from qa_core.document_parsing.mineru_client import MinerUError
        with self.assertRaises(MinerUError):
            database.save_revision(source_path=str(source))
        database._save_revision_unlocked.assert_not_called()

    def test_missing_reference_store_fails_closed(self):
        fid=self.upload()
        self.f.app.state.document_delete_references=self.default_check
        self.assertEqual(self.delete(fid).status_code,503)
        self.assert_visible(fid)

    def test_archive_link_is_rejected(self):
        fid=self.upload();archive=self.reader.root('alice')/'.deleted'
        outside=self.f.root/'outside';outside.mkdir()
        try:
            archive.symlink_to(outside,target_is_directory=True)
        except OSError:
            self.skipTest('平台不允许创建测试链接')
        self.assertEqual(self.delete(fid).status_code,503)
        self.assert_visible(fid)

    def test_concurrent_delete_has_one_success(self):
        fid=self.upload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.delete(fid).status_code,range(2)))
        self.assertCountEqual(results,[200,404])

    def test_task_submission_wins_lock_and_delete_is_rejected(self):
        fid=self.upload();entered=threading.Event();release=threading.Event()
        original=self.f.service._submit_unlocked
        async def slow(*args,**kwargs):
            entered.set();await asyncio.to_thread(release.wait,5)
            return await original(*args,**kwargs)
        def submit():
            return self.client.post('/api/parse/tasks',headers={**self.f.auth,'Idempotency-Key':'race-task'},json={'file_ids':[fid]})
        with patch.object(self.f.service,'_submit_unlocked',side_effect=slow),ThreadPoolExecutor(max_workers=2) as pool:
            task=pool.submit(submit)
            try:
                self.assertTrue(entered.wait(3));deletion=pool.submit(self.delete,fid)
            finally: release.set()
            self.assertEqual(task.result().status_code,202)
            self.assertEqual(deletion.result().status_code,409)

    def test_delete_wins_and_no_task_can_reference_archived_upload(self):
        fid=self.upload();entered=threading.Event();release=threading.Event()
        def check(*args): entered.set();release.wait(5);return False
        self.f.app.state.document_delete_references=check
        def submit():
            return self.client.post('/api/parse/tasks',headers={**self.f.auth,'Idempotency-Key':'race-after-delete'},json={'file_ids':[fid]})
        with ThreadPoolExecutor(max_workers=2) as pool:
            deletion=pool.submit(self.delete,fid)
            try:
                self.assertTrue(entered.wait(3));task=pool.submit(submit)
            finally: release.set()
            self.assertEqual(deletion.result().status_code,200)
            self.assertIn(task.result().status_code,(400,404))
        self.assertEqual(self.f.service.repository.owned_tasks('alice'),[])

    def test_openapi_declares_delete_and_preserves_get(self):
        schema=self.client.get('/api/openapi.json',headers=self.f.auth).json()
        path=schema['paths']['/api/documents/{file_id}']
        self.assertIn('get',path);self.assertIn('delete',path)
        self.assertEqual(schema['info']['x-contract-version'],'frontend-api-v0.2.3-draft-4')
        self.assertIn('DocumentDeletion',schema['components']['schemas'])
        self.assertTrue(path['delete']['security'])
        for status in ('401','403','404','409','422','503'):
            self.assertIn(status,path['delete']['responses'])
