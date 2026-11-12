import os
os.environ.update(MINERU_RESULT_DIR='/tmp/release-check', MINERU_ENABLED='0', DUAL_OCR_ENABLED='0', PARSING_API_TOKENS_JSON='{"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa":"synthetic"}')
os.environ.pop('PARSING_RESULT_PG_DSN',None)
from deploy.release.application import create_app
from fastapi.testclient import TestClient
with TestClient(create_app()) as c:
    for p in ('/','/dashboard','/documents','/parsing','/review','/knowledge/ingestion','/knowledge/search','/system'):
        r=c.get(p)
        assert r.status_code==200 and 'id="app"' in r.text,p
    assert c.get('/assets/missing.js').status_code==404
    assert c.get('/api/missing').status_code==404
    assert c.get('/api/documents').status_code==401
    h={'Authorization':'Bearer '+'a'*32}
    r=c.get('/api/openapi.json',headers=h)
    assert r.status_code==200 and len(r.json()['paths'])==22
    assert c.get('/api/documents',headers=h).json()['total']==0
    print('isolated release UI/API PASS')
