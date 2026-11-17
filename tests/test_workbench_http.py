"""合成文件的真实HTTP编排，临时SQLite和状态目录；不启动引擎或访问正式库。"""
import asyncio
import unittest
from unittest.mock import patch

from tests import test_frontend_api as fixtures


class WorkbenchHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.FrontendAPITests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def post(self, path, body=None, key="batch-key", headers=None):
        return self.f.client.post(path, json=body, headers={**(headers or self.f.auth), "Idempotency-Key": key})

    def upload(self, name="synthetic.pdf"):
        response = self.f.client.post("/api/parse/files", params={"file_name": name},
                                      content=self.f.data, headers=self.f.auth)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["file_id"]

    def test_batch_http_auth_scope_atomic_append_and_persistent_dispatch(self):
        fid = self.upload()
        created = self.post("/api/workbench/batches", {"name": "合成批次"})
        self.assertEqual(created.status_code, 201, created.text)
        batch_id = created.json()["operation_id"]
        url = f"/api/workbench/batches/{batch_id}/files"
        rejected = self.post(url, {"files": [{"file_id": fid}, {"file_id": "0"*32}]})
        self.assertEqual(rejected.status_code, 404)
        self.assertEqual(self.f.get(f"/api/workbench/batches/{batch_id}").json()["files"], [])
        added = self.post(url, {"files": [{"file_id": fid, "relative_path": "地区/合成.pdf"}]})
        self.assertEqual(added.status_code, 200, added.text)
        self.assertEqual(self.f.client.get(f"/api/workbench/batches/{batch_id}", headers=self.f.other).status_code, 404)
        self.assertEqual(self.f.client.get(f"/api/workbench/batches/{batch_id}").status_code, 401)
        asyncio.run(self.f.app.state.file_batches.dispatch(self.f.service, self.f.reader))
        value = self.f.get(f"/api/workbench/batches/{batch_id}").json()
        self.assertEqual(value["files"][0]["status"], "submitted")
        task_id = value["files"][0]["task_id"]
        self.assertEqual(self.f.service.repository.get(task_id, "alice")["files"][0]["source_file_id"], fid)
        self.assertNotIn("source_path", str(value))

    def test_selection_snapshot_excludes_later_upload_and_enforces_scope(self):
        fid = self.upload()
        result = self.post("/api/workbench/selections", {"keyword": "synthetic"})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()["count"], 1)
        self.upload("synthetic-later.pdf")
        sid = result.json()["selection_id"]
        url = f"/api/workbench/selections/{sid}/files"
        selected = self.f.get(url).json()
        self.assertEqual(selected["total"], 1)
        self.assertEqual(selected["list"][0]["file_id"], fid)
        self.assertEqual(self.f.client.get(url, headers=self.f.other).status_code, 404)
        self.assertEqual(self.f.client.get(url).status_code, 401)

    def test_workbench_query_filter_and_unavailable_state_are_truthful(self):
        self.upload("synthetic.pdf")
        self.upload("other.pdf")
        response = self.f.get("/api/workbench/documents?keyword=synthetic")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["list"][0]["stage"], "uploaded")
        self.assertFalse(response.json()["availability"]["postgres"])
        self.assertEqual(self.f.get("/api/workbench/documents?page=0").status_code, 422)

    def test_batch_storage_failure_returns_503(self):
        with patch.object(self.f.app.state.file_batches, "create", side_effect=OSError("private path")):
            response = self.post("/api/workbench/batches", {"name": "合成批次"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private path", response.text)

    def test_dispatch_result_recovery_and_failed_only_retry(self):
        fid = self.upload()
        value = self.post("/api/workbench/batches", {"name": "合成批次"}).json()
        batch_id = value["operation_id"]
        self.post(f"/api/workbench/batches/{batch_id}/files", {"files": [{"file_id": fid}]})
        store = self.f.app.state.file_batches
        asyncio.run(store.dispatch(self.f.service, self.f.reader))
        task_id = store.read_owned(batch_id, "legacy:alice")["files"][0]["task_id"]
        task = self.f.service.repository.get(task_id, "alice")
        task["files"][0]["status"] = "failed"
        task["status"] = "failed"
        self.f.service.repository.save(task)
        store.reconcile(self.f.service.repository)
        self.assertEqual(store.read_owned(batch_id, "legacy:alice")["files"][0]["status"], "failed")
        self.post(f"/api/workbench/batches/{batch_id}/retry")
        retried = store.read_owned(batch_id, "legacy:alice")
        self.assertEqual(retried["files"][0]["status"], "queued")
        self.assertEqual(retried["files"][0]["attempt"], 1)

    def test_admin_does_not_reassign_owner_for_legacy_metadata(self):
        import json
        fid,_=self.f.upload_task()
        metadata=self.f.reader.root('alice')/(fid+'.json')
        value=json.loads(metadata.read_text(encoding='utf-8'));value.pop('owner_id',None)
        metadata.write_text(json.dumps(value),encoding='utf-8')
        self.f.app.state.auth_registry.replace({'a'*32:dict(principal_id='admin-person',owner_id='admin-owner',roles=['ADMIN'],review_owner_scopes=[],credential_status='active')})
        batch=self.post('/api/workbench/batches',{'name':'合成历史文件'}).json()
        response=self.post('/api/workbench/batches/'+batch['operation_id']+'/files',{'files':[{'file_id':fid}]})
        self.assertEqual(response.status_code,200,response.text)
        saved=self.f.app.state.file_batches.read_owned(batch['operation_id'],'admin-person')
        self.assertEqual(saved['files'][0]['owner_id'],'alice')

    def test_workbench_openapi_has_revision_protocol_and_typed_routes(self):
        response=self.f.get('/api/openapi.json')
        self.assertEqual(response.status_code,200)
        schema=response.json()
        self.assertEqual(schema['info']['x-contract-version'],'frontend-api-v0.2.3-workbench-1')
        for path,method in [('/api/workbench/documents','get'),('/api/workbench/selections','post'),
                            ('/api/workbench/review-batches','post'),('/api/workbench/releases/{release_id}/publish','post'),
                            ('/api/review/{parse_id}/reviewed-text','get')]:
            operation=schema['paths'][path][method]
            self.assertTrue(operation['security'])
            for status in ('401','403','404','409','422','503'):
                self.assertIn(status,operation['responses'])
        action=schema['components']['schemas']['ReviewAction']
        self.assertIn('revision_scope',action['properties'])
        self.assertFalse(action.get('additionalProperties',True))
        self.assertEqual(schema['components']['schemas']['KnowledgeJobCheck']['properties']['document']['$ref'],
                         '#/components/schemas/KnowledgeJobStatus')

    def test_slow_parser_does_not_stop_dispatch_of_other_batch_files(self):
        first=self.upload()
        second=self.f.client.post('/api/parse/files?file_name=second.pdf',headers=self.f.auth,content=self.f.data+b' second').json()['file_id']
        batch=self.post('/api/workbench/batches',{'name':'合成慢任务调度'}).json()['operation_id']
        self.post('/api/workbench/batches/'+batch+'/files',{'files':[{'file_id':first},{'file_id':second}]})
        async def verify():
            started=asyncio.Event();blocked=asyncio.Event()
            async def slow_parse(task_id):
                started.set();await blocked.wait()
            with patch.object(self.f.service,'run',side_effect=slow_parse):
                async with self.f.app.router.lifespan_context(self.f.app):
                    await asyncio.wait_for(started.wait(),3)
                    for _ in range(40):
                        if len(self.f.service.repository.owned_tasks('alice'))==2:break
                        await asyncio.sleep(0.05)
                    self.assertEqual(len(self.f.service.repository.owned_tasks('alice')),2)
        asyncio.run(verify())

    def test_error_contract_is_independent_of_eager_router_annotation(self):
        schema=self.f.app.openapi()
        response=schema['paths']['/api/workbench/documents']['get']['responses']
        for status in ('401','403','404','409','422','429','503'):
            response.pop(status,None)
        rebuilt=self.f.app.openapi()
        for status in ('401','403','404','409','422','429','503'):
            error=rebuilt['paths']['/api/workbench/documents']['get']['responses'][status]
            self.assertEqual(error['content']['application/json']['schema'],
                             {'$ref':'#/components/schemas/DocumentDeletionError'})
