"""候选内真实HTTP账号/权限/删除闭环；仅临时合成数据与显式无引用夹具。"""
import json
import os
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen

import uvicorn


with tempfile.TemporaryDirectory() as directory:
    from scripts.provision_auth_accounts import provision
    password=secrets.token_urlsafe(20)
    account_file=Path(directory)/'accounts.json'
    provision(account_file,'synthetic-admin',password)
    os.environ.update(AUTH_ACCOUNTS_FILE=str(account_file),PARSING_API_TOKENS_JSON='{}',MINERU_ENABLED='1',
                      MINERU_MODE='mock',MINERU_RESULT_DIR=directory,DUAL_OCR_ENABLED='0')
    for key in ('PG_DSN','PARSING_RESULT_PG_DSN','REVIEW_MYSQL_CONFIG_JSON','KNOWLEDGE_WRITE_PG_DSN'):
        os.environ.pop(key,None)
    from deploy.release.application import create_app
    app=create_app()
    # 此HTTP角色用例不冒充真实PG验证；引用保护由独立PG夹具测试。
    app.state.document_delete_references=lambda *args:False
    listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
    worker=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True);worker.start()
    try:
        deadline=time.monotonic()+15
        while not server.started and worker.is_alive() and time.monotonic()<deadline:
            time.sleep(.02)
        assert server.started
        def send(method,path,body=None,token=None,raw=False):
            headers={'Authorization':'Bearer '+token} if token else {}
            if body is not None and not raw:
                headers['Content-Type']='application/json';body=json.dumps(body).encode()
            request=Request('http://127.0.0.1:'+str(port)+path,data=body,method=method,headers=headers)
            try:
                response=urlopen(request,timeout=15)
            except HTTPError as error:
                response=error
            data=response.read()
            try:
                value=json.loads(data)
            except (ValueError,UnicodeDecodeError):
                value=data
            return response.status,value,response.headers
        code,receipt,headers=send('POST','/api/auth/login',{'username':'synthetic-admin','password':password})
        assert code==200 and headers['Cache-Control']=='no-store'
        admin=receipt['access_token'];assert receipt['principal']['data_scope']=='all'
        assert send('GET','/api/admin/accounts')[0]==401
        code,schema,_=send('GET','/api/openapi.json',token=admin)
        assert code==200 and schema['info']['x-contract-version']=='frontend-api-v0.2.3'
        assert len(schema['paths'])==54
        for path,method in [('/api/auth/login','post'),('/api/admin/accounts','post'),
                ('/api/admin/accounts/{principal_id}','patch'),('/api/parse/tasks/{task_id}/logs','get'),
                ('/api/system/api-logs','get'),('/api/system/error-logs','get'),
                ('/api/ingestion/precheck','post'),('/api/ingestion/batches','post'),
                ('/api/ingestion/publish','post'),('/api/ingestion/rollback','post'),('/api/system/capabilities','get')]:
            assert method in schema['paths'][path]
            assert '503' in schema['paths'][path][method]['responses']
        assert 'security' not in schema['paths']['/api/auth/login']['post']
        assert schema['paths']['/api/admin/accounts']['post']['security']
        assert any(item['name']=='owner_id' and item['in']=='query' for item in schema['paths']['/api/parse/tasks']['post']['parameters'])
        assert send('GET','/login')[1]==Path('/app/frontend/dist/index.html').read_bytes()
        user_password=secrets.token_urlsafe(20)
        code,created,_=send('POST','/api/admin/accounts',{'username':'synthetic-user','password':user_password,'roles':['USER']},admin)
        assert code==201 and 'password_hash' not in created
        code,login,_=send('POST','/api/auth/login',{'username':'synthetic-user','password':user_password})
        assert code==200;user=login['access_token']
        assert send('GET','/api/admin/accounts',token=user)[0]==403
        code,upload,_=send('POST','/api/parse/files?file_name=synthetic.pdf',b'%PDF-1.7 synthetic API workflow',user,True)
        assert code==201;file_id=upload['file_id']
        code,listing,_=send('GET','/api/documents',token=admin)
        assert code==200 and listing['list'][0]['owner_id']==created['owner_id']
        assert send('DELETE','/api/documents/'+file_id,token=user)[0]==403
        assert send('DELETE','/api/documents/'+file_id,token=admin)[0]==200
        assert send('GET','/api/documents',token=user)[1]['total']==0
        assert send('GET','/api/parse/files/'+file_id+'/source',token=admin)[0]==404
        assert send('POST','/api/auth/logout',token=user)[0]==200
        assert send('GET','/api/auth/me',token=user)[0]==401
        print(json.dumps({'password_only_login':True,'admin_all_permissions':True,'user_admin_access':403,
            'admin_cross_owner_delete':200,'user_delete':403,'logout_revokes_session':True,
            'contract':schema['info']['x-contract-version'],'paths':len(schema['paths']),
            'reference_fixture':'explicit_no_reference_not_real_pg','browser_password_form_tested':False}))
    finally:
        server.should_exit=True;worker.join(10);listener.close()
