"""QA独立ASGI上传副本边界；对外链路严格使用MockTransport。"""
import unittest
import httpx
from qa_core.document_parsing.mineru_api import create_app
from tests import test_v021_test_batch_flow as flow


class ActualHTTPUploadBoundary(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture=flow.BatchHTTPFlow('test_anonymous_full_chain_charges_all_network_boundaries')
        await self.fixture.asyncSetUp()
        self.addCleanup(self.fixture.doCleanups)
        self.service=self.fixture.service()
        app=create_app(self.service.config,tokens={'a'*32:'alice','b'*32:'bob'},service=self.service,
                       dual_config=self.service.dual_router.config,batch_authorizer=self.fixture.authority)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://synthetic-app')
        self.addAsyncCleanup(self.client.aclose)
        self.headers={'Authorization':'Bearer '+'a'*32,'Idempotency-Key':'synthetic-stable'}

    async def upload(self,content=None):
        response=await self.client.post('/api/parse/files?file_name=synthetic-copy.png',content=content or self.fixture.source.read_bytes(),headers=self.headers)
        self.assertEqual(response.status_code,201)
        return response.json()['file_id']

    async def test_approved_sha_http_copy_gets_only_server_context(self):
        fid=await self.upload()
        response=await self.client.post('/api/parse/tasks',json=dict(file_ids=[fid],strategy='remote',allow_cloud_fallback=True),headers=self.headers)
        self.assertEqual(response.status_code,202,response.text)
        taskid=response.json()['task_id'];task=self.service.repository.get(taskid,'alice')
        self.assertEqual(task['authorization_context'],dict(mode='TEST_BATCH',owner='alice',batch_id='synthetic'))
        self.assertNotEqual(task['files'][0]['source_path'],str(self.fixture.source))
        await self.service.run(taskid)
        self.assertEqual(self.service.repository.get(taskid)['status'],'completed')
        self.assertTrue(self.fixture.requests)

    async def test_unapproved_http_copy_never_reaches_official_transport(self):
        fid=await self.upload(self.fixture.source.read_bytes()+b'unapproved-synthetic-trailer')
        response=await self.client.post('/api/parse/tasks',json=dict(file_ids=[fid],strategy='remote',allow_cloud_fallback=True),headers=self.headers)
        self.assertEqual(response.status_code,202)
        await self.service.run(response.json()['task_id'])
        self.assertEqual(self.fixture.requests,[])

    async def test_http_cannot_select_batch_manifest_or_context(self):
        fid=await self.upload()
        for key,value in [('batch_id','synthetic'),('manifest_path','untrusted.json'),('authorization_context',{'mode':'TEST_BATCH','owner':'alice','batch_id':'synthetic'})]:
            with self.subTest(key=key):
                response=await self.client.post('/api/parse/tasks',json=dict(file_ids=[fid],strategy='remote',allow_cloud_fallback=True,**{key:value}),headers=self.headers)
                self.assertEqual(response.status_code,400)
        self.assertEqual(self.fixture.requests,[])


if __name__=='__main__':unittest.main()
