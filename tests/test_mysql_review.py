"""MySQL审核真实事务与HTTP隔离测试；只使用显式指定的随机测试库。"""
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock
from uuid import uuid4

from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.storage.mysql_review_ledger import MySQLReviewLedger
from tests import test_frontend_api as fixtures


class MySQLReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=os.getenv('REVIEW_MYSQL_TEST_CONFIG')
        if not path:
            raise unittest.SkipTest('需要显式MySQL隔离测试配置')
        cls.config=json.loads(Path(path).read_text(encoding='utf-8'))
        if not cls.config['database'].startswith('market_review_test_'):
            raise RuntimeError('拒绝使用非隔离测试库')

    def setUp(self):
        self.fixture=fixtures.FrontendAPITests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.client=self.fixture.client
        self.ledger=MySQLReviewLedger(self.config)
        self.fixture.app.state.review_ledger=self.ledger
        self.pid='synthetic-'+uuid4().hex
        self.source=dict(parse_id=self.pid,document_id='synthetic-document',file_name='synthetic.pdf',
            parsing_status='needs_review',requires_review=True,source_location={},quality={},
            raw_text='synthetic original',markdown_content='synthetic original',original_result={'pages':[{'page_number':1}]})
        def detail(owner,parse_id):
            if owner!='alice' or parse_id!=self.pid:
                raise MinerUError('document_not_found',404)
            return dict(self.source)
        self.fixture.reader.review=Mock()
        self.fixture.reader.review.detail.side_effect=detail

    def post(self,action,version=0,key=None,**fields):
        return self.client.post(f'/api/review/{self.pid}/{action}',
            headers={**self.fixture.auth,'Idempotency-Key':key or uuid4().hex},
            json=dict(base_result_id=self.pid,expected_version=version,**fields))

    def test_append_revision_approve_and_replay(self):
        key=uuid4().hex
        first=self.post('save-revision',key=key,page=1,content='synthetic revision')
        self.assertEqual(first.status_code,200,first.text)
        event=first.json()
        self.assertEqual(event['version'],1)
        self.assertIsNotNone(event['revision_id'])
        self.assertEqual(self.post('save-revision',key=key,page=1,content='synthetic revision').json(),event)
        self.assertEqual(self.post('save-revision',key=key,page=1,content='different').status_code,409)
        self.assertEqual(self.post('approve',version=0).status_code,409)
        approved=self.post('approve',version=1).json()
        self.assertEqual(approved['status'],'approved')
        self.assertFalse(approved['publish_authorized'])
        self.assertFalse(approved['original_result_modified'])
        detail=self.client.get(f'/api/review/{self.pid}',headers=self.fixture.auth).json()
        self.assertTrue(detail['review_write_supported'])
        self.assertTrue(detail['requires_review'])
        self.assertEqual(detail['raw_text'],'synthetic original')
        audit=self.client.get(f'/api/review/{self.pid}/events',headers=self.fixture.auth).json()
        self.assertEqual(audit['total'],2)
        self.assertEqual(audit['list'][1]['request']['content'],'synthetic revision')

    def test_auth_owner_write_grants_and_validation(self):
        url=f'/api/review/{self.pid}/approve'
        body=dict(base_result_id=self.pid,expected_version=0)
        self.assertEqual(self.client.post(url,json=body).status_code,401)
        self.assertEqual(self.client.post(url,json=body,headers={**self.fixture.other,'Idempotency-Key':'x'}).status_code,404)
        self.assertEqual(self.post('reject').status_code,422)
        self.assertEqual(self.post('save-revision',page=99,content='x').status_code,422)
        self.assertEqual(self.post('mark-error',reason='synthetic').status_code,422)
        self.assertEqual(self.post('save-revision',content='x').status_code,422)
        self.assertEqual(self.post('approve',content='x').status_code,422)
        self.assertEqual(self.client.post(url,json=body,headers=self.fixture.auth).status_code,422)
        self.ledger.writers=frozenset()
        self.assertEqual(self.post('approve').status_code,403)
        self.fixture.app.state.review_ledger=None
        self.assertEqual(self.post('approve').status_code,503)

    def test_flag_reject_source_change_and_pagination(self):
        self.assertEqual(self.post('mark-error',page=1,reason='synthetic').json()['status'],'flagged')
        rejected=self.post('reject',version=1,reason='synthetic').json()
        self.assertEqual(rejected['status'],'rejected')
        self.assertFalse(rejected['reparse_task_created'])
        self.source['original_result']={'changed':True}
        self.assertEqual(self.post('approve',version=2).status_code,409)
        result=self.client.get(f'/api/review/{self.pid}/events?page=2&page_size=1',headers=self.fixture.auth).json()
        self.assertEqual(result['total'],2)
        self.assertEqual(len(result['list']),1)
        self.assertEqual(result['list'][0]['version'],1)

    def test_concurrent_version_allocation_and_rollback(self):
        body=dict(base_result_id=self.pid,expected_version=0,reason='',page=None,content=None,span=None)
        def write(_):
            try:
                return self.ledger.apply('alice',self.pid,'approve',body,uuid4().hex,'a'*64)['version']
            except MinerUError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(write,range(2)))
        self.assertCountEqual(results,[1,'review_version_conflict'])
        self.assertEqual(self.ledger.events('alice',self.pid,1,20)['total'],1)
        self.assertEqual(self.ledger.state('alice',self.pid)['version'],1)

    def test_runtime_account_cannot_rewrite_audit(self):
        import pymysql
        with self.assertRaises(pymysql.err.OperationalError):
            with self.ledger.connection() as connection, connection.cursor() as cursor:
                cursor.execute('UPDATE review_events SET version=version WHERE 1=0')


if __name__=='__main__':
    unittest.main()
