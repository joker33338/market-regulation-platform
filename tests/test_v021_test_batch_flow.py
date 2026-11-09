"""TEST_BATCH走既有MockHTTP链，验证匿名命名、撤销和全链记账。"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import httpx

from qa_core.document_parsing.config import ParsingConfig
from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_official import OfficialMinerUClient
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService
from qa_core.document_parsing.test_batch_authorization import TrustedTestBatch
from tests.dual_engine_adapter import OfficialFixture, ScenarioRuntime
from tests.test_v02_dual_engine import make_source


class BatchHTTPFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = make_source(self.root, 'png')
        self.sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.path = self.root/'manifest.json'
        self.manifest = dict(version=1, owner='alice', batch_id='synthetic', revoked=False,
            expires_at=time.time()+300, entries=[dict(sha256=self.sha, source_qualified=True,
            sensitivity_confirmed=True, sensitive=False, third_party_transfer_rights_confirmed=True,
            source_evidence='纯合成夹具')])
        self.path.write_text(json.dumps(self.manifest))
        self.authority = TrustedTestBatch(self.path, owner='alice', batch_id='synthetic')
        self.fixture = OfficialFixture(); self.requests = []

    def service(self, revoke_after_create=False):
        def handle(request):
            self.requests.append((request.method, request.url.path))
            if request.method == 'POST':
                body = json.loads(request.content)
                self.assertTrue(body['files'][0]['name'].startswith('sample-'))
                self.assertNotEqual(body['files'][0]['name'], self.source.name)
            response = self.fixture.handle(request)
            if revoke_after_create and request.method == 'POST':
                self.manifest['revoked'] = True
                self.path.write_text(json.dumps(self.manifest))
            return response
        remote = MinerUConfig(enabled=True, mode='remote', provider='official', api_url='https://mineru.net/api',
            api_key='synthetic-token', result_dir=self.root, poll_interval=0, max_polls=3)
        router = DualEngineRouter(DualEngineConfig(enabled=True, cloud_enabled=True, environment='test',
            authorization_mode='TEST_BATCH', min_request_interval=0), remote, batch_authorizer=self.authority,
            parser_factory=lambda: DocumentParser(ParsingConfig(), runtime=ScenarioRuntime({'local_confidence':0.1})),
            client_factory=lambda cfg: OfficialMinerUClient(cfg, transport=httpx.MockTransport(handle)))
        return MinerUService(replace(remote, mode='local', provider='self_hosted', api_url=''),
            TaskRepository(self.root/'tasks.sqlite3'), dual_router=router)

    async def execute(self, service):
        task, _ = await service.submit('alice', 'stable-key', [(self.source.name, self.source)],
            parse_options=dict(strategy='remote', allow_cloud_fallback=True))
        self.assertEqual(task['authorization_context']['batch_id'], 'synthetic')
        await service.run(task['id'])
        return service.repository.get(task['id'])

    async def test_anonymous_full_chain_charges_all_network_boundaries(self):
        service = self.service()
        with patch.dict('os.environ', {'MARKET_REGULATION_TEST_CORPUS':str(self.root)}):
            task = await self.execute(service)
        self.assertEqual(task['status'], 'completed')
        ledger = json.loads(self.authority.usage_path.read_text())
        self.assertEqual(ledger['calls'], len(self.requests))
        self.assertEqual(ledger['methods']['POST'], 1)
        self.assertEqual(ledger['methods']['PUT'], 1)
        self.assertGreaterEqual(ledger['methods']['GET'], 2)
        self.assertTrue((self.root/task['id']/task['files'][0]['id']/'local-candidate.json').exists())

    async def test_revocation_after_create_prevents_upload(self):
        await self.execute(self.service(revoke_after_create=True))
        self.assertEqual([m for m, _ in self.requests], ['POST'])
        self.assertEqual(json.loads(self.authority.usage_path.read_text())['calls'], 1)

    async def test_idempotency_does_not_rebind_task_to_new_batch(self):
        service = self.service()
        task, _ = await service.submit('alice', 'stable-key', [(self.source.name, self.source)])
        service.dual_router.batch_authorizer = TrustedTestBatch(self.path, owner='alice', batch_id='other')
        from qa_core.document_parsing.mineru_client import MinerUError
        with self.assertRaises(MinerUError):
            await service.submit('alice', 'stable-key', [(self.source.name, self.source)])
        self.assertEqual(service.repository.get(task['id'])['authorization_context']['batch_id'], 'synthetic')

    async def test_new_task_does_not_repeat_same_mode_post(self):
        from qa_core.document_parsing.mineru_client import MinerUError
        task = dict(owner='alice', parse_options=dict(strategy='remote', sensitive=False))
        self.authority.bind_task(task)
        file = dict(source_path=str(self.source), sha256=self.sha)
        self.authority.reserve_request(task, file, 'POST')
        task['id'] = 'another-task'
        fresh = TrustedTestBatch(self.path, owner='alice', batch_id='synthetic')
        with self.assertRaises(MinerUError):
            fresh.reserve_request(task, file, 'POST')
        self.assertEqual(json.loads(fresh.usage_path.read_text())['calls'], 1)

    async def test_revocation_during_rate_wait_prevents_first_post(self):
        async def revoke(delay):
            self.manifest['revoked'] = True
            self.path.write_text(json.dumps(self.manifest))
        with patch('qa_core.document_parsing.dual_engine.asyncio.sleep', side_effect=revoke):
            await self.execute(self.service())
        self.assertEqual(self.requests, [])
        self.assertFalse(self.authority.usage_path.exists())

    async def test_duplicate_manifest_fields_fail_closed(self):
        raw = json.dumps(self.manifest).replace('"revoked": false', '"revoked": false, "revoked": false')
        self.path.write_text(raw)
        task = dict(owner='alice', parse_options=dict(sensitive=False))
        self.authority.bind_task(task)
        self.assertFalse(self.authority.authorize(task, dict(source_path=str(self.source), sha256=self.sha))[0])

    async def test_factory_accepts_properly_bound_batch_service(self):
        from qa_core.document_parsing.mineru_api import create_app
        service = self.service()
        app = create_app(service.config, tokens={'a'*32:'alice'}, service=service,
                         dual_config=service.dual_router.config)
        self.assertIsNotNone(app)
