"""SAFE-001：资源拒绝不能经auto/remote或旧候选恢复绕到云端。"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

from qa_core.document_parsing.config import ParsingConfig
from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter, persist_result
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_official import OfficialMinerUClient
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService
from qa_core.document_parsing.schemas import DocumentResult, PageResult
from tests.dual_engine_adapter import OfficialFixture
from tests.test_document_parsing import FakeRuntime


class ReleaseSafetyTests(unittest.IsolatedAsyncioTestCase):
    def test_local_batch_reports_typed_safety_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'synthetic.png'
            Image.new('RGB', (10, 10), 'white').save(source)
            before = source.read_bytes()
            runtime = FakeRuntime()
            with DocumentParser(ParsingConfig(max_image_pixels=50), runtime=runtime) as parser:
                result = parser.parse_batch([source])[0]
            self.assertEqual(result.parsing_status, 'failed')
            self.assertTrue(result.requires_review)
            self.assertEqual(result.quality['safety_rejection'], {'status': 'SAFE_REJECT', 'code': 'image_pixel_limit'})
            self.assertEqual(runtime.calls, [])
            self.assertEqual(source.read_bytes(), before)

    async def run_image(self, *, strategy='auto', cached=False, fail_ocr=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'synthetic.png'
            Image.new('RGB',(10,10),'white').save(source)
            before=source.read_bytes()
            sha=hashlib.sha256(before).hexdigest()
            fixture=OfficialFixture()
            runtime=FakeRuntime()
            runtime.fail=fail_ocr
            limits=ParsingConfig(max_image_pixels=200 if fail_ocr else 50)
            remote=MinerUConfig(enabled=True,mode='remote',provider='official',api_url='https://mineru.net/api',
                                api_key='synthetic-only',result_dir=root,poll_interval=0,max_polls=3)
            router=DualEngineRouter(DualEngineConfig(enabled=True,cloud_enabled=True,min_request_interval=0),remote,
                grants={'alice':{sha:{'authorization_id':'synthetic-grant','expires_at':time.time()+300}}},
                parser_factory=lambda:DocumentParser(limits,runtime=runtime),
                client_factory=lambda config:OfficialMinerUClient(config,transport=httpx.MockTransport(fixture.handle)))
            service=MinerUService(replace(remote,mode='local',provider='self_hosted',api_url=''),
                                 TaskRepository(root/'tasks.sqlite3'),dual_router=router)
            task,_=await service.submit('alice','synthetic-request',[(source.name,source)],
                                        parse_options={'strategy':strategy,'allow_cloud_fallback':True})
            if cached:
                candidate=DocumentResult(sha,source.name,'.png',{},pages=[PageResult(1,'ocr',raw_text='synthetic retained candidate')])
                persist_result(root/task['id']/task['files'][0]['id']/'local-candidate.json',candidate)
            with patch('qa_core.document_parsing.dual_engine.ParsingConfig.from_env',return_value=limits):
                await service.run(task['id'])
            task=service.repository.get(task['id'])
            result=json.loads((Path(task['files'][0]['local_result_path'])/'normalized.json').read_text(encoding='utf-8'))
            self.assertEqual(source.read_bytes(),before)
            return task,result,fixture,runtime

    async def test_auto_and_remote_resource_rejection_make_zero_cloud_requests(self):
        for strategy in ('auto','remote'):
            with self.subTest(strategy=strategy):
                task,result,fixture,runtime=await self.run_image(strategy=strategy)
                self.assertEqual(fixture.calls,[])
                self.assertEqual(runtime.calls,[])
                self.assertEqual(task['status'],'failed')
                self.assertEqual(task['files'][0]['error']['code'],'image_pixel_limit')
                self.assertEqual(result['quality']['safety_rejection']['status'],'SAFE_REJECT')
                self.assertTrue(result['requires_review'])

    async def test_cached_candidate_cannot_bypass_current_input_safety(self):
        for strategy in ('auto', 'local', 'remote'):
            with self.subTest(strategy=strategy):
                task,result,fixture,_=await self.run_image(strategy=strategy,cached=True)
                self.assertEqual(fixture.calls,[])
                self.assertEqual(task['status'],'failed')
                self.assertEqual(result['quality']['routing_trace']['failure_reason'],'image_pixel_limit')
                self.assertIn('synthetic retained candidate',str(result['quality']['routing_trace']['raw_results']))

    async def test_ordinary_ocr_failure_can_still_use_authorized_fallback(self):
        task,result,fixture,_=await self.run_image(fail_ocr=True)
        self.assertEqual(fixture.submissions,1)
        self.assertEqual(task['status'],'completed')
        self.assertEqual(result['quality']['routing_trace']['selected_engine'],['mineru_official'])
