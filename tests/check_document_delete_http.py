"""无宿主端口的候选HTTP探针；仅临时文件、合成凭证和显式无引用夹具。"""
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uvicorn
from deploy.release.application import create_app


with tempfile.TemporaryDirectory() as directory:
    record=dict(principal_id='synthetic-delete-admin',owner_id='alice',roles=['ADMIN'],
        review_owner_scopes=[],credential_status='active',document_delete_owner_scopes=['alice'])
    os.environ.update(PARSING_API_TOKENS_JSON=json.dumps({'a'*32:record}),MINERU_ENABLED='1',
        MINERU_MODE='mock',MINERU_RESULT_DIR=directory,DUAL_OCR_ENABLED='0')
    os.environ.pop('PARSING_RESULT_PG_DSN',None)
    app=create_app()
    # 正向夹具不连接正式PG；引用适配器与失败关闭由单元/集成套件分别验证。
    app.state.document_delete_references=lambda *args:False
    listener=socket.socket();listener.bind(('127.0.0.1',0))
    port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
    thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True);thread.start()
    try:
        deadline=time.monotonic()+15
        while not server.started and thread.is_alive() and time.monotonic()<deadline:
            time.sleep(0.02)
        assert server.started
        def send(method,path,body=None,auth=True):
            headers={'Authorization':'Bearer '+'a'*32} if auth else {}
            request=Request('http://127.0.0.1:'+str(port)+path,data=body,method=method,headers=headers)
            try:
                response=urlopen(request,timeout=10)
            except HTTPError as error:
                response=error
            return response.status,response.read()
        code,body=send('GET','/api/openapi.json');schema=json.loads(body)
        assert code==200 and 'delete' in schema['paths']['/api/documents/{file_id}']
        operation=schema['paths']['/api/documents/{file_id}']['delete']
        assert all(str(status) in operation['responses'] for status in (401,403,404,409,422,503))
        code,body=send('GET','/dashboard');assert code==200 and b'id="app"' in body
        assert body==Path('/app/frontend/dist/index.html').read_bytes()
        code,body=send('POST','/api/parse/files?file_name=synthetic.pdf',b'%PDF-1.7 synthetic deletion sample')
        assert code==201;fid=json.loads(body)['file_id']
        assert send('DELETE','/api/documents/'+fid,auth=False)[0]==401
        code,body=send('DELETE','/api/documents/'+fid)
        assert code==200 and json.loads(body)['deleted'] is True
        code,body=send('GET','/api/documents');assert code==200 and json.loads(body)['total']==0
        for path in ('/api/documents/'+fid,'/api/documents/'+fid+'/parse-history','/api/parse/files/'+fid+'/source'):
            assert send('GET',path)[0]==404
        assert send('HEAD','/api/parse/files/'+fid+'/source')[0]==404
        assert send('DELETE','/api/documents/'+fid)[0]==404
        print(json.dumps({'http_delete_declared':True,'response_error_schemas_present':True,
            'upload':201,'delete':200,'list_after_delete':0,'detail_history_source':404,'repeat_delete':404,
            'contract':schema['info']['x-contract-version'],'paths':len(schema['paths'])}))
    finally:
        server.should_exit=True;thread.join(10);listener.close()
