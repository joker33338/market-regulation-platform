"""临时SQLite知识库与合成审核来源验证HTTP编排；无正式数据或真实模型调用。"""
import json
import os
from unittest.mock import patch
import unittest
from contextlib import contextmanager

from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.document_parsing.schemas import DocumentResult,PageResult,LayoutBlock
from qa_core.retrieval.models import DemoEmbeddings
from qa_core.storage.database import Database
from tests import test_frontend_api as fixtures


class IngestionAPITests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.FrontendAPITests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.client=self.f.client
        self.f.app.state.auth_registry.replace({'a'*32:dict(principal_id='synthetic-admin',owner_id='alice',
            roles=['ADMIN'],review_owner_scopes=[],credential_status='active'),
            'b'*32:dict(principal_id='synthetic-user',owner_id='bob',roles=['USER'],review_owner_scopes=[],credential_status='active')})
        upload=self.client.post('/api/parse/files?file_name=synthetic.pdf',headers=self.f.auth,content=self.f.data).json()
        original=DocumentResult(upload['sha256'],'synthetic.pdf','pdf',{},pages=[PageResult(1,'synthetic',
            raw_text='第一条 合成条文。',layout_blocks=[LayoutBlock('synthetic','text','第一条 合成条文。')])]).to_dict()
        self.row=dict(parse_id='synthetic-parse',document_id=upload['sha256'],file_name='synthetic.pdf',
            source_location={'owner_id':'alice','source_file_id':upload['file_id']},original_result=original,
            raw_text='第一条 合成条文。',markdown_content='第一条 合成条文。')
        test=self
        class Review:
            def latest_parse_id(self,owner,file_id):
                return test.row['parse_id'] if owner=='alice' and file_id==test.row['source_location']['source_file_id'] else None
            def detail(self,owners,parse_id):
                from qa_core.access import is_all_owners
                if parse_id!=test.row['parse_id'] or not is_all_owners(owners) and 'alice' not in ([owners] if isinstance(owners,str) else owners):
                    raise MinerUError('document_not_found',404)
                return test.row
        class Ledger:
            approved=True
            revision=None
            def health(self):
                pass
            def verify_for_ingestion(self,owner,parse_id,source_digest,expected_version):
                from qa_core.api.ingestion import source_fingerprint
                if not self.approved or expected_version!=1 or source_digest!=source_fingerprint(test.row):
                    raise MinerUError('review_approval_required',409)
                return {'version':1,'status':'approved','current_revision':self.revision}
            def events(self,*args):
                return {'list':[{'version':1,'action':'approve','operator_id':'synthetic-reviewer'}]}
            @contextmanager
            def verified_ingestion_scope(self,references):
                for reference in references:
                    self.verify_for_ingestion(reference['owner_id'],reference['parse_id'],reference['source_digest'],reference['version'])
                yield
        self.f.reader.review=Review();self.ledger=Ledger();self.f.app.state.review_ledger=self.ledger
        self.database_path=self.f.root/'knowledge.sqlite'
        database=Database(sqlite_path=self.database_path);database.initialize();database.close()
        self.f.reader.kb_factory=lambda:Database(sqlite_path=self.database_path)
        self.f.reader.kb_write_factory=self.f.reader.kb_factory
        self.f.reader.embeddings_factory=lambda:DemoEmbeddings(8)
        self.grants=self.f.root/'test-grants.json'
        self.write_grants()
        environment=patch.dict(os.environ,{'KB_API_GRANTS_FILE':str(self.grants)})
        environment.start();self.addCleanup(environment.stop)
        self.body={'kb_version':'synthetic-v1','documents':[{'parse_id':'synthetic-parse','law_name':'合成法规',
                    'law_id':'synthetic-law','expected_review_version':1}]}

    def write_grants(self,**changes):
        entry={'owner_scopes':['alice'],'build_versions':['synthetic-v1','synthetic-v2'],
               'publish_versions':['synthetic-v1','synthetic-v2'],'rollback_versions':['synthetic-v1']}
        entry.update(changes)
        self.grants.write_text(json.dumps({'synthetic-admin':entry}),encoding='utf-8')

    def post(self,path,body,key='synthetic-key',auth=None):
        return self.client.post('/api/ingestion/'+path,json=body,
            headers={**(auth or self.f.auth),'Idempotency-Key':key})

    def active(self):
        database=Database(sqlite_path=self.database_path)
        try:
            return database.active_version()
        finally:
            database.close()

    def build(self,key='synthetic-key'):
        result=self.post('batches',self.body,key=key)
        self.assertEqual(result.status_code,201,result.text)
        return result.json()

    def test_precheck_build_release_and_rollback_reuse_existing_services(self):
        precheck=self.post('precheck',self.body)
        self.assertEqual(precheck.status_code,200,precheck.text)
        self.assertTrue(precheck.json()['eligible']);self.assertIsNone(self.active())
        operation=self.build()
        self.assertEqual(operation['status'],'STAGED');self.assertFalse(operation['publish_authorized'])
        self.assertIsNone(self.active())
        self.assertEqual(self.build()['operation_id'],operation['operation_id'])
        path='/api/ingestion/batches/'+operation['operation_id']
        self.assertEqual(self.client.get(path,headers=self.f.auth).status_code,200)
        self.assertEqual(self.client.get(path,headers=self.f.other).status_code,404)
        check=self.client.get('/api/ingestion/version-check?kb_version=synthetic-v1',headers=self.f.auth)
        self.assertTrue(check.json()['publish_eligible'])
        publish={'kb_version':'synthetic-v1','expected_active_version':None}
        result=self.post('publish',publish)
        self.assertEqual(result.status_code,200,result.text);self.assertEqual(self.active(),'synthetic-v1')
        self.assertEqual(self.post('publish',publish).json()['operation_id'],result.json()['operation_id'])
        self.body['kb_version']='synthetic-v2';self.build(key='second-build')
        self.assertEqual(self.post('publish',{'kb_version':'synthetic-v2','expected_active_version':'synthetic-v1'},key='second').status_code,200)
        self.assertEqual(self.post('rollback',{'kb_version':'synthetic-v1','expected_active_version':'synthetic-v2'}).status_code,200)
        self.assertEqual(self.active(),'synthetic-v1')

    def test_admin_all_permissions_and_role_revocation(self):
        self.assertEqual(self.post('batches',self.body,auth=self.f.other).status_code,403)
        self.write_grants(build_versions=[])
        self.build()
        self.f.app.state.auth_registry.replace({'a'*32:dict(principal_id='synthetic-admin',owner_id='alice',
            roles=['USER'],review_owner_scopes=[],credential_status='active')})
        self.assertEqual(self.post('publish',{'kb_version':'synthetic-v1','expected_active_version':None}).status_code,403)
        self.assertIsNone(self.active())

    def test_review_mismatch_and_revision_never_enter_index(self):
        self.ledger.approved=False
        precheck=self.post('precheck',self.body)
        self.assertEqual(precheck.status_code,200,precheck.text)
        self.assertFalse(precheck.json()['eligible'])
        self.assertEqual(precheck.json()['documents'][0]['error_code'],'review_approval_required')
        self.assertEqual(self.post('batches',self.body).status_code,409)
        self.ledger.approved=True;self.ledger.revision='synthetic-revision'
        self.assertEqual(self.post('batches',self.body).status_code,409)
        self.assertIsNone(self.active())

    def test_idempotency_and_optimistic_release_guard(self):
        self.build();self.body['full_snapshot']=True
        self.assertEqual(self.post('batches',self.body).status_code,409)
        bad={'kb_version':'synthetic-v1','expected_active_version':'unexpected'}
        self.assertEqual(self.post('publish',bad).status_code,409)
        self.assertIsNone(self.active())
        self.assertEqual(self.post('publish',{'kb_version':'synthetic-v1','expected_active_version':None},key='correct').status_code,200)

    def test_missing_ledger_and_inference_failure_are_not_success(self):
        self.f.app.state.review_ledger=None
        self.assertEqual(self.post('precheck',self.body).status_code,503)
        self.f.app.state.review_ledger=self.ledger
        self.f.reader.embeddings_factory=lambda:(_ for _ in ()).throw(OSError('sensitive model location'))
        response=self.post('batches',self.body)
        self.assertEqual(response.status_code,503,response.text)
        self.assertNotIn('sensitive',response.text)
        self.assertEqual(self.post('batches',self.body).status_code,409)
        self.assertIsNone(self.active())

    def test_body_cannot_supply_identity_or_paths(self):
        for key in ('owner_id','operator_id','source_path'):
            body={**self.body,key:'synthetic'}
            self.assertEqual(self.post('batches',body).status_code,422)

    def test_read_store_does_not_implicitly_enable_knowledge_writes(self):
        self.f.reader.kb_write_factory=self.f.reader._write_database
        with patch.dict(os.environ,{'KNOWLEDGE_WRITE_PG_DSN':''}):
            response=self.post('batches',self.body)
            self.assertEqual(response.status_code,503,response.text)
            self.assertEqual(response.json()['error']['code'],'knowledge_write_store_not_configured')
        self.assertEqual(self.post('precheck',self.body).status_code,200)
        self.assertIsNone(self.active())

    def test_search_filters_and_published_historical_versions(self):
        self.build()
        database=Database(sqlite_path=self.database_path)
        try:
            for row in database.all('SELECT chunk_id,metadata FROM mr_chunks'):
                metadata=json.loads(row['metadata']);metadata.update(effective_status='synthetic-effective')
                database.execute('UPDATE mr_chunks SET metadata=:m WHERE chunk_id=:id',{'m':json.dumps(metadata),'id':row['chunk_id']}).close()
            for row in database.all('SELECT doc_version_id,metadata FROM mr_document_versions'):
                metadata=json.loads(row['metadata']);metadata['issuing_authority']='synthetic authority'
                database.execute('UPDATE mr_document_versions SET metadata=:m WHERE doc_version_id=:id',{'m':json.dumps(metadata),'id':row['doc_version_id']}).close()
        finally:
            database.close()
        self.assertEqual(self.post('publish',{'kb_version':'synthetic-v1','expected_active_version':None}).status_code,200)
        def search(**filters):
            return self.client.post('/api/knowledge/search',headers=self.f.auth,json={'query':'合成条文',**filters})
        self.assertEqual(search(issuing_authority='synthetic authority').json()['count'],1)
        self.assertEqual(search(issuing_authority='missing').json()['count'],0)
        self.assertEqual(search(effective_status='synthetic-effective').json()['count'],1)
        self.assertEqual(search(issuing_authority="' OR 1=1 --").json()['count'],0)
        self.body['kb_version']='synthetic-v2';self.build(key='second-version')
        self.assertEqual(search(kb_version='synthetic-v2').status_code,409)
        self.assertEqual(self.post('publish',{'kb_version':'synthetic-v2','expected_active_version':'synthetic-v1'},key='second-version').status_code,200)
        result=search(kb_version='synthetic-v1',issuing_authority='synthetic authority')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['kb_version'],'synthetic-v1');self.assertEqual(result.json()['count'],1)
        self.assertEqual(search(mode='hybrid',kb_version='synthetic-v1').status_code,200)
