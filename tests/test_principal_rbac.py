"""独立合成身份、RBAC和owner范围；不使用任何真实凭据。"""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from qa_core.api.principals import AuthRegistry
from qa_core.document_parsing.mineru_api import create_app
from qa_core.document_parsing.mineru_client import MinerUError
from tests import test_mysql_review as mysql


def entry(pid,owner=None,roles=None,scopes=None,status='active'):
    return dict(principal_id=pid,owner_id=owner,roles=roles or [],review_owner_scopes=scopes or [],credential_status=status)


class PrincipalConfigTests(unittest.TestCase):
    def test_different_tokens_cannot_share_principal(self):
        with self.assertRaises(MinerUError):
            AuthRegistry({'a'*32:entry('same','one',['USER']),'b'*32:entry('same','two',['USER'])})

    def test_user_owners_cannot_be_silently_shared(self):
        with self.assertRaises(MinerUError):
            AuthRegistry({'a'*32:entry('one','same',['USER']),'b'*32:entry('two','same',['USER'])})

    def test_pg_scope_query_is_parameterized_and_empty_scope_false(self):
        from qa_core.api.read_store import ReviewReader
        from unittest.mock import MagicMock
        connection=MagicMock();cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value={'total':0};cursor.fetchall.return_value=[]
        with patch('psycopg2.connect',return_value=connection):
            ReviewReader('synthetic').listing(('alice','bob'),1,20)
        queries=cursor.execute.call_args_list[1:]
        self.assertTrue(all('ANY(%s)' in call.args[0] for call in queries))
        self.assertEqual(queries[0].args[1],[['alice','bob']])
        self.assertEqual(ReviewReader.scope(()),('FALSE',[]))

    def test_no_wildcard_review_scope(self):
        with self.assertRaises(MinerUError):
            AuthRegistry({'a'*32:entry('reviewer',roles=['REVIEWER'],scopes=['*'])})

    def test_legacy_local_user_is_not_reviewer(self):
        identity=AuthRegistry({'a'*32:'local-user'}).resolve('a'*32)
        self.assertEqual(identity.owner_id,'local-user')
        self.assertEqual(identity.roles,frozenset({'USER'}))
        self.assertFalse(identity.can_review('local-user'))

    def test_user_scope_and_admin_do_not_grant_review(self):
        registry=AuthRegistry({'a'*32:entry('ordinary','one',['USER'],['two']),
                               'b'*32:entry('administrator',roles=['ADMIN'],scopes=['one'])})
        self.assertEqual(registry.resolve('a'*32).read_owners,('one',))
        self.assertFalse(registry.resolve('a'*32).can_review('two'))
        self.assertEqual(registry.resolve('b'*32).read_owners,())


class PrincipalMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mysql.MySQLReviewTests.setUpClass()

    def setUp(self):
        self.fixture=mysql.MySQLReviewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client=self.fixture.client
        self.pid=self.fixture.pid
        self.records={
            'a'*32:entry('user-a','alice',['USER']),
            'b'*32:entry('user-b','bob',['USER']),
            'c'*32:entry('reviewer-1',roles=['REVIEWER'],scopes=['alice']),
            'd'*32:entry('reviewer-2',roles=['REVIEWER'],scopes=['alice']),
            'e'*32:entry('reviewer-outside',roles=['REVIEWER'],scopes=['bob']),
            'f'*32:entry('administrator',roles=['ADMIN']),
        }
        self.registry=self.fixture.fixture.app.state.auth_registry
        self.registry.replace(self.records)
        source=self.fixture.source
        def detail(owners,parse_id):
            allowed=[owners] if isinstance(owners,str) else owners
            if 'alice' not in allowed or parse_id!=self.pid:
                raise MinerUError('document_not_found',404)
            return copy.deepcopy(source)
        self.fixture.fixture.reader.review.detail.side_effect=detail

    def auth(self,letter): return {'Authorization':'Bearer '+letter*32}

    def write(self,letter='c',version=0,key='same-key',**extra):
        return self.client.post(f'/api/review/{self.pid}/approve',
            headers={**self.auth(letter),'Idempotency-Key':self.pid+'-'+key},
            json=dict(base_result_id=self.pid,expected_version=version,**extra))

    def test_two_users_data_isolation_and_no_review(self):
        self.assertEqual(self.client.get('/api/review/'+self.pid,headers=self.auth('a')).status_code,200)
        self.assertEqual(self.client.get('/api/review/'+self.pid,headers=self.auth('b')).status_code,404)
        self.assertEqual(self.write('a').status_code,403)
        self.assertEqual(self.write('b').status_code,403)

    def test_scoped_reviewer_can_write_without_personal_owner(self):
        detail=self.client.get('/api/review/'+self.pid,headers=self.auth('c')).json()
        self.assertTrue(detail['review_write_supported'])
        receipt=self.write().json()
        self.assertEqual(receipt['operator_id'],'reviewer-1')
        self.assertEqual(receipt['owner_id'],'alice')
        self.assertFalse(receipt['original_result_modified'])
        self.assertEqual(self.fixture.source['raw_text'],'synthetic original')

    def test_reviewer_outside_scope_remains_404(self):
        self.assertEqual(self.write('e').status_code,404)
        self.assertEqual(self.client.get('/api/review/'+self.pid,headers=self.auth('e')).status_code,404)
        self.assertEqual(self.client.get(f'/api/review/{self.pid}/events',headers=self.auth('e')).status_code,404)

    def test_two_reviewers_same_owner_have_distinct_operator_and_idempotency(self):
        first=self.write('c',0)
        second=self.write('d',1)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(second.status_code,200,second.text)
        self.assertNotEqual(first.json()['operator_id'],second.json()['operator_id'])
        self.assertEqual(first.json()['owner_id'],second.json()['owner_id'])
        self.assertNotEqual(first.json()['event_id'],second.json()['event_id'])
        self.assertEqual(self.write('c',0).json()['event_id'],first.json()['event_id'])
        self.assertEqual(self.write('d',0).status_code,409)

    def test_disabled_credential_immediately_denied(self):
        self.records['c'*32]['credential_status']='revoked'
        self.registry.replace(self.records)
        self.assertEqual(self.write().status_code,401)

    def test_role_revocation_ignores_legacy_writers(self):
        self.records['c'*32]['roles']=[]
        self.registry.replace(self.records)
        self.assertEqual(self.write().status_code,403)
        self.assertEqual(self.client.get('/api/review/'+self.pid,headers=self.auth('c')).status_code,404)

    def test_admin_is_not_reviewer(self):
        self.assertEqual(self.write('f').status_code,403)
        self.assertEqual(self.client.get('/api/review/'+self.pid,headers=self.auth('f')).status_code,404)

    def test_body_cannot_forge_actor_or_owner(self):
        self.assertEqual(self.write(operator_id='administrator').status_code,422)
        self.assertEqual(self.write(owner_id='bob').status_code,422)

    def test_original_source_download_respects_review_scope(self):
        fid,_=self.fixture.fixture.upload_task()
        path='/api/parse/files/'+fid+'/source'
        self.assertEqual(self.client.get(path,headers=self.auth('c')).status_code,200)
        self.assertEqual(self.client.get(path,headers=self.auth('e')).status_code,404)

    def test_private_file_revocation_is_effective_next_request(self):
        from qa_core.document_parsing.mineru_config import MinerUConfig
        runtime=self.fixture.fixture.root/'auth.json'
        runtime.write_text(json.dumps(self.records))
        config=MinerUConfig(result_dir=self.fixture.fixture.root/'reload')
        with patch.dict('os.environ',{'PARSING_API_TOKENS_JSON':json.dumps(self.records),
                                   'PARSING_AUTH_CONFIG_FILE':str(runtime)}):
            app=create_app(config)
            client=TestClient(app)
            self.addCleanup(client.close)
            import asyncio
            self.addCleanup(lambda: asyncio.run(app.state.service.client.close()))
            self.assertEqual(client.get('/api/auth/me',headers=self.auth('c')).status_code,200)
            self.records['c'*32]['roles']=[]
            runtime.write_text(json.dumps(self.records))
            self.assertEqual(client.post('/api/review/'+self.pid+'/approve',headers={**self.auth('c'),'Idempotency-Key':'role-revoked'},json={'base_result_id':self.pid,'expected_version':0}).status_code,403)
            self.records['c'*32]['credential_status']='disabled'
            runtime.write_text(json.dumps(self.records))
            self.assertEqual(client.get('/api/auth/me',headers=self.auth('c')).status_code,401)
