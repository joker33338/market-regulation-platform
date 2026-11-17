"""知识检索按owner和资料类别隔离，案例不能默认作为法规依据。"""
import unittest
from tests import test_ingestion_api as fixtures


class WorkbenchSearchScopeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.IngestionAPITests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def publish(self):
        self.f.build()
        result=self.f.post('publish',{'kb_version':'synthetic-v1','expected_active_version':None})
        self.assertEqual(result.status_code,200,result.text)

    def search(self,auth=None,**fields):
        return self.f.client.post('/api/knowledge/search',json={'query':'合成条文','mode':'keyword',**fields},
                                  headers=auth or self.f.f.auth)

    def test_user_cannot_search_another_owners_published_text(self):
        self.publish()
        result=self.search(self.f.f.other)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['count'],0)

    def test_case_and_law_have_explicit_separate_search_scopes(self):
        self.f.body['documents'][0]['document_type']='case'
        self.publish()
        self.assertEqual(self.search().json()['count'],0)
        result=self.search(document_type='case')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['count'],1)
        self.assertEqual(result.json()['list'][0]['source']['document_type'],'case')

    def test_user_can_search_their_explicitly_owned_published_text(self):
        self.publish()
        self.f.f.app.state.auth_registry.replace({'a'*32:dict(principal_id='alice-user',owner_id='alice',roles=['USER'],review_owner_scopes=[],credential_status='active')})
        response=self.search()
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['count'],1)
