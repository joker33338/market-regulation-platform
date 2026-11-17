"""多份候选合并为一次明确发布，临时SQLite与合成审核台账。"""
from contextlib import contextmanager
from copy import deepcopy
import unittest

from tests import test_workbench_ingestion as fixtures
from qa_core.api.ingestion import source_fingerprint
from qa_core.document_parsing.mineru_client import MinerUError


class WorkbenchReleaseTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.WorkbenchIngestionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        first=deepcopy(self.f.f.row)
        client=self.f.f.client;auth=self.f.f.f.auth
        upload=client.post('/api/parse/files?file_name=second.pdf',content=self.f.f.f.data+b' second',headers=auth).json()
        second=deepcopy(first);second.update(parse_id='second-parse',document_id=upload['sha256'])
        second['source_location']['source_file_id']=upload['file_id']
        second['original_result']['document_id']=upload['sha256']
        self.rows={first['parse_id']:first,second['parse_id']:second}
        test=self
        class Review:
            def latest_parse_id(self,owner,file_id):
                return next((row['parse_id'] for row in test.rows.values() if row['source_location']['owner_id']==owner and row['source_location']['source_file_id']==file_id),None)
            def detail(self,owners,parse_id):
                if parse_id not in test.rows:raise MinerUError('document_not_found',404)
                return test.rows[parse_id]
        self.f.f.f.reader.review=Review()
        def verify(owner,parse_id,source_digest,version):
            if version!=1 or source_digest!=source_fingerprint(self.rows[parse_id]):raise MinerUError('review_approval_required',409)
            return {'status':'approved','version':1,'current_revision':None}
        self.f.f.ledger.verify_for_ingestion=verify
        self.jobs=[]
        for index,row in enumerate((first,second)):
            response=client.post(f"/api/workbench/documents/{row['source_location']['source_file_id']}/prepare",
                json={'title':f'合成法规{index}','document_type':'law','expected_sha256':row['document_id'],'source_parse_id':row['parse_id']},
                headers={**auth,'Idempotency-Key':f'prepare-{index}'})
            self.assertEqual(response.status_code,202,response.text)
            self.jobs.append(response.json())
            self.f.f.f.app.state.workbench_ingestion.tick()

    def post(self,path,body,key):
        return self.f.f.client.post(path,json=body,headers={**self.f.f.f.auth,'Idempotency-Key':key})

    def prepare_release(self):
        response=self.post('/api/workbench/releases',{'job_ids':[j['job_id'] for j in self.jobs]},'release')
        self.assertEqual(response.status_code,201,response.text)
        draft=response.json()
        response=self.post(f"/api/workbench/releases/{draft['release_id']}/prepare",{},'prepare-release')
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_selected_documents_are_in_one_candidate_and_publish_once(self):
        release=self.prepare_release()
        self.assertEqual(len(release['documents']),2)
        self.assertEqual(release['status'],'STAGED')
        self.assertIsNone(self.f.f.active())
        response=self.post(f"/api/workbench/releases/{release['release_id']}/publish",{'expected_active_version':None},'confirmed-release')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'published')
        database=self.f.f.f.reader.kb_factory()
        try:
            self.assertEqual(database.one('SELECT count(*) AS n FROM mr_kb_documents WHERE kb_version=:v',{'v':database.active_version()})['n'],2)
        finally:database.close()

    def test_active_change_does_not_silently_publish_stale_batch(self):
        release=self.prepare_release()
        first=self.jobs[0]
        response=self.post(f"/api/workbench/jobs/{first['job_id']}/publish",{'expected_active_version':None},'first')
        self.assertEqual(response.status_code,200,response.text)
        active=self.f.f.active()
        response=self.post(f"/api/workbench/releases/{release['release_id']}/publish",{'expected_active_version':None},'stale-release')
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.f.f.active(),active)
