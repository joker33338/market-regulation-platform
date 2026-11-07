"""QA参考场景及独立生产适配器验收；所有HTTP流量使用Mock。"""
import asyncio
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import httpx
from tests.mineru_contract_harness import ContractDriver


def zipped(name='result.md'):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as archive:
        archive.writestr(name, 'synthetic')
    return buffer.getvalue()


class MinerUReferenceContracts(unittest.TestCase):
    def driver(self, handler):
        driver = ContractDriver(httpx.MockTransport(handler))
        self.addCleanup(driver.http.close)
        return driver

    def test_create_upload_poll_download_multifile_partial(self):
        calls=[]
        def handle(request):
            calls.append(request)
            if request.method=='POST':
                body=json.loads(request.content)
                self.assertEqual(body['tier'],'standard')
                self.assertEqual(len(body['files']),2)
                self.assertNotIn('file_id',body['files'][0])
                return httpx.Response(202,json={'task_id':'t','status':'waiting-file','files':[
                    {'file_id':'f1','file_name':'a.pdf','status':'waiting-file','upload':{
                        'url':'https://store.invalid/input','headers':{'X-Signed':'fixture'},'expires_at':4102444800}},
                    {'file_id':'f2','file_name':'b.pdf','status':'pending'}]})
            if request.method=='PUT':
                self.assertEqual(request.headers['X-Signed'],'fixture')
                self.assertNotIn('Authorization',request.headers)
                self.assertEqual(request.content,b'pdf')
                return httpx.Response(200)
            if request.url.host=='store.invalid':
                self.assertNotIn('Authorization',request.headers)
                return httpx.Response(200,content=zipped())
            return httpx.Response(200,json={'task_id':'t','status':'partial','files':[
                {'file_id':'f1','status':'completed','result_url':'https://store.invalid/result'},
                {'file_id':'f2','status':'failed','error':{'code':'parse_failed','message':'synthetic'}}]})
        driver=self.driver(handle)
        created=driver.create([{'file_name':n,'bytes':3} for n in ['a.pdf','b.pdf']])
        for file in created['files']:
            driver.upload(file,b'pdf')
        result=driver.poll(created['task_id'])
        self.assertEqual(result['files'][0]['file_id'],'f1')
        self.assertEqual(driver.download(result['files'][0]),['result.md'])
        self.assertEqual([r.method for r in calls],['POST','PUT','GET','GET'])

    def test_create_errors_are_not_retried(self):
        for status in [400,401,429,500]:
            with self.subTest(status=status):
                calls=[]
                def handle(request):
                    calls.append(request)
                    return httpx.Response(status,json={'error':{'code':'fixture','message':'synthetic'}})
                with self.assertRaises(httpx.HTTPStatusError):
                    self.driver(handle).create([{'file_name':'a.pdf','bytes':1}])
                self.assertEqual(len(calls),1)

    def test_uncertain_creation_timeout_no_retry(self):
        calls=[]
        def handle(request):
            calls.append(request)
            raise httpx.ConnectTimeout('synthetic',request=request)
        with self.assertRaises(httpx.ConnectTimeout):
            self.driver(handle).create([{'file_name':'a.pdf','bytes':1}])
        self.assertEqual(len(calls),1)

    def test_all_poll_states_and_bounded_resume(self):
        for terminal in ['completed','partial','failed','canceled']:
            states=iter(['waiting-file','pending','running',terminal])
            intervals=[]
            driver=self.driver(lambda r:httpx.Response(200,json={'task_id':'a/b','status':next(states),'files':[]}))
            result=driver.poll('a/b',max_polls=4,interval=2,sleep=intervals.append)
            self.assertEqual(result['status'],terminal)
            self.assertEqual(intervals,[2,2,2])
        calls=[]
        def handle(request):
            calls.append(request)
            return httpx.Response(200,json={'task_id':'t','status':'running' if len(calls)<3 else 'completed','files':[]})
        driver=self.driver(handle)
        with self.assertRaisesRegex(TimeoutError,'t'):
            driver.poll('t',max_polls=2)
        self.assertEqual(driver.poll('t')['status'],'completed')
        self.assertTrue(all(r.method=='GET' for r in calls))

    def test_cache_and_waiting_without_upload_do_not_put(self):
        driver=self.driver(lambda _:self.fail('unexpected network'))
        for state in ['pending','running','completed','waiting-file']:
            driver.upload({'file_id':'f','status':state},b'x')

    def test_upload_failure_and_expiry(self):
        for status in [403,410,500]:
            driver=self.driver(lambda r:httpx.Response(status))
            with self.assertRaises(httpx.HTTPStatusError):
                driver.upload({'status':'waiting-file','upload':{'url':'https://store.invalid/input','headers':{}}},b'x')

    def test_invalid_and_oversized_manifest_rejection(self):
        for item, status in [({'file_name':'../a.pdf','bytes':1},400),
                             ({'file_name':'a.pdf','bytes':0},400),
                             ({'file_name':'a.pdf','bytes':10**15},413)]:
            driver=self.driver(lambda r:httpx.Response(status,json={'error':{'code':'fixture','message':'synthetic'}}))
            with self.assertRaises(httpx.HTTPStatusError):
                driver.create([item])

    def test_interrupted_upload_resume_queries_before_reupload(self):
        calls=[]
        def handle(request):
            calls.append(request.method)
            if request.method=='PUT':
                raise httpx.WriteError('synthetic',request=request)
            return httpx.Response(200,json={'task_id':'t','status':'completed','files':[
                {'file_id':'f','status':'completed','result_url':'https://store.invalid/result'}]})
        driver=self.driver(handle)
        with self.assertRaises(httpx.WriteError):
            driver.upload({'status':'waiting-file','upload':{'url':'https://store.invalid/input','headers':{}}},b'x')
        detail=driver.poll('t')
        driver.upload(detail['files'][0],b'x')
        self.assertEqual(calls,['PUT','GET'])

    def test_health_tiers_and_proxy_task_path(self):
        paths=[]
        def handle(request):
            paths.append(request.url.raw_path)
            return httpx.Response(200,json={'task_id':'a/b','status':'completed','files':[]})
        driver=self.driver(handle)
        for route in ['/v1/health','/v1/tiers']:
            driver.request('GET',driver.base+route)
        driver.poll('a/b')
        self.assertEqual(paths,[b'/proxy/v1/health',b'/proxy/v1/tiers',b'/proxy/v1/tasks/a%2Fb'])

    def test_download_rejects_corruption_incomplete_and_traversal(self):
        for data in [b'not zip',zipped('../escape.md'),zipped('/escape.md'),zipped('C:/escape.md'),zipped('only.json')]:
            driver=self.driver(lambda r:httpx.Response(200,content=data))
            with self.assertRaises((ValueError,zipfile.BadZipFile)):
                driver.download({'result_url':'https://store.invalid/result'})

    def test_download_expired_or_interrupted(self):
        driver=self.driver(lambda r:httpx.Response(403))
        with self.assertRaises(httpx.HTTPStatusError):
            driver.download({'result_url':'https://store.invalid/result'})
        def interrupted(request):
            raise httpx.ReadError('synthetic',request=request)
        with self.assertRaises(httpx.ReadError):
            self.driver(interrupted).download({'result_url':'https://store.invalid/result'})

    def test_redirect_does_not_leak_api_key(self):
        def handle(request):
            if request.url.host=='api.invalid':
                self.assertIn('Authorization',request.headers)
                return httpx.Response(302,headers={'location':'https://store.invalid/result'})
            self.assertNotIn('Authorization',request.headers)
            return httpx.Response(200,content=zipped())
        self.driver(handle).download({'result_url':'https://api.invalid/result'})

    def test_mock_driver_refuses_real_transport(self):
        with self.assertRaises(ValueError):
            ContractDriver(None)

    @unittest.skipUnless(importlib.util.find_spec('qa_core.document_parsing.mineru_service'),
                         '当前源提交尚无生产适配器')
    def test_production_adapter_acceptance(self):
        from qa_core.document_parsing.mineru_config import MinerUConfig
        from qa_core.document_parsing.mineru_client import MinerUClient
        from qa_core.document_parsing.mineru_repository import TaskRepository
        from qa_core.document_parsing.mineru_service import MinerUService
        from qa_core.document_parsing.mineru_mock import mock_transport

        async def verify(root):
            config = MinerUConfig(enabled=True, result_dir=root, poll_interval=0, max_polls=3)
            client = MinerUClient(config, transport=mock_transport())
            try:
                service = MinerUService(config, TaskRepository(root/'tasks.sqlite3'), client)
                path = root/'synthetic.pdf'
                path.write_bytes(b'%PDF-1.7 synthetic adapter contract')
                task, _ = await service.submit('qa-owner', 'qa-contract', [('synthetic.pdf', path)])
                await service.run(task['id'])
                stored = service.repository.get(task['id'], 'qa-owner')
                self.assertEqual(stored['status'], 'completed')
                file = stored['files'][0]
                self.assertTrue(stored['remote_id'])
                normalized = json.loads((Path(file['result_path'])/'normalized.json').read_text(encoding='utf-8'))
                self.assertEqual(normalized['document_id'], file['sha256'])
                self.assertEqual(normalized['source_location']['mineru_task_id'], stored['remote_id'])
                self.assertEqual(normalized['source_location']['mineru_file_id'], file['remote_id'])
                self.assertTrue(normalized['quality']['mock'])
                repeated, created = await service.submit('qa-owner', 'qa-contract', [('synthetic.pdf', path)])
                self.assertFalse(created)
                self.assertEqual(repeated['id'], task['id'])
            finally:
                await client.close()

        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(verify(Path(directory)))
