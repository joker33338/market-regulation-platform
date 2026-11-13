"""真实原生解析任务元数据与数据库重试的回归测试。"""
import json
from pathlib import Path
import tempfile
import unittest

import fitz

from qa_core.document_parsing.mineru_api import public
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService


class LocalTaskMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_name_engine_and_exact_cached_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/('a'*32+'.pdf')
            with fitz.open() as document:
                page=document.new_page()
                page.insert_text((50,60),'Synthetic evidence for native extraction and database retry.')
                document.save(source)
            records=[]

            class RetrySink:
                def save(self,task,file,result):
                    records.append(result.to_json())
                    if len(records)==1:
                        raise RuntimeError('合成数据库失败')
                    return 'synthetic-parse-id'

            repository=TaskRepository(root/'tasks.sqlite3')
            service=MinerUService(MinerUConfig(enabled=True,mode='local',result_dir=root),repository,result_sink=RetrySink())
            task,_=await service.submit('synthetic-owner','synthetic-key',[('original-upload.pdf',source,'a'*32)])
            await service.run(task['id'])
            self.assertEqual(repository.get(task['id'])['status'],'failed')
            await service.resume(task['id'],'synthetic-owner')
            await service.run(task['id'])
            finished=repository.get(task['id'])
            self.assertEqual(finished['status'],'completed')
            self.assertEqual(records[0],records[1])
            result=json.loads(records[0])
            self.assertEqual(result['file_name'],'original-upload.pdf')
            self.assertEqual(public(finished)['files'][0]['selected_engine'],['native_pdf'])
            self.assertEqual(public(finished)['files'][0]['requires_review'],result['requires_review'])
            self.assertEqual(finished['files'][0]['database_parse_id'],'synthetic-parse-id')
