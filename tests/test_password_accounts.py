"""账号密码、会话撤销和全权限管理员的临时文件测试。"""
import hashlib
import json
import secrets
import time
import unittest
from unittest.mock import patch

from qa_core.api.accounts import hash_password
from tests import test_frontend_api as fixtures


class PasswordAccountTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.FrontendAPITests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.client=self.f.client;self.password=secrets.token_urlsafe(20)
        self.path=self.f.root/'accounts.json'
        accounts=[]
        for username,roles,owner in [('synthetic-admin',['ADMIN'],None),('synthetic-user',['USER'],'synthetic-owner')]:
            accounts.append(dict(username=username,password_hash=hash_password(self.password),principal_id=username,
                owner_id=owner,roles=roles,review_owner_scopes=[],credential_status='active',document_delete_owner_scopes=[]))
        self.path.write_text(json.dumps({'schema_version':1,'accounts':accounts,'events':[]}),encoding='utf-8')
        self.f.app.state.account_store.filename=str(self.path)

    def login(self,username='synthetic-admin',password=None):
        return self.client.post('/api/auth/login',json={'username':username,'password':password or self.password})

    def auth(self,username='synthetic-admin'):
        response=self.login(username)
        self.assertEqual(response.status_code,200,response.text)
        return {'Authorization':'Bearer '+response.json()['access_token']}

    def test_login_uses_hashed_credentials_and_no_store(self):
        response=self.login()
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(response.json()['expires_in'],3600)
        self.assertEqual(response.json()['principal']['data_scope'],'all')
        self.assertIn('knowledge.publish',response.json()['principal']['permissions'])
        self.assertNotIn(self.password,response.text)
        self.assertNotIn(self.password,self.path.read_text())
        self.assertNotIn(response.json()['access_token'],''.join(path.read_text() for path in self.f.app.state.account_store.root.glob('*.json')))
        self.assertEqual(self.login('unknown-account').status_code,401)
        self.assertEqual(self.login(password=secrets.token_urlsafe(20)).status_code,401)

    def test_admin_create_manage_and_user_cannot_access(self):
        admin=self.auth();user=self.auth('synthetic-user')
        self.assertEqual(self.client.get('/api/admin/accounts',headers=user).status_code,403)
        self.assertEqual(self.client.get('/api/admin/accounts').status_code,401)
        new_password=secrets.token_urlsafe(20)
        body={'username':'new-synthetic-user','password':new_password,'roles':['USER']}
        response=self.client.post('/api/admin/accounts',json=body,headers=admin)
        self.assertEqual(response.status_code,201,response.text)
        created=response.json()
        self.assertEqual(created['owner_id'],created['principal_id'])
        self.assertNotIn('password_hash',response.text)
        self.assertNotIn(new_password,response.text)
        self.assertEqual(self.client.post('/api/admin/accounts',json=body,headers=admin).status_code,409)
        self.assertEqual(self.client.post('/api/admin/accounts',json={**body,'username':'another-user'},headers=user).status_code,403)
        self.assertEqual(self.client.patch('/api/admin/accounts/'+created['principal_id'],json={'owner_id':'other'},headers=admin).status_code,422)
        events=self.client.get('/api/admin/account-events',headers=admin).json()
        self.assertEqual(events['total'],1)
        self.assertNotIn(new_password,json.dumps(events))

    def test_password_reset_and_account_disable_invalidate_old_session(self):
        admin=self.auth();user=self.auth('synthetic-user')
        new_password=secrets.token_urlsafe(20)
        response=self.client.patch('/api/admin/accounts/synthetic-user',json={'password':new_password},headers=admin)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/auth/me',headers=user).status_code,401)
        response=self.login('synthetic-user',new_password);self.assertEqual(response.status_code,200)
        user={'Authorization':'Bearer '+response.json()['access_token']}
        self.assertEqual(self.client.patch('/api/admin/accounts/synthetic-user',json={'credential_status':'disabled'},headers=admin).status_code,200)
        self.assertEqual(self.client.get('/api/auth/me',headers=user).status_code,401)

    def test_role_changes_apply_on_next_request_and_last_admin_is_protected(self):
        admin=self.auth();user=self.auth('synthetic-user')
        response=self.client.patch('/api/admin/accounts/synthetic-user',json={'roles':['REVIEWER'],'review_owner_scopes':['alice']},headers=admin)
        self.assertEqual(response.status_code,200,response.text)
        me=self.client.get('/api/auth/me',headers=user).json()
        self.assertEqual(me['roles'],['REVIEWER']);self.assertEqual(me['review_owner_scopes'],['alice'])
        response=self.client.patch('/api/admin/accounts/synthetic-user',json={'roles':['USER'],'review_owner_scopes':[]},headers=admin)
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn('review.write:review_scopes',self.client.get('/api/auth/me',headers=user).json()['permissions'])
        self.assertEqual(self.client.patch('/api/admin/accounts/synthetic-admin',json={'roles':['USER']},headers=admin).status_code,422)
        self.assertEqual(self.client.patch('/api/admin/accounts/synthetic-admin',json={'credential_status':'disabled'},headers=admin).status_code,409)

    def test_logout_expiry_and_corrupt_storage_fail_closed(self):
        auth=self.auth()
        self.assertEqual(self.client.post('/api/auth/logout',headers=auth).status_code,200)
        self.assertEqual(self.client.get('/api/auth/me',headers=auth).status_code,401)
        auth=self.auth()
        token=auth['Authorization'][7:]
        path=self.f.app.state.account_store.root/(hashlib.sha256(token.encode()).hexdigest()+'.json')
        session=json.loads(path.read_text());session['expires_at']=time.time()-1;path.write_text(json.dumps(session))
        self.assertEqual(self.client.get('/api/auth/me',headers=auth).status_code,401)
        self.path.write_text('invalid')
        self.assertEqual(self.login().status_code,503)

    def test_login_rate_limit_and_legacy_tokens_remain_supported(self):
        for _ in range(8):
            self.assertEqual(self.login('nonexistent-synthetic').status_code,401)
        self.assertEqual(self.login('nonexistent-synthetic').status_code,429)
        self.assertEqual(self.client.get('/api/auth/me',headers=self.f.auth).status_code,200)
        self.assertEqual(self.client.post('/api/auth/logout',headers=self.f.auth).status_code,409)

    def test_admin_reads_all_uploads_and_tasks_without_reassigning_owner(self):
        fid,task=self.f.upload_task()
        admin=self.auth()
        listing=self.client.get('/api/documents',headers=admin)
        self.assertEqual(listing.status_code,200,listing.text)
        self.assertIn(fid,[row['file_id'] for row in listing.json()['list']])
        self.assertEqual(self.client.get('/api/parse/tasks/'+task['task_id'],headers=admin).status_code,200)
        self.assertEqual(self.client.get('/api/parse/files/'+fid+'/source',headers=admin).status_code,200)
        self.assertEqual(self.f.service.repository.get(task['task_id'],'alice')['owner'],'alice')
        self.assertEqual(self.client.post('/api/parse/files?file_name=synthetic.pdf&owner_id=bob',content=self.f.data,headers=self.f.auth).status_code,403)

    def test_password_only_mode_and_no_automatic_legacy_owner_claim(self):
        admin=self.auth()
        response=self.client.post('/api/admin/accounts',headers=admin,json={'username':'reserved-owner',
            'password':secrets.token_urlsafe(20),'owner_id':'alice','roles':['USER']})
        self.assertEqual(response.status_code,409,response.text)
        with patch.dict('os.environ',{'AUTH_ACCOUNTS_FILE':str(self.path)}):
            from qa_core.document_parsing.mineru_api import create_app
            from fastapi.testclient import TestClient
            app=create_app(self.f.config,tokens={},service=self.f.service)
            with TestClient(app) as client:
                response=client.post('/api/auth/login',json={'username':'synthetic-admin','password':self.password})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(client.get('/api/auth/me',headers={'Authorization':'Bearer '+response.json()['access_token']}).status_code,200)

    def test_local_bootstrap_has_no_default_password_and_never_overwrites(self):
        from scripts.provision_auth_accounts import provision
        path=self.f.root/'bootstrap.json'
        principal_id=provision(path,'new-synthetic-admin',self.password)
        record=json.loads(path.read_text())
        self.assertEqual(record['accounts'][0]['principal_id'],principal_id)
        self.assertEqual(record['accounts'][0]['roles'],['ADMIN'])
        self.assertNotIn(self.password,path.read_text())
        before=path.read_bytes()
        with self.assertRaises(ValueError):
            provision(path,'another-synthetic-admin',self.password)
        self.assertEqual(path.read_bytes(),before)
