"""仅对显式独立PG容器的真实引用查询取证，不使用正式连接。"""
import os
from pathlib import Path
import unittest

import psycopg2
from psycopg2.extras import Json

from qa_core.api.read_store import ReviewReader
from qa_core.storage.database import Database
from tests import test_frontend_api as fixtures


@unittest.skipUnless(os.getenv('DELETE_PG_FIXTURE_ISOLATED') == '1', '需要独立临时PG容器')
class DocumentDeletePGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = os.environ['DELETE_PG_TEST_ADMIN_DSN']
        cls.read = os.environ['DELETE_PG_TEST_READ_DSN']
        # 初始化只允许空的qa_round01数据库，严禁把本开关指向既有业务库。
        with psycopg2.connect(cls.admin) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_database()')
                if cursor.fetchone()[0] != 'qa_round01':
                    raise RuntimeError('隔离库身份错误')
                cursor.execute("SELECT to_regnamespace('document_review'),to_regclass('public.mr_active')")
                if any(cursor.fetchone()):
                    raise RuntimeError('隔离夹具要求空库，拒绝覆盖')
                cursor.execute((Path(__file__).parent/'fixtures'/'round01_document_review.sql').read_text(encoding='utf-8'))
        database=Database(pg_dsn=cls.admin)
        try:
            database.initialize()
        finally:
            database.close()
        with psycopg2.connect(cls.admin) as connection:
            with connection.cursor() as cursor:
                cursor.execute('CREATE ROLE delete_evidence_reader LOGIN')
                cursor.execute('GRANT USAGE ON SCHEMA public,document_review TO delete_evidence_reader')
                cursor.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public,document_review TO delete_evidence_reader')

    def setUp(self):
        from uuid import uuid4
        self.fixture=fixtures.FrontendAPITests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.data=b'%PDF-1.7 synthetic '+uuid4().hex.encode()
        self.client=self.fixture.client;self.reader=self.fixture.reader
        self.fixture.app.state.auth_registry.replace({'a'*32:dict(principal_id='synthetic-admin',
            owner_id='alice',roles=['ADMIN'],review_owner_scopes=[],credential_status='active',
            document_delete_owner_scopes=['alice'])})
        self.reader.review=ReviewReader(self.read)
        self.reader.kb_dsn=self.read
        response=self.client.post('/api/parse/files?file_name=synthetic.pdf',
            headers=self.fixture.auth,content=self.fixture.data)
        self.assertEqual(response.status_code,201)
        self.fid=response.json()['file_id'];self.sha=response.json()['sha256']

    def snapshot(self):
        with psycopg2.connect(self.admin) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('public','document_review') ORDER BY 1,2")
                tables=cursor.fetchall();result={}
                for schema,table in tables:
                    from psycopg2 import sql
                    cursor.execute(sql.SQL('SELECT row_to_json(t)::text FROM {}.{} t ORDER BY row_to_json(t)::text').format(sql.Identifier(schema),sql.Identifier(table)))
                    result[schema+'.'+table]=cursor.fetchall()
                return result

    def attempt(self,status):
        before=self.snapshot()
        response=self.client.delete('/api/documents/'+self.fid,headers=self.fixture.auth)
        self.assertEqual(response.status_code,status,response.text)
        self.assertEqual(self.snapshot(),before)
        _,source=(None,None) if status==200 else self.reader.upload('alice',self.fid)
        if source:
            self.assertEqual(source.read_bytes(),self.fixture.data)
        return response

    def add_document(self,by_hash):
        from uuid import uuid4
        with psycopg2.connect(self.admin) as connection:
            with connection.cursor() as cursor:
                cursor.execute('''INSERT INTO document_review.documents VALUES
                    (%s,%s,%s,'synthetic.pdf','pdf','needs_review',true,%s,'{}','synthetic','synthetic','{}',now())''',
                    (uuid4().hex,self.sha if by_hash else uuid4().hex,uuid4().hex,
                     Json({'owner_id':'alice','source_file_id':uuid4().hex if by_hash else self.fid})))

    def test_pg_upload_id_reference(self):
        self.add_document(False)
        self.assertEqual(self.attempt(409).json()['error']['code'],'document_referenced')

    def test_pg_document_hash_reference(self):
        self.add_document(True)
        self.assertEqual(self.attempt(409).json()['error']['code'],'document_referenced')

    def test_non_active_knowledge_reference(self):
        from uuid import uuid4
        unique=uuid4().hex
        with psycopg2.connect(self.admin) as connection:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO mr_kb_versions VALUES (%s,NULL,'RETIRED','synthetic','synthetic',1024,'synthetic','{}')",(unique,))
                cursor.execute("INSERT INTO mr_document_versions VALUES (%s,%s,%s,'synthetic','{}',0)",(unique,unique,self.sha))
                cursor.execute('INSERT INTO mr_kb_documents VALUES (%s,%s,%s,%s)',(unique,unique,unique,'synthetic'))
                cursor.execute('SELECT count(*) FROM mr_active')
                self.assertEqual(cursor.fetchone()[0],0)
        self.assertEqual(self.attempt(409).json()['error']['code'],'document_referenced')

    def test_no_reference_success(self):
        self.assertTrue(self.attempt(200).json()['deleted'])

    def test_pg_unavailable_fails_closed(self):
        self.reader.review=ReviewReader('host=127.0.0.1 port=1 dbname=qa_round01 user=delete_evidence_reader connect_timeout=1')
        self.attempt(503)

    def test_kb_unavailable_fails_closed(self):
        self.reader.kb_dsn='host=127.0.0.1 port=1 dbname=qa_round01 user=delete_evidence_reader connect_timeout=1'
        self.attempt(503)
