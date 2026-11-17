"""独立PG、既有隔离MySQL验证工作台闭环；向量为明确标注的测试向量。"""
import hashlib
import json
import os
from pathlib import Path
import unittest
from uuid import uuid4

import psycopg2
from qa_core.api.read_store import ReviewReader
from qa_core.document_parsing.schemas import DocumentResult,PageResult,LayoutBlock
from qa_core.storage.database import Database
from qa_core.storage.parsing_results import PostgresResultSink
from qa_core.storage.mysql_review_ledger import MySQLReviewLedger
from tests import test_frontend_workflow_pg as baseline
from tests import test_ingestion_api as fixtures


@unittest.skipUnless(os.getenv('FRONTEND_WORKFLOW_TEST_PG_ADMIN_DSN') and os.getenv('REVIEW_MYSQL_TEST_CONFIG'),
                     '需要明确的专用PG和隔离MySQL')
class WorkbenchRealPGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        baseline.FrontendWorkflowPGTests.setUpClass.__func__(cls)
        with psycopg2.connect(cls.admin) as connection,connection.cursor() as cursor:
            cursor.execute(Path('scripts/sql/20261116_reviewed_article_range_up.sql').read_text(encoding='utf-8'))

    def fixture(self,text):
        f=fixtures.IngestionAPITests();f.setUp();self.addCleanup(f.doCleanups)
        nonce=uuid4().hex
        response=f.client.post('/api/parse/files?file_name=synthetic-'+nonce+'.pdf',
            headers=f.f.auth,content=f.f.data+nonce.encode())
        self.assertEqual(response.status_code,201,response.text)
        upload=response.json()
        result=DocumentResult(upload['sha256'],'synthetic-'+nonce+'.pdf','pdf',{},pages=[
            PageResult(1,'synthetic',raw_text=text,layout_blocks=[LayoutBlock('body','text',text)])])
        parse_id=PostgresResultSink(self.admin).save_import('alice','synthetic-'+nonce,upload['file_id'],result)
        reader=f.f.reader
        reader.review=ReviewReader(self.runtime)
        reader.kb_dsn=self.runtime
        reader.kb_factory=lambda:Database(pg_dsn=self.runtime)
        reader.kb_write_factory=reader.kb_factory
        class TestVectors:
            dimension=1024
            signature='synthetic-test-vectors-1024'
            def embed_documents(self,texts):return [[1.0]+[0.0]*1023 for _ in texts]
        reader.embeddings_factory=TestVectors
        f.f.app.state.review_ledger=MySQLReviewLedger(self.mysql)
        return f,upload,parse_id

    def post(self,f,path,body,key=None):
        return f.client.post(path,json=body,headers={**f.f.auth,'Idempotency-Key':key or uuid4().hex})

    def approve(self,f,parse_id,version=0):
        response=self.post(f,'/api/review/'+parse_id+'/approve',{'base_result_id':parse_id,'expected_version':version})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['operator_id'],'synthetic-admin')
        return response.json()

    def prepare(self,f,upload,parse_id,title,kind='law',scope=None):
        response=self.post(f,'/api/workbench/documents/'+upload['file_id']+'/prepare',
            {'title':title,'document_type':kind,'source_parse_id':parse_id,'expected_sha256':upload['sha256'],
             'source_range':scope,'whole_file_confirmed':scope is None})
        self.assertEqual(response.status_code,202,response.text)
        f.f.app.state.workbench_ingestion.tick()
        job=f.client.get('/api/workbench/jobs/'+response.json()['job_id'],headers=f.f.auth)
        self.assertEqual(job.json()['status'],'awaiting_publish',job.text)
        return job.json()

    def release(self,f,jobs):
        response=self.post(f,'/api/workbench/releases',{'job_ids':[job['job_id'] for job in jobs]})
        self.assertEqual(response.status_code,201,response.text)
        id=response.json()['release_id']
        response=self.post(f,'/api/workbench/releases/'+id+'/prepare',{})
        self.assertEqual(response.status_code,200,response.text)
        manifest=response.json()
        response=self.post(f,'/api/workbench/releases/'+id+'/publish',
                           {'expected_active_version':manifest['expected_active_version']})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_case_projection_and_owner_scoped_search_use_real_databases(self):
        nonce=uuid4().hex[:10]
        text='行政处罚决定书\n当事人：合成主体。\n违法事实\n存在合成违法行为。\n处罚决定\n给予警告'+nonce+'。'
        f,upload,parse_id=self.fixture(text)
        original=f.f.reader.review.detail('alice',parse_id)
        self.approve(f,parse_id)
        job=self.prepare(f,upload,parse_id,'合成案例'+nonce,'case')
        manifest=self.release(f,[job])
        listing=f.client.get('/api/library/cases',params={'query':nonce},headers=f.f.auth)
        self.assertEqual(listing.status_code,200,listing.text)
        self.assertEqual(listing.json()['total'],1)
        record=listing.json()['list'][0]
        detail=f.client.get('/api/library/cases/'+record['doc_version_id'],headers=f.f.auth)
        self.assertEqual(detail.status_code,200,detail.text)
        self.assertIsNone(detail.json()['structured']['penalty_amount'])
        response=f.client.post('/api/knowledge/search',headers=f.f.auth,
            json={'query':nonce,'mode':'keyword','document_type':'case'})
        self.assertEqual(response.status_code,200,response.text);self.assertGreater(response.json()['count'],0)
        response=f.client.post('/api/knowledge/search',headers=f.f.other,
            json={'query':nonce,'mode':'keyword','document_type':'all'})
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['count'],0)
        self.assertEqual(f.f.reader.review.detail('alice',parse_id),original)
        self.assertEqual(hashlib.sha256(f.client.get('/api/parse/files/'+upload['file_id']+'/source',headers=f.f.auth).content).hexdigest(),upload['sha256'])

    def test_long_page_revision_uses_reviewed_copy_without_updating_ocr(self):
        nonce=uuid4().hex[:8]
        f,upload,parse_id=self.fixture('第一条 原正文。')
        original=f.f.reader.review.detail('alice',parse_id)
        content='第一条 新增长正文'+nonce+'。'*20+'\n第二条 补充条文。'
        response=self.post(f,'/api/review/'+parse_id+'/save-revision',
            {'base_result_id':parse_id,'expected_version':0,'page':1,'content':content,'revision_scope':'page_body_v1'})
        self.assertEqual(response.status_code,200,response.text)
        self.approve(f,parse_id,1)
        job=self.prepare(f,upload,parse_id,'合成'+nonce+'修订办法')
        self.release(f,[job])
        listing=f.client.get('/api/library/laws',params={'query':nonce},headers=f.f.auth).json()
        self.assertEqual(listing['total'],1)
        detail=f.client.get('/api/library/laws/'+listing['list'][0]['doc_version_id'],headers=f.f.auth)
        self.assertEqual(detail.status_code,200,detail.text)
        self.assertEqual(detail.json()['original_text'],content)
        self.assertEqual(detail.json()['text_status'],'reviewed_copy')
        self.assertEqual(f.f.reader.review.detail('alice',parse_id),original)
        reviewed=f.client.get('/api/review/'+parse_id+'/reviewed-text',headers=f.f.auth)
        self.assertEqual(reviewed.status_code,200,reviewed.text)
        self.assertEqual(reviewed.json()['pages'][0]['text'],content)

    def test_same_page_compilation_keeps_two_entries_and_combined_release(self):
        nonce=uuid4().hex[:8]
        first='合成'+nonce+'甲管理办法'
        second='合成'+nonce+'乙管理条例'
        f,upload,parse_id=self.fixture(first+'\n第一条 甲正文。\n'+second+'\n第一条 乙正文。')
        self.approve(f,parse_id)
        suggestions=f.client.get('/api/workbench/documents/'+upload['file_id']+'/suggestions',headers=f.f.auth)
        self.assertEqual(suggestions.status_code,200,suggestions.text)
        parts=suggestions.json()['segments'];self.assertEqual(len(parts),2)
        jobs=[]
        for part in parts:
            scope={key:part[key] for key in ('start','end','expected_text_sha256')}
            jobs.append(self.prepare(f,upload,parse_id,part['title'],scope=scope))
        self.assertEqual(len(f.client.get('/api/workbench/jobs',headers=f.f.auth).json()['list']),2)
        self.release(f,jobs)
        listing=f.client.get('/api/library/laws',params={'query':nonce},headers=f.f.auth)
        self.assertEqual(listing.status_code,200,listing.text);self.assertEqual(listing.json()['total'],2)
        for record in listing.json()['list']:
            detail=f.client.get('/api/library/laws/'+record['doc_version_id'],headers=f.f.auth).json()
            self.assertIn(record['title'],detail['original_text'])
            other=second if record['title']==first else first
            self.assertNotIn(other,detail['original_text'])
        files=f.client.get('/api/workbench/documents',params={'keyword':nonce},headers=f.f.auth)
        self.assertEqual(files.status_code,200,files.text)
        row=next(row for row in files.json()['list'] if row['file_id']==upload['file_id'])
        self.assertEqual(row['stage'],'published');self.assertEqual(row['child_document_count'],2)
        self.assertEqual(row['published_document_count'],2)

    def test_newer_offline_parse_rejects_old_review_and_candidate(self):
        f,upload,parse_id=self.fixture('第一条 原始合成正文。')
        self.approve(f,parse_id)
        response=self.post(f,'/api/workbench/documents/'+upload['file_id']+'/prepare',
            {'title':'合成来源变更检查','document_type':'law','source_parse_id':parse_id,
             'expected_sha256':upload['sha256'],'whole_file_confirmed':True})
        self.assertEqual(response.status_code,202,response.text)
        result=DocumentResult(upload['sha256'],'synthetic-new.pdf','pdf',{},pages=[
            PageResult(1,'synthetic',raw_text='第一条 更新后的合成正文。',layout_blocks=[LayoutBlock('body','text','第一条 更新后的合成正文。')])])
        newer=PostgresResultSink(self.admin).save_import('alice','newer-'+uuid4().hex,upload['file_id'],result)
        self.assertNotEqual(newer,parse_id)
        old_review=self.post(f,'/api/review/'+parse_id+'/approve',{'base_result_id':parse_id,'expected_version':1})
        self.assertEqual(old_review.status_code,409,old_review.text)
        f.f.app.state.workbench_ingestion.tick()
        job=f.client.get('/api/workbench/jobs/'+response.json()['job_id'],headers=f.f.auth).json()
        self.assertEqual(job['status'],'needs_attention');self.assertEqual(job['error_code'],'review_source_changed')
