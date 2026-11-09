"""Focused safety/compatibility tests for production dual-engine orchestration."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import asyncio
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx

from qa_core.document_parsing.config import ParsingConfig
from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter
from qa_core.document_parsing.mineru_api import create_app
from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_official import OfficialMinerUClient
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService
from tests.dual_engine_adapter import OfficialFixture, ScenarioRuntime
from tests.test_v02_dual_engine import make_source


class DualEnginePolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = MinerUConfig(enabled=True, mode='remote', provider='official', api_url='https://mineru.net/api',
                                   api_key='synthetic-token', result_dir=self.root, poll_interval=0, max_polls=3)
        self.fixture = OfficialFixture()
        self.runtime = ScenarioRuntime({'local_confidence': 0.1})
        self.grants = {}

    def service(self, **policy):
        router = DualEngineRouter(DualEngineConfig(enabled=True, cloud_enabled=True, min_request_interval=0, **policy),
                                  self.remote, grants=self.grants,
                                  parser_factory=lambda: DocumentParser(ParsingConfig(), runtime=self.runtime),
                                  client_factory=lambda config: OfficialMinerUClient(config, transport=httpx.MockTransport(self.fixture.handle)))
        return MinerUService(replace(self.remote, mode='local', provider='self_hosted', api_url=''),
                             TaskRepository(self.root / 'tasks.sqlite3'), dual_router=router)

    def authorize(self, source, **options):
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        self.grants.setdefault('alice', {})[sha] = {'authorization_id': 'synthetic-approval',
                                                  'expires_at': time.time() + 300, **options}

    async def run_source(self, service, source, **options):
        task, _ = await service.submit('alice', 'synthetic-request', [(source.name, source)], parse_options=options)
        await service.run(task['id'])
        task = service.repository.get(task['id'])
        file = task['files'][0]
        result = json.loads((Path(file['local_result_path']) / 'normalized.json').read_text(encoding='utf-8'))
        return task, result

    async def test_request_flag_cannot_grant_transfer(self):
        source = make_source(self.root, 'png')
        _, result = await self.run_source(self.service(), source, allow_cloud_fallback=True)
        self.assertEqual(self.fixture.submissions, 0)
        self.assertEqual(result['quality']['routing_trace']['failure_reason'], 'file_authorization_required')

    async def test_expired_and_sensitive_grants_are_denied(self):
        source = make_source(self.root, 'png')
        self.authorize(source, sensitive=True)
        _, result = await self.run_source(self.service(), source, allow_cloud_fallback=True)
        self.assertEqual(self.fixture.submissions, 0)
        self.assertEqual(result['quality']['routing_trace']['failure_reason'], 'sensitive_transfer_denied')

    async def test_expired_and_nonfinite_expiry_cannot_authorize(self):
        source = make_source(self.root, 'png')
        for expiry in [time.time() - 1, float('nan')]:
            self.authorize(source, expires_at=expiry)
            service = self.service()
            task = {'owner': 'alice', 'parse_options': {'allow_cloud_fallback': True}}
            file = {'source_path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
            self.assertFalse(service.dual_router.authorization(task, file)[0])

    async def test_corpus_and_disabled_cloud_cannot_be_overridden_by_request(self):
        source = make_source(self.root, 'png')
        self.authorize(source, allow_sensitive=True)
        service = self.service()
        with patch.dict('os.environ', {'MARKET_REGULATION_TEST_CORPUS': str(self.root)}):
            _, result = await self.run_source(service, source, allow_cloud_fallback=True)
        self.assertEqual(self.fixture.submissions, 0)
        self.assertEqual(result['quality']['routing_trace']['failure_reason'], 'corpus_transfer_denied')
        service.dual_router.config = replace(service.dual_router.config, cloud_enabled=False)
        task = {'owner': 'alice', 'parse_options': {'allow_cloud_fallback': True}}
        file = {'source_path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        self.assertFalse(service.dual_router.authorization(task, file)[0])

    async def test_mixed_batch_only_authorized_hash_can_upload(self):
        source = make_source(self.root, 'png')
        other = self.root / 'other.png'
        other.write_bytes(source.read_bytes() + b'synthetic distinct hash')
        self.authorize(source)
        service = self.service()
        task, _ = await service.submit('alice', 'mixed', [(source.name, source), (other.name, other)],
                                       parse_options={'allow_cloud_fallback': True})
        await service.run(task['id'])
        self.assertEqual(self.fixture.submissions, 1)
        stored = service.repository.get(task['id'])
        self.assertEqual(stored['status'], 'completed')
        self.assertEqual(stored['files'][1]['selected_engine'], ['paddle_ocr'])

    async def test_call_budget_applies_to_transport_attempts(self):
        source = make_source(self.root, 'png')
        self.authorize(source)
        task, result = await self.run_source(self.service(max_cloud_calls=2), source, allow_cloud_fallback=True)
        self.assertEqual(len(self.fixture.calls), 2)
        trace = result['quality']['routing_trace']
        self.assertEqual(trace['usage']['calls'], 2)
        self.assertEqual(trace['selected_engine'], ['paddle_ocr'])
        self.assertTrue(trace['failure_reason'])
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(result['parsing_status'], 'needs_review')

    async def test_file_and_page_budgets_stop_before_unapproved_transfer(self):
        source = make_source(self.root, 'png')
        other = self.root / 'other.png'
        other.write_bytes(source.read_bytes() + b'another synthetic hash')
        self.authorize(source)
        self.authorize(other)
        service = self.service(max_cloud_files=1)
        task, _ = await service.submit('alice', 'limited-files', [(source.name, source), (other.name, other)],
                                       parse_options={'allow_cloud_fallback': True})
        await service.run(task['id'])
        self.assertEqual(self.fixture.submissions, 1)
        self.assertEqual(service.repository.get(task['id'])['files'][1]['fallback_reason'], 'cloud_task_budget_exhausted')
        self.fixture.calls.clear()
        self.fixture.submissions = 0
        import fitz
        pdf_path = self.root / 'two-pages.pdf'
        with fitz.open() as pdf:
            pdf.new_page().insert_text((40, 50), 'Synthetic first page')
            pdf.new_page().insert_text((40, 50), 'Synthetic second page')
            pdf.save(pdf_path)
        self.authorize(pdf_path)
        limited = self.service(max_cloud_pages=1)
        task, _ = await limited.submit('alice', 'limited-pages', [(pdf_path.name, pdf_path)],
                                       parse_options={'strategy': 'remote', 'allow_cloud_fallback': True})
        await limited.run(task['id'])
        self.assertEqual(self.fixture.calls, [])
        self.assertEqual(limited.repository.get(task['id'])['files'][0]['fallback_reason'], 'cloud_task_budget_exhausted')

    async def test_ocr_failure_can_fallback_but_both_failures_remain_failed(self):
        source = make_source(self.root, 'png')
        self.runtime.fail = True
        self.authorize(source)
        service = self.service()
        task, result = await self.run_source(service, source, allow_cloud_fallback=True)
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(result['quality']['routing_trace']['raw_results']['local']['parsing_status'], 'failed')
        self.assertEqual(result['source_location']['selected_engine'], ['mineru_official'])
        self.grants.clear()
        task, _ = await service.submit('alice', 'both-unavailable', [(source.name, source)],
                                       parse_options={'allow_cloud_fallback': True})
        await service.run(task['id'])
        task = service.repository.get(task['id'])
        self.assertEqual(task['status'], 'failed')
        self.assertTrue(task['files'][0]['local_result_path'])
        self.assertTrue(task['files'][0]['requires_review'])

    async def test_revoked_authorization_prevents_source_upload(self):
        source = make_source(self.root, 'png')
        self.authorize(source)
        original = self.fixture.handle
        def handle(request):
            response = original(request)
            if request.method == 'POST':
                self.grants.clear()
            return response
        self.fixture.handle = handle
        _, result = await self.run_source(self.service(), source, allow_cloud_fallback=True)
        self.assertFalse(self.fixture.uploaded)
        self.assertEqual(self.fixture.submissions, 1)
        self.assertIn('local', result['quality']['routing_trace']['raw_results'])

    async def test_unknown_create_outcome_does_not_repeat_on_retry(self):
        source = make_source(self.root, 'png')
        self.authorize(source)
        self.fixture.failure = 'timeout'
        service = self.service()
        task, result = await self.run_source(service, source, allow_cloud_fallback=True)
        await service.run(task['id'])
        self.assertEqual(self.fixture.submissions, 1)
        self.assertIn('local', result['quality']['routing_trace']['raw_results'])

    async def test_interruption_after_create_resumes_same_remote_task(self):
        source = make_source(self.root, 'png')
        self.authorize(source)
        service = self.service()
        original = self.fixture.handle
        interrupted = False
        def handle(request):
            nonlocal interrupted
            if request.method == 'GET' and not interrupted:
                interrupted = True
                raise asyncio.CancelledError()
            return original(request)
        self.fixture.handle = handle
        task, _ = await service.submit('alice', 'interrupted', [(source.name, source)],
                                       parse_options={'allow_cloud_fallback': True})
        with self.assertRaises(asyncio.CancelledError):
            await service.run(task['id'])
        await service.run(task['id'])
        stored = service.repository.get(task['id'])
        self.assertEqual(stored['status'], 'completed')
        self.assertEqual(self.fixture.submissions, 1)
        self.assertEqual(self.runtime.calls, ['ocr'])
        self.assertEqual(stored['files'][0]['selected_engine'], ['mineru_official'])

    async def test_local_strategy_never_submits_even_with_authorization(self):
        source = make_source(self.root, 'png')
        self.authorize(source)
        await self.run_source(self.service(), source, strategy='local', allow_cloud_fallback=True)
        self.assertEqual(self.fixture.submissions, 0)

    async def test_options_are_part_of_idempotency_identity(self):
        source = make_source(self.root, 'png')
        service = self.service()
        await service.submit('alice', 'same-key', [(source.name, source)], parse_options={'strategy': 'local'})
        with self.assertRaises(MinerUError) as context:
            await service.submit('alice', 'same-key', [(source.name, source)], parse_options={'strategy': 'remote'})
        self.assertEqual(context.exception.code, 'idempotency_conflict')

    async def test_api_old_request_is_local_and_new_options_validated(self):
        service = self.service()
        app = create_app(service.config, tokens={'x' * 32: 'alice'}, service=service)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://local',
                                    headers={'Authorization': 'Bearer ' + 'x' * 32}) as http:
            source = make_source(self.root, 'pdf')
            upload = await http.post('/api/parse/files?file_name=synthetic.pdf', content=source.read_bytes())
            self.assertEqual(upload.status_code, 201)
            body = {'file_ids': [upload.json()['file_id']]}
            submitted = await http.post('/api/parse/tasks', json=body, headers={'Idempotency-Key': 'old-client'})
            self.assertEqual(submitted.status_code, 202)
            await service.run(submitted.json()['task_id'])
            result = await http.get('/api/parse/tasks/' + submitted.json()['task_id'] + '/results')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['results'][0]['document']['source_location']['selected_engine'], ['native'])
            for options in [{'strategy': []}, {'allow_cloud_fallback': 'true'}, {'sensitive': 1}]:
                invalid = await http.post('/api/parse/tasks', json={**body, **options}, headers={'Idempotency-Key': 'invalid'})
                self.assertEqual(invalid.status_code, 400)
            denied = await http.get('/api/parse/tasks/' + submitted.json()['task_id'], headers={'Authorization': 'Bearer ' + 'y' * 32})
            self.assertEqual(denied.status_code, 401)
        self.assertEqual(self.fixture.submissions, 0)
