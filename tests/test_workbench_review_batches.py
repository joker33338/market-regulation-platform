"""批量审核冻结解析身份及审核版本，临时状态中验证逐项权限复核。"""
import unittest

from tests import test_workbench_ingestion as fixtures
from qa_core.document_parsing.mineru_client import MinerUError


class WorkbenchReviewBatchTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.WorkbenchIngestionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.version=0
        self.calls=[]
        self.f.f.ledger.state=lambda *args:{'status':'unreviewed','version':self.version,'current_revision':None}
        test=self
        def apply(owner,parse_id,action,body,key,source_digest,*,operator_id):
            if body['expected_version']!=test.version:raise MinerUError('review_version_conflict',409)
            test.calls.append(operator_id);test.version+=1
            return {'write_performed':True,'event_id':'synthetic-event','version':test.version}
        self.f.f.ledger.apply=apply

    def create(self,headers=None):
        return self.f.f.client.post('/api/workbench/review-batches',json={'action':'approve','attested':True,'targets':[{
            'file_id':self.f.file_id,'parse_id':'synthetic-parse','expected_review_version':0,
            'expected_sha256':self.f.f.row['document_id']}]},
            headers={**(headers or self.f.f.f.auth),'Idempotency-Key':'review-batch'})

    def test_bulk_approval_uses_actual_principal_and_is_idempotent(self):
        response=self.create();self.assertEqual(response.status_code,202,response.text)
        batch=response.json()
        self.f.f.f.app.state.review_batches.tick()
        self.assertEqual(self.calls,['synthetic-admin'])
        repeat=self.create();self.assertEqual(repeat.json()['batch_id'],batch['batch_id'])
        self.f.f.f.app.state.review_batches.tick()
        self.assertEqual(len(self.calls),1)

    def test_normal_user_cannot_create_review_batch(self):
        response=self.create(self.f.f.f.other)
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.calls,[])

    def test_later_version_change_does_not_approve_unseen_content(self):
        response=self.create();self.assertEqual(response.status_code,202,response.text)
        self.version=2
        self.f.f.f.app.state.review_batches.tick()
        result=self.f.f.client.get('/api/workbench/review-batches/'+response.json()['batch_id'],headers=self.f.f.f.auth)
        self.assertEqual(result.json()['counts'].get('failed'),1)
        self.assertEqual(self.calls,[])
