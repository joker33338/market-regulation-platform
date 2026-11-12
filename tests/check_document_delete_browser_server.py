"""短期浏览器夹具：仅合成上传；不连接正式PG或历史状态。"""
import json
import os
import tempfile

import uvicorn
from fastapi.testclient import TestClient
from deploy.release.application import create_app


with tempfile.TemporaryDirectory() as directory:
    records={letter*32:dict(principal_id='synthetic-'+role.lower(),owner_id='alice',roles=[role],
        review_owner_scopes=[],credential_status='active',document_delete_owner_scopes=['alice'] if role=='ADMIN' else [])
        for letter,role in [('a','ADMIN'),('b','USER')]}
    os.environ.update(PARSING_API_TOKENS_JSON=json.dumps(records),MINERU_ENABLED='1',MINERU_MODE='mock',
        MINERU_RESULT_DIR=directory,DUAL_OCR_ENABLED='0')
    for key in ('PARSING_RESULT_PG_DSN','PG_DSN','REVIEW_MYSQL_CONFIG_JSON'):
        os.environ.pop(key,None)
    app=create_app()
    results={}
    def references(owner,file_id,value):
        name=value['file_name']
        if 'conflict' in name:
            return True
        if 'unavailable' in name:
            raise OSError('synthetic unavailable')
        return False
    app.state.document_delete_references=references
    with TestClient(app) as client:
        for name in ('success','forbidden','conflict','unavailable','repeated'):
            response=client.post('/api/parse/files?file_name=synthetic-'+name+'.pdf',
                headers={'Authorization':'Bearer '+'a'*32},content=b'%PDF-1.7 synthetic browser '+name.encode())
            assert response.status_code==201
            results[name]=response.json()['file_id']
    print(json.dumps({'synthetic_files':results}),flush=True)
    uvicorn.run(app,host='0.0.0.0',port=8180,log_level='critical',access_log=False)
