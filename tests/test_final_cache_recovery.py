"""最终 normalized 缓存的成功、失效及资源限制恢复，不使用真实服务。"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
from qa_core.document_parsing.config import ParsingConfig
from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter, persist_result
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService
from qa_core.document_parsing.schemas import DocumentResult, PageResult


class FinalCacheRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def recover(self, *, limits=None, corrupt=None, pdf=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/('synthetic.pdf' if pdf else 'synthetic.png')
            if pdf:
                import fitz
                with fitz.open() as document:
                    document.new_page();document.new_page();document.save(source)
            else:Image.new('RGB',(10,10),'white').save(source)
            original=source.read_bytes();sha=hashlib.sha256(original).hexdigest()
            config=MinerUConfig(enabled=True,mode='local',result_dir=root/'results')
            remote=replace(config,mode='remote',provider='official',api_url='https://mineru.net/api')
            parser=MagicMock(side_effect=AssertionError('缓存不应重新 OCR'))
            cloud=MagicMock(side_effect=AssertionError('缓存不应访问云端'))
            sink=MagicMock();sink.save.return_value='synthetic-id'
            router=DualEngineRouter(DualEngineConfig(enabled=True),remote,parser_factory=parser,client_factory=cloud)
            service=MinerUService(config,TaskRepository(root/'tasks.sqlite3'),result_sink=sink,dual_router=router)
            task,_=await service.submit('qa','stable',[(source.name,source)])
            file=task['files'][0];folder=config.result_dir/task['id']/file['id']
            result=DocumentResult(sha,source.name,source.suffix,{},pages=[PageResult(1,'ocr',raw_text='synthetic retained text')])
            result.quality['routing_trace']=dict(selected_engine=['paddle_ocr'],failure_reason=None,fallback_reason=[])
            if corrupt=='empty':result.pages=[]
            if corrupt=='sha':result.document_id='wrong-sha'
            if corrupt=='version':result.schema_version='unknown'
            persist_result(folder/'normalized.json',result)
            if corrupt=='json':(folder/'normalized.json').write_text('{invalid',encoding='utf-8')
            before=(folder/'normalized.json').read_bytes()
            file.update(status='failed',local_result_path=str(folder));task['status']='failed';service.repository.save(task)
            with patch.object(ParsingConfig,'from_env',return_value=limits or ParsingConfig()):
                await service.resume(task['id'],'qa');await service.run(task['id'])
                # 再次运行成功任务不再次保存，不改变结果摘要。
                await service.run(task['id'])
            updated=service.repository.get(task['id'],'qa')
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual((folder/'normalized.json').read_bytes(),before)
            parser.assert_not_called();cloud.assert_not_called()
            return updated,sink.save.call_count

    async def test_valid_final_cache_saves_once_without_parsing(self):
        task,calls=await self.recover()
        self.assertEqual(task['status'],'completed');self.assertEqual(calls,1)

    async def test_invalid_cache_never_reaches_sink(self):
        for corrupt in ('empty','sha','json','version'):
            with self.subTest(corrupt=corrupt):
                task,calls=await self.recover(corrupt=corrupt)
                self.assertEqual(task['status'],'failed');self.assertEqual(calls,0)

    async def test_current_file_and_page_limits_apply_to_final_cache(self):
        for limits,pdf,code in [(ParsingConfig(max_file_bytes=1),False,'file_byte_limit'),
                                (ParsingConfig(max_pages=1),True,'pdf_page_limit')]:
            with self.subTest(code=code):
                task,calls=await self.recover(limits=limits,pdf=pdf)
                self.assertEqual(task['status'],'failed');self.assertEqual(calls,0)
                self.assertEqual(task['files'][0]['error']['code'],code)
