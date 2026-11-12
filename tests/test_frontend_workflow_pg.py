"""独立PG、既有隔离MySQL、合成密码账号的真实数据库端到端验证。"""
import json
import os
from pathlib import Path
import secrets
import unittest
from uuid import uuid4

import psycopg2
from psycopg2.extras import Json

from qa_core.api.read_store import ReviewReader
from qa_core.storage.database import Database
from qa_core.storage.mysql_review_ledger import MySQLReviewLedger
from tests import test_ingestion_api as fixtures


@unittest.skipUnless(os.getenv('FRONTEND_WORKFLOW_TEST_PG_ADMIN_DSN') and os.getenv('REVIEW_MYSQL_TEST_CONFIG'), '需要显式独立PG与隔离MySQL')
class FrontendWorkflowPGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('DELETE_PG_FIXTURE_ISOLATED')!='1':
            raise RuntimeError('必须明确独立PG夹具')
        cls.admin=os.environ['FRONTEND_WORKFLOW_TEST_PG_ADMIN_DSN']
        cls.runtime=os.environ['FRONTEND_WORKFLOW_TEST_PG_DSN']
        cls.mysql=json.loads(Path(os.environ['REVIEW_MYSQL_TEST_CONFIG']).read_text(encoding='utf-8-sig'))
        if not cls.mysql['database'].startswith('market_review_test_'):
            raise RuntimeError('拒绝正式MySQL')
        with psycopg2.connect(cls.admin) as connection,connection.cursor() as cursor:
            cursor.execute('SELECT current_database()')
            if cursor.fetchone()[0]!='qa_round01':
                raise RuntimeError('仅允许全新qa_round01临时库')
            cursor.execute("SELECT to_regnamespace('document_review'),to_regclass('public.mr_active')")
            if any(cursor.fetchone()):
                raise RuntimeError('拒绝覆盖已存在的夹具')
            cursor.execute((Path(__file__).parent/'fixtures'/'round01_document_review.sql').read_text(encoding='utf-8'))
        database=Database(pg_dsn=cls.admin)
        try:
            database.initialize()
        finally:
            database.close()
        with psycopg2.connect(cls.admin) as connection,connection.cursor() as cursor:
            cursor.execute('CREATE ROLE frontend_api_test LOGIN')
            cursor.execute('GRANT USAGE ON SCHEMA public,document_review TO frontend_api_test')
            cursor.execute('GRANT SELECT ON ALL TABLES IN SCHEMA document_review TO frontend_api_test')
            cursor.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO frontend_api_test')
            cursor.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO frontend_api_test')

    def test_password_admin_review_build_publish_search_and_rollback(self):
        fixture=fixtures.IngestionAPITests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        row=fixture.row;row['parse_id']='synthetic-'+uuid4().hex
        fixture.body['documents'][0]['parse_id']=row['parse_id']
        with psycopg2.connect(self.admin) as connection,connection.cursor() as cursor:
            cursor.execute('''INSERT INTO document_review.documents
                (parse_id,document_id,report_sha256,file_name,file_type,parsing_status,requires_review,
                 source_location,quality,raw_text,markdown_content,original_result)
                VALUES (%s,%s,%s,%s,'pdf','needs_review',true,%s,'{}',%s,%s,%s)''',
                (row['parse_id'],row['document_id'],uuid4().hex,row['file_name'],Json(row['source_location']),
                 row['raw_text'],row['markdown_content'],Json(row['original_result'])))
        reader=fixture.f.reader
        reader.review=ReviewReader(self.runtime)
        reader.kb_factory=lambda:Database(pg_dsn=self.runtime)
        reader.kb_write_factory=reader.kb_factory
        class SyntheticVectors:
            # 仅隔离测试向量，不代表BGE-M3真实推理或正式检索质量。
            dimension=1024
            signature='synthetic-test-vectors-1024'
            def embed_documents(self,texts):
                return [[1.0]+[0.0]*1023 for _ in texts]
        reader.embeddings_factory=SyntheticVectors
        fixture.f.app.state.review_ledger=MySQLReviewLedger(self.mysql)
        from scripts.provision_auth_accounts import provision
        account_file=fixture.f.root/'isolated-accounts.json';password=secrets.token_urlsafe(20)
        provision(account_file,'workflow-admin',password)
        fixture.f.app.state.account_store.filename=str(account_file)
        response=fixture.client.post('/api/auth/login',json={'username':'workflow-admin','password':password})
        self.assertEqual(response.status_code,200,response.text)
        fixture.f.auth={'Authorization':'Bearer '+response.json()['access_token']}
        source_before=reader.review.detail('alice',row['parse_id'])
        response=fixture.client.post('/api/review/'+row['parse_id']+'/approve',headers={**fixture.f.auth,'Idempotency-Key':uuid4().hex},
            json={'base_result_id':row['parse_id'],'expected_version':0})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['owner_id'],'alice')
        self.assertNotEqual(response.json()['operator_id'],'alice')
        events_before=fixture.f.app.state.review_ledger.events('alice',row['parse_id'],1,100)
        self.assertEqual(fixture.post('precheck',fixture.body).status_code,200)
        fixture.build()
        database=Database(pg_dsn=self.runtime)
        try:
            self.assertIsNone(database.active_version())
        finally:
            database.close()
        self.assertEqual(fixture.post('publish',{'kb_version':'synthetic-v1','expected_active_version':None}).status_code,200)
        result=fixture.client.post('/api/knowledge/search',headers=fixture.f.auth,json={'query':'合成条文','mode':'hybrid'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['count'],1)
        fixture.body['kb_version']='synthetic-v2';fixture.build(key='version-two')
        self.assertEqual(fixture.post('publish',{'kb_version':'synthetic-v2','expected_active_version':'synthetic-v1'},key='version-two').status_code,200)
        self.assertEqual(fixture.post('rollback',{'kb_version':'synthetic-v1','expected_active_version':'synthetic-v2'}).status_code,200)
        self.assertEqual(reader.review.detail('alice',row['parse_id']),source_before)
        self.assertEqual(fixture.f.app.state.review_ledger.events('alice',row['parse_id'],1,100),events_before)
