"""浏览器驱动真实隔离PG/MySQL流程；合成PDF和固定测试向量不代表OCR或模型验收。"""
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import unittest
from uuid import uuid4

import fitz
import uvicorn
from deploy.release.application import VueFiles
from qa_core.api.read_store import ReviewReader
from qa_core.document_parsing.schemas import DocumentResult,PageResult,LayoutBlock
from qa_core.storage.database import Database
from qa_core.storage.mysql_review_ledger import MySQLReviewLedger
from qa_core.storage.parsing_results import PostgresResultSink
from tests import test_frontend_workflow_pg as baseline
from tests import test_ingestion_api as fixtures


@unittest.skipUnless(os.getenv('WORKBENCH_BROWSER_CHECKS')=='1','需要显式浏览器和独立数据库配置')
class WorkbenchBrowserPGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        baseline.FrontendWorkflowPGTests.setUpClass.__func__(cls)
        import psycopg2
        with psycopg2.connect(cls.admin) as connection,connection.cursor() as cursor:
            cursor.execute(Path('scripts/sql/20261116_reviewed_article_range_up.sql').read_text(encoding='utf-8'))

    def test_browser_prepare_revision_bulk_review_build_publish_and_library(self):
        f=fixtures.IngestionAPITests();f.setUp();self.addCleanup(f.doCleanups)
        reader=f.f.reader;reader.review=ReviewReader(self.runtime);reader.kb_dsn=self.runtime
        reader.kb_factory=lambda:Database(pg_dsn=self.runtime);reader.kb_write_factory=reader.kb_factory
        class TestVectors:
            dimension=1024
            signature='synthetic-browser-vectors-1024'
            def embed_documents(self,texts):return [[1.0]+[0.0]*1023 for _ in texts]
        from tests.test_workbench_real_pg import workflow_embeddings
        reader.embeddings_factory=workflow_embeddings(TestVectors)
        app=f.f.app;app.state.review_ledger=MySQLReviewLedger(self.mysql)
        nonce=uuid4().hex[:8];items=[]
        for index,kind in enumerate(['law','law','case']):
            name='flow-'+nonce+'-'+str(index)+'.pdf'
            pdf=fitz.open();page=pdf.new_page();page.insert_text((50,50),'Synthetic workflow '+nonce+' '+str(index))
            payload=pdf.tobytes();pdf.close()
            upload=f.client.post('/api/parse/files',params={'file_name':name},headers=f.f.auth,content=payload).json()
            title=('合成'+nonce+str(index)+'管理办法') if kind=='law' else ('合成'+nonce+'行政处罚决定书')
            text=title+'\n'+('第一条 合成条款。' if kind=='law' else '当事人某测试主体，案号合成。处罚决定罚款十元。')
            result=DocumentResult(upload['sha256'],name,'pdf',{},pages=[PageResult(1,'synthetic',raw_text=text,layout_blocks=[LayoutBlock('body','text',text)])])
            parse_id=PostgresResultSink(self.admin).save_import('alice','browser-'+nonce,upload['file_id'],result)
            items.append({'file_id':upload['file_id'],'file_name':name,'parse_id':parse_id,'kind':kind,'title':title})
        @asynccontextmanager
        async def lifespan(application):
            # 仅驱动已保存的合成解析副本，不运行OCR或外部服务。
            yield
        app.router.lifespan_context=lifespan
        app.router.routes[:]=[route for route in app.router.routes if getattr(route,'path',None)!='/']
        app.mount('/',VueFiles(directory=str(Path('local/workbench-ui-build').resolve()),html=True))
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error',access_log=False))
        stopped=threading.Event()
        def work():
            while not stopped.wait(0.2):
                app.state.review_batches.tick();app.state.workbench_ingestion.tick()
        thread=threading.Thread(target=server.run,daemon=True);worker=threading.Thread(target=work,daemon=True)
        evidence=Path('local/workbench-evidence/browser-flow-'+nonce);evidence.mkdir(parents=True)
        fixture=evidence/'fixture.json';fixture.write_text(json.dumps({'items':items,'keyword':'flow-'+nonce}),encoding='utf-8')
        thread.start()
        try:
            deadline=time.monotonic()+15
            while not server.started:
                if time.monotonic()>deadline:raise RuntimeError('isolated_http_start_failed')
                time.sleep(0.1)
            worker.start()
            env=os.environ.copy();env.update(WORKBENCH_URL='http://127.0.0.1:'+str(port),WORKBENCH_FLOW_FIXTURE=str(fixture.resolve()),WORKBENCH_EVIDENCE=str(evidence.resolve()))
            run=subprocess.run([os.environ['WORKBENCH_NODE'],'tests/check_workbench_flow_browser.cjs'],env=env,capture_output=True,text=True,encoding='utf-8',timeout=180)
            (evidence/'execution.log').write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
            self.assertEqual(run.returncode,0,'浏览器流程失败；仅在私密证据目录查看细节')
            result=json.loads((evidence/'flow-result.json').read_text(encoding='utf-8'))
            self.assertEqual(result['status'],'PASS');self.assertEqual(result['pageErrors'],[])
            self.assertGreaterEqual(len(result['checks']),6)
            # 原始OCR未被整页修订覆盖，发布版通过独立库查询取得审核副本。
            self.assertNotIn('浏览器整页修订',reader.review.detail('alice',items[0]['parse_id'])['raw_text'])
            published=f.client.get('/api/library/laws',params={'query':nonce},headers=f.f.auth)
            self.assertEqual(published.json()['total'],2)
            self.assertEqual(f.client.get('/api/library/cases',params={'query':nonce},headers=f.f.auth).json()['total'],1)
        finally:
            stopped.set()
            if worker.is_alive():worker.join(timeout=15)
            server.should_exit=True;thread.join(timeout=15)
            self.assertFalse(thread.is_alive(),'隔离HTTP服务必须退出')
