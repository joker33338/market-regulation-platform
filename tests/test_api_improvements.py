"""优化接口的合成数据契约与权限测试。"""
from datetime import datetime
import unittest
from unittest.mock import patch
from qa_core.api.document_query import select_documents
from tests import test_frontend_api as fixtures


class APIImprovementTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.FrontendAPITests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.client, self.auth = self.fixture.client, self.fixture.auth

    def test_document_window_validation_sorting_and_owner(self):
        rows = [dict(file_id='b', uploaded_at='2026-01-01T00:00:00+00:00', file_name='b', size_bytes=2, status='uploaded'),
                dict(file_id='a', uploaded_at='2026-01-02T00:00:00+00:00', file_name='a', size_bytes=1, status='uploaded')]
        for row in rows:
            row.update(doc_type='pdf',sha256='a'*64,uploaded_at_source='metadata_mtime',latest_task_id=None,parse_count=0)
        with patch.object(self.fixture.reader, 'documents', return_value=rows) as read:
            response = self.client.get('/api/documents', headers=self.auth, params={'sort_by':'size_bytes','order':'asc'})
            self.assertEqual([row['file_id'] for row in response.json()['list']], ['a','b'])
            self.assertEqual(read.call_args.args, ('alice',))
            for params in ({'date_from':'2026-01-01'}, {'sort_by':'path'}, {'order':'random'},
                           {'date_from':'2026-01-02T00:00:00Z','date_to':'2026-01-01T00:00:00Z'}):
                self.assertEqual(self.client.get('/api/documents',headers=self.auth,params=params).status_code,422)

    def test_date_comparison_uses_instants_and_closed_bounds(self):
        rows=[dict(file_id='a',uploaded_at='2026-01-01T08:00:00+08:00',file_name='a')]
        point=datetime.fromisoformat('2026-01-01T00:00:00+00:00')
        self.assertEqual(select_documents(rows,point,point,'uploaded_at','desc'),rows)

    def test_resources_auth_and_no_fake_zero_on_failure(self):
        path='/api/system/resources'
        self.assertEqual(self.client.get(path).status_code,401)
        with patch('psutil.Process',side_effect=RuntimeError('secret/internal/path')):
            result=self.client.get(path,headers=self.auth).json()
        self.assertFalse(result['available'])
        self.assertIsNone(result['memory_rss_bytes'])
        self.assertNotIn('secret',str(result))
        response=self.client.get(path,headers=self.auth)
        self.assertTrue(response.json()['available'])
        self.assertGreater(response.json()['memory_rss_bytes'],0)
        self.assertEqual(response.json()['scope'],'api_process')

    def test_database_unavailability_and_version_semantics(self):
        body=self.client.get('/api/stats/overview',headers=self.auth).json()['parsed_documents']
        self.assertFalse(body['available'])
        self.assertIsNone(body['total'])
        self.assertEqual(body['reason'],'review_store_not_configured')
        schema=self.client.get('/api/openapi.json',headers=self.auth).json()
        self.assertEqual(schema['info']['version'],'0.2.3')
        self.assertIn('x-contract-version',schema['info'])
        self.assertIn('/api/system/resources',schema['paths'])
