"""独立收尾验收：旧的最终结果缓存也不能绕过当前资源限额。"""
from dataclasses import replace
from contextlib import nullcontext
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


class FinalResultCacheSafety(unittest.IsolatedAsyncioTestCase):
    async def test_current_limits_reject_pre_database_final_cache_in_all_strategies(self):
        """QRC-001：DB失败前写出的normalized缓存恢复时仍须SAFE_REJECT。"""
        for strategy,default_limit in [('local',False),('auto',False),('remote',False),('auto',True)]:
            with self.subTest(strategy=strategy,production_default_limit=default_limit),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source=root/'synthetic.png'
                side=4500 if default_limit else 10
                Image.new('RGB',(side,side),'white').save(source)
                sha=hashlib.sha256(source.read_bytes()).hexdigest()
                config=MinerUConfig(enabled=True,mode='local',result_dir=root/'results')
                remote=replace(config,mode='remote',provider='official',api_url='https://mineru.net/api',api_key='synthetic-only')
                client=MagicMock(side_effect=AssertionError('资源拒绝不得尝试外传'))
                router=DualEngineRouter(DualEngineConfig(enabled=True,cloud_enabled=True),remote,client_factory=client)
                class RecordingSink:
                    def __init__(self):self.calls=0
                    def save(self,*args):self.calls+=1;return 'synthetic-insert-must-not-happen'
                sink=RecordingSink();repository=TaskRepository(root/'tasks.sqlite3')
                service=MinerUService(config,repository,result_sink=sink,dual_router=router)
                task,_=await service.submit('qa','stable-'+strategy,[(source.name,source,'synthetic-source')],
                    parse_options=dict(strategy=strategy,allow_cloud_fallback=True,sensitive=False))
                file=task['files'][0];directory=config.result_dir/task['id']/file['id']
                old=DocumentResult(sha,source.name,'.png',{'file_path':str(source)},
                    pages=[PageResult(1,'ocr',raw_text='以前通过处理的合成正文。')],requires_review=True)
                old.quality['routing_trace']=dict(initial_engine=['paddle_ocr'],selected_engine=['paddle_ocr'],
                    fallback_reason=[],failure_reason=None,route_reason='local_quality_sufficient',requires_review=True)
                persist_result(directory/'normalized.json',old)
                prior=(directory/'normalized.json').read_bytes()
                file.update(status='failed',local_result_path=str(directory),error={'code':'synthetic_database_unavailable'})
                task['status']='failed';repository.save(task)
                # 同时覆盖小夹具与真实默认20MP限额，均不运行模型或真实数据库。
                limits=nullcontext() if default_limit else patch.object(ParsingConfig,'from_env',return_value=ParsingConfig(max_image_pixels=50))
                with limits:
                    current_limit=ParsingConfig.from_env().max_image_pixels
                    self.assertGreater(side*side,current_limit)
                    await service.resume(task['id'],'qa');await service.run(task['id'])
                updated=repository.get(task['id'],'qa')
                print(json.dumps(dict(case='QRC-001',strategy=strategy,actual_status=updated['status'],
                                      source_pixels=side*side,current_limit=current_limit,
                                      sink_calls=sink.calls,cloud_client_calls=client.call_count)))
                self.assertEqual(updated['status'],'failed','最终结果缓存不能免除当前安全限额')
                self.assertEqual(updated['files'][0]['error']['code'],'image_pixel_limit')
                self.assertEqual(sink.calls,0,'SAFE_REJECT结果禁止进入sink')
                client.assert_not_called()
                self.assertEqual((directory/'normalized.json').read_bytes(),prior,'历史缓存保留供审计')
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),sha)


if __name__=='__main__':unittest.main()
