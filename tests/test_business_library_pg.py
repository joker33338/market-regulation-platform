"""真实隔离 PostgreSQL 的增量结构与只读 API 验证，不接收正式库名。"""
import json
import os
from pathlib import Path
import unittest

import psycopg2
from psycopg2.extras import Json
from qa_core.api.business_library import LibraryStore
from qa_core.api.principals import Principal
from qa_core.storage.database import Database
from tests import test_frontend_api as fixtures


@unittest.skipUnless(os.getenv('LIBRARY_ISOLATED_PG')=='1','必须提供专用隔离PG')
class BusinessLibraryPGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ['LIBRARY_TEST_DSN']
        cls.sql=Path('scripts/sql')
        with psycopg2.connect(cls.dsn) as c:
            with c.cursor() as q:
                q.execute('SELECT current_database(),to_regclass(\'public.mr_active\')')
                if q.fetchone()!=('qa_round01',None):
                    raise RuntimeError('测试只允许空qa_round01库')
                q.execute(Path('tests/fixtures/round01_document_review.sql').read_text())
        db=Database(pg_dsn=cls.dsn)
        db.initialize();db.close()
        with psycopg2.connect(cls.dsn) as c:
            with c.cursor() as q:
                q.execute((cls.sql/'20261113_business_library_up.sql').read_text())
                for id,kind,owner in [('l1','law','alice'),('l2','law','alice'),('c1','case','alice'),('c2','case','bob')]:
                    q.execute('''INSERT INTO document_review.documents VALUES(%s,%s,%s,'synthetic','pdf','success',false,%s,'{}','第一条 synthetic facts','', '{}',now())''',
                              (id,id,id,Json(dict(owner_id=owner,source_file_id=id))))
                    q.execute("INSERT INTO public.mr_document_versions VALUES(%s,%s,%s,%s,%s,0)",(id,'law' if kind=='law' else id,id,'synthetic',json.dumps({'document_type':kind})))
                    q.execute('''INSERT INTO business_library.records(doc_version_id,kind,owner_id,parse_id,source_file_id,title,facts_source)
                        VALUES(%s,%s,%s,%s,%s,%s,'synthetic_source')''',(id,kind,owner,id,id,'Synthetic '+id))
                q.execute("INSERT INTO public.mr_kb_versions VALUES('v1',NULL,'ACTIVE','p','m',1024,'now','{}'),('v2','v1','ARCHIVED','p','m',1024,'now','{}'),('draft',NULL,'STAGED','p','m',1024,'now','{}')")
                q.execute("INSERT INTO public.mr_kb_documents VALUES('v1','law','l1','private'),('v1','c1','c1','private'),('v1','c2','c2','private'),('v2','law','l2','private'),('draft','law','l2','private')")
                q.execute("INSERT INTO public.mr_active VALUES(1,'v1')")
                q.execute("INSERT INTO public.mr_release_history VALUES('e1',NULL,'v1','publish','now'),('e2',NULL,'v2','publish','now')")
                q.execute("INSERT INTO business_library.chapters VALUES('ch','l1','law','第一章','synthetic',0)")
                q.execute("INSERT INTO business_library.articles VALUES('ar','l1','law','ch','第一条',NULL,0,0,10,1,1,'synthetic')")
                q.execute("INSERT INTO business_library.case_profiles(doc_version_id,violation,facts,penalty_amount,penalty_result) VALUES('c1','synthetic violation','synthetic facts',12.34,'synthetic decision')")
                q.execute("INSERT INTO business_library.case_law_references(reference_id,case_version_id,law_version_id,article_id,citation,source,method) VALUES('ref','c1','l1','ar','第一条','synthetic','extracted')")
                q.execute("INSERT INTO public.mr_chunks VALUES('chunk','l1','synthetic','第一章','第一条',0,'synthetic content','synthetic','hash','{}',%s)",('['+','.join(['0']*1024)+']',))
                q.execute("INSERT INTO business_library.article_chunks VALUES('ar','l1','chunk')")
                q.execute("CREATE ROLE library_reader LOGIN; GRANT USAGE ON SCHEMA public,document_review,business_library TO library_reader; GRANT SELECT ON ALL TABLES IN SCHEMA public,document_review,business_library TO library_reader")
        cls.read=cls.dsn.replace('user=postgres','user=library_reader')

    def setUp(self):
        self.store=LibraryStore(self.read)
        self.user=Principal('alice','alice',frozenset(['USER']),(),'active')
        self.admin=Principal('admin',None,frozenset(['ADMIN']),(),'active')

    def query(self,sql,args=()):
        with psycopg2.connect(self.dsn) as c:
            with c.cursor() as q:
                q.execute(sql,args)
                return q.fetchall() if q.description else []

    def reject(self,sql,args=()):
        with self.assertRaises(psycopg2.IntegrityError):
            self.query(sql,args)

    def test_law_fields_and_query(self):
        row=self.store.listing(self.user,'law',1,20,query='l1')['list'][0]
        self.assertEqual(row['doc_version_id'],'l1');self.assertIsNone(row['effective_status'])

    def test_multiple_versions(self):
        self.assertEqual(self.store.listing(self.user,'law',1,20,version='v2')['list'][0]['doc_version_id'],'l2')

    def test_chapter_article_order(self):
        self.assertEqual(self.store.detail(self.user,'law','l1',part='chapters')['list'][0]['chapter_id'],'ch')
        self.assertEqual(self.store.detail(self.user,'law','l1',part='articles')['list'][0]['number'],'第一条')

    def test_chunk_foreign_key(self):
        self.assertEqual(self.store.detail(self.user,'law','l1',article='ar')['structured']['chunk_ids'],['chunk'])
        self.reject("INSERT INTO business_library.article_chunks VALUES('ar','l1','missing')")
        self.reject("INSERT INTO business_library.article_chunks VALUES('ar','l2','chunk')")

    def test_source_link_and_offsets(self):
        row=self.store.detail(self.user,'law','l1',article='ar')
        self.assertEqual(row['original_text'],'第一条 synthe');self.assertEqual(row['source_url'],'/api/parse/files/l1/source')
        self.reject("UPDATE business_library.records SET owner_id='bob' WHERE doc_version_id='l1'")

    def test_case_basic_and_numeric(self):
        row=self.store.detail(self.user,'case','c1')
        self.assertEqual(row['structured']['penalty_amount'],'12.34')

    def test_original_vs_structured(self):
        row=self.store.detail(self.user,'case','c1')
        from qa_core.api.business_library import LibraryDetail
        self.assertEqual(LibraryDetail(**row).text_status,'ocr_not_manually_verified')
        self.assertEqual(row['record']['verification_status'],'pending')
        self.assertNotEqual(row['original_text'],row['structured']['facts'])

    def test_case_law_reference_pending(self):
        row=self.store.detail(self.user,'case','c1',part='references')['list'][0]
        self.assertEqual(row['verification_status'],'pending')
        self.assertEqual(row['article_id'],'ar')

    def test_document_type_isolation(self):
        from qa_core.document_parsing.mineru_client import MinerUError
        with self.assertRaises(MinerUError):self.store.detail(self.user,'case','l1')
        self.reject("INSERT INTO business_library.case_profiles(doc_version_id) VALUES('l1')")

    def test_legacy_data_unchanged(self):
        self.assertEqual(self.query('SELECT count(*) FROM document_review.documents')[0][0],4)
        self.assertEqual(self.query('SELECT count(*) FROM public.law_chunks')[0][0],0)

    def test_foreign_keys(self):
        self.reject("UPDATE business_library.case_law_references SET law_version_id='l2' WHERE reference_id='ref'")

    def test_unique_article_number(self):
        self.reject("INSERT INTO business_library.articles VALUES('ar2','l1','law','ch','第一条',NULL,1,0,3,1,1,'synthetic')")

    def test_indexes(self):
        self.assertGreaterEqual(self.query("SELECT count(*) FROM pg_indexes WHERE schemaname='business_library'")[0][0],15)

    def test_pagination_search_scope(self):
        self.assertEqual(self.store.listing(self.admin,'case',1,1)['total'],2)
        self.assertEqual(self.store.listing(self.user,'case',1,20,violation='violation')['total'],1)
        self.assertEqual(self.store.listing(self.user,'case',1,20)['total'],1)

    def test_active_and_unpublished(self):
        from qa_core.document_parsing.mineru_client import MinerUError
        with self.assertRaises(MinerUError):self.store.listing(self.user,'law',1,20,version='draft')
        self.query('DELETE FROM public.mr_active')
        try:self.assertEqual(self.store.listing(self.user,'law',1,20)['status'],'unpublished')
        finally:self.query("INSERT INTO public.mr_active VALUES(1,'v1')")

    def test_rollback_guard_and_empty_roundtrip(self):
        with self.assertRaises(psycopg2.Error):self.query((self.sql/'20261113_business_library_down.sql').read_text())
        self.assertEqual(self.query('SELECT count(*) FROM business_library.records')[0][0],4)
        # 事务内的 DDL 回退不提交，真实验证空库 down/up，同时保留其他测试夹具。
        c=psycopg2.connect(self.dsn)
        try:
            with c.cursor() as q:
                q.execute('DELETE FROM business_library.case_law_references; DELETE FROM business_library.case_profiles; DELETE FROM business_library.article_chunks; DELETE FROM business_library.articles; DELETE FROM business_library.chapters; DELETE FROM business_library.records')
                down=(self.sql/'20261113_business_library_down.sql').read_text().replace('BEGIN;','').replace('COMMIT;','')
                up=(self.sql/'20261113_business_library_up.sql').read_text().replace('BEGIN;','').replace('COMMIT;','')
                q.execute(down);q.execute(up)
        finally:c.rollback();c.close()

    def test_http_contract_auth_and_readonly(self):
        f=fixtures.FrontendAPITests();f.setUp()
        try:
            f.reader.kb_dsn=self.read
            self.assertEqual(f.client.get('/api/library/laws').status_code,401)
            r=f.client.get('/api/library/laws',headers=f.auth)
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()['total'],1)
            self.assertEqual(f.client.get('/api/library/cases/c2',headers=f.auth).status_code,404)
            self.assertEqual(f.client.get('/api/library/laws?page_size=0',headers=f.auth).status_code,422)
            self.assertEqual(f.client.get('/api/library/laws?kb_version=v1',headers=f.auth).status_code,403)
            schema=f.client.get('/api/openapi.json',headers=f.auth).json()
            self.assertEqual(schema['info']['x-contract-version'],'frontend-api-v0.2.3')
            self.assertEqual(f.client.get('/api/system/capabilities',headers=f.auth).json()['contract_version'],schema['info']['x-contract-version'])
            self.assertIn('/api/library/laws/{doc_version_id}/articles',schema['paths'])
        finally:f.doCleanups()

    def test_invalid_body_range_and_manual_claim(self):
        self.reject("UPDATE business_library.articles SET raw_end=9999 WHERE article_id='ar'")
        self.reject("UPDATE business_library.records SET verification_status='verified' WHERE doc_version_id='l1'")

    def test_read_role_cannot_write(self):
        with self.assertRaises(psycopg2.errors.InsufficientPrivilege):
            with psycopg2.connect(self.read) as c:
                with c.cursor() as q:q.execute("UPDATE business_library.records SET title='changed'")

    def test_existing_pg_search(self):
        from qa_core.retrieval.store import keyword_search
        db=Database(pg_dsn=self.read)
        try:
            rows=keyword_search(db,'synthetic',top_k=5,kb_version='v1')
            self.assertEqual(rows[0]['chunk_id'],'chunk')
        finally:db.close()

    def test_offline_import_pending_and_idempotent(self):
        from qa_core.storage.parsing_results import PostgresResultSink
        from qa_core.document_parsing.schemas import DocumentResult,PageResult
        sink=PostgresResultSink(self.dsn)
        result=DocumentResult('synthetic-import-hash','synthetic.pdf','.pdf',{},
                              pages=[PageResult(1,'native_pdf','第一章 总则\n第一条 synthetic import')])
        parse_id=None
        version=None
        try:
            parse_id=sink.save_import('admin-import','synthetic-import','a'*32,result)
            self.assertEqual(sink.save_import('admin-import','synthetic-import','a'*32,result),parse_id)
            row=self.query('SELECT requires_review,source_location,quality,raw_text FROM document_review.documents WHERE parse_id=%s',(parse_id,))[0]
            self.assertTrue(row[0]);self.assertNotIn('local_task_id',row[1])
            self.assertEqual(row[1]['owner_id'],'admin-import')
            self.assertFalse(row[2]['human_verified'])
            self.assertEqual(row[3],'第一章 总则\n第一条 synthetic import')
            self.assertFalse(result.requires_review)
            from qa_core.storage.law_intake import receive_law
            self.query("UPDATE document_review.documents SET quality=quality||'{\"document_type\":\"law\"}'::jsonb WHERE parse_id=%s",(parse_id,))
            received=receive_law(self.dsn,'admin-import',parse_id)
            version=received['doc_version_id']
            self.assertFalse(received['published'])
            self.assertEqual(received['status'],'INTAKE_NOT_INDEXED')
            self.assertEqual(received['articles'],1)
            self.assertFalse(receive_law(self.dsn,'admin-import',parse_id)['created'])
            self.assertEqual(self.query('SELECT count(*) FROM public.mr_kb_documents WHERE doc_version_id=%s',(version,))[0][0],0)
        finally:
            if version:
                self.query('DELETE FROM business_library.articles WHERE doc_version_id=%s',(version,))
                self.query('DELETE FROM business_library.chapters WHERE doc_version_id=%s',(version,))
                self.query('DELETE FROM business_library.records WHERE doc_version_id=%s',(version,))
                self.query('DELETE FROM public.mr_document_versions WHERE doc_version_id=%s',(version,))
            if parse_id:
                self.query('DELETE FROM document_review.pages WHERE parse_id=%s',(parse_id,))
                self.query('DELETE FROM document_review.documents WHERE parse_id=%s',(parse_id,))

    def test_intake_article_ranges(self):
        from qa_core.storage.law_intake import structure_ranges
        text='第一章 总则\n第一条 真实正文。\n第二条 其他正文。\n'
        chapters,articles=structure_ranges(text)
        self.assertEqual(len(chapters),1);self.assertEqual(len(articles),2)
        self.assertEqual(text[articles[0]['raw_start']:articles[0]['raw_end']],'第一条 真实正文。\n')
        self.assertEqual(structure_ranges('第一条 文本\n第一条 重复'),([],[]))
