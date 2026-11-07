"""仅对QA新建的专用PostgreSQL夹具执行；不使用业务连接。"""
import os
import unittest
from uuid import uuid4


@unittest.skipUnless(os.getenv('QA_ISOLATED_PG_DSN'), '需要QA专用隔离PostgreSQL夹具')
class Round01PostgresAcceptance(unittest.TestCase):
    def setUp(self):
        import psycopg2
        from psycopg2.extensions import parse_dsn
        self.dsn = os.environ['QA_ISOLATED_PG_DSN']
        parameters = parse_dsn(self.dsn)
        self.assertEqual(parameters['dbname'], 'qa_round01')
        self.assertEqual(parameters['host'], 'qa-postgres')
        self.connection = psycopg2.connect(self.dsn)
        self.addCleanup(self.connection.close)
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('qa.round01_isolated',true)")
            self.assertEqual(cursor.fetchone()[0], 'test-only')
        self.connection.rollback()

    def fixture(self):
        from qa_core.document_parsing.schemas import DocumentResult, PageResult, LayoutBlock, TableResult
        task, file = {'id':uuid4().hex,'owner':'synthetic-qa'}, {'id':uuid4().hex,'source_file_id':'synthetic-source'}
        page = PageResult(1,'synthetic',raw_text='synthetic original',normalized_text='synthetic original',
                          layout_blocks=[LayoutBlock('b1','text','synthetic block')],
                          tables=[TableResult('t1',html='<table></table>',rows=[['100']],cells=[
                              {'row':0,'column':0,'rowspan':1,'colspan':1,'text':'100','header':True}])])
        result = DocumentResult('synthetic-sha','synthetic.pdf','.pdf',{'mineru_task_id':'remote-t','mineru_file_id':'remote-f'},
                                pages=[page],requires_review=True,quality={'markdown':'synthetic markdown'})
        return task,file,result

    def row(self, query, parameters):
        with self.connection.cursor() as cursor:
            cursor.execute(query,parameters)
            return cursor.fetchone()

    def test_mapping_idempotency_conflict_preserves_existing_result(self):
        from qa_core.storage.parsing_results import PostgresResultSink
        from qa_core.document_parsing.mineru_client import MinerUError
        task,file,result=self.fixture()
        sink=PostgresResultSink(self.dsn)
        pid=sink.save(task,file,result)
        self.assertEqual(sink.save(task,file,result),pid)
        for table in ['documents','pages','blocks','tables','cells']:
            self.assertEqual(self.row('SELECT COUNT(*) FROM document_review.'+table+' WHERE parse_id=%s',(pid,))[0],1)
        saved=self.row('SELECT source_location,raw_text,markdown_content FROM document_review.documents WHERE parse_id=%s',(pid,))
        self.assertEqual(saved[0]['local_task_id'],task['id'])
        self.assertEqual(saved[0]['source_file_id'],file['source_file_id'])
        self.assertEqual(saved[0]['mineru_file_id'],'remote-f')
        self.assertEqual(saved[1: ],('synthetic original','synthetic markdown'))
        self.assertEqual(self.row('SELECT cell_text,row_span,is_header FROM document_review.cells WHERE parse_id=%s',(pid,)),('100',1,True))
        result.pages[0].raw_text='changed synthetic content'
        with self.assertRaisesRegex(MinerUError,'database_result_conflict'):
            sink.save(task,file,result)
        self.assertEqual(self.row('SELECT raw_text FROM document_review.documents WHERE parse_id=%s',(pid,))[0],'synthetic original')

    def test_cell_failure_rolls_back_all_levels_and_preserves_prior_row(self):
        import psycopg2
        from qa_core.storage.parsing_results import PostgresResultSink
        from qa_core.utils import stable_hash
        sink=PostgresResultSink(self.dsn)
        task,file,result=self.fixture()
        previous=sink.save(task,file,result)
        broken_task,broken_file,broken=self.fixture()
        broken.pages[0].tables[0].cells[0]['rowspan']=None
        pid=stable_hash('parsing-result-v1',broken_task['owner'],broken_task['id'],broken_file['id'])
        with self.assertRaises(psycopg2.IntegrityError):
            sink.save(broken_task,broken_file,broken)
        for table in ['documents','pages','blocks','tables','cells']:
            self.assertEqual(self.row('SELECT COUNT(*) FROM document_review.'+table+' WHERE parse_id=%s',(pid,))[0],0)
        self.assertEqual(self.row('SELECT COUNT(*) FROM document_review.documents WHERE parse_id=%s',(previous,))[0],1)
