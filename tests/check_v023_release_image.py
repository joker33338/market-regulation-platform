"""最终镜像增量检查：源码来源、前端静态资源及正式契约，无状态或外网。"""
import hashlib
import json
import os
from pathlib import Path
import re

os.environ.update(MINERU_RESULT_DIR='/tmp/final-release-check',MINERU_ENABLED='0',DUAL_OCR_ENABLED='0',PARSING_API_TOKENS_JSON=json.dumps({'a'*32:'synthetic'}))
for key in ('PARSING_RESULT_PG_DSN','PG_DSN','KNOWLEDGE_WRITE_PG_DSN','REVIEW_MYSQL_CONFIG_JSON','AUTH_ACCOUNTS_FILE','PARSING_AUTH_CONFIG_FILE'):
    os.environ.pop(key,None)
manifest=json.loads(Path(os.environ['CANDIDATE_SOURCE_HASHES']).read_text())
for name,expected in manifest['files'].items():
    assert hashlib.sha256(Path(name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==expected,name
from deploy.release.application import create_app
from fastapi.testclient import TestClient
with TestClient(create_app()) as client:
    pages=['/','/login','/dashboard','/documents','/parsing','/review','/knowledge/ingestion','/knowledge/search','/library/laws','/library/cases','/admin/accounts','/system']
    for url in pages:
        response=client.get(url);assert response.status_code==200 and 'id="app"' in response.text,url
    assets=list(Path('/app/frontend/dist/assets').glob('*'))
    assert assets
    for asset in assets:
        if asset.is_file():assert client.get('/assets/'+asset.name).status_code==200,asset.name
    assert client.get('/assets/missing.js').status_code==404
    assert client.get('/api/missing').status_code==404
    assert client.get('/api/documents').status_code==401
    schema=client.get('/api/openapi.json',headers={'Authorization':'Bearer '+'a'*32}).json()
    snapshot=json.loads(Path(os.environ['OPENAPI_SNAPSHOT']).read_text())
    assert schema['info']['version']=='0.2.3' and schema['info']['x-contract-version']=='frontend-api-v0.2.3'
    assert schema['paths']==snapshot['paths'] and schema['components']==snapshot['components']
    assert 'delete' in schema['paths']['/api/documents/{file_id}']
    print(json.dumps({'source_files_verified':len(manifest['files']),'pages':len(pages),'assets':len(assets),'openapi_paths':len(schema['paths']),'schema_matches_snapshot':True,'anonymous_documents':401}))
