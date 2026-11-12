"""仅使用隔离审核配置验证私密runtime加载与部署工厂。"""
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

config=json.loads(Path('/private/test-review.json').read_text())
values={'PARSING_API_TOKENS_JSON': json.dumps({'a'*32:dict(principal_id='runtime-reviewer',owner_id=None,roles=['REVIEWER'],review_owner_scopes=['alice'],credential_status='active')}),
        'PARSING_RESULT_PG_DSN':'postgresql://unconfigured@127.0.0.1:1/not_used',
        'REVIEW_MYSQL_CONFIG_JSON':json.dumps(config)}
runtime=Path('/tmp/runtime-check.json')
runtime.write_text(json.dumps(values))
spec=importlib.util.spec_from_file_location('release_entry','/opt/workbench/entrypoint.py')
entry=importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)
loaded=entry.configuration(runtime)
assert json.loads(loaded['REVIEW_MYSQL_CONFIG_JSON'])['database'].startswith('market_review_test_')
os.environ.update(REVIEW_MYSQL_CONFIG_JSON=loaded['REVIEW_MYSQL_CONFIG_JSON'],
    PARSING_API_TOKENS_JSON=loaded['PARSING_API_TOKENS_JSON'],MINERU_ENABLED='0',
    DUAL_OCR_ENABLED='0',MINERU_RESULT_DIR='/tmp/runtime-candidate')
os.environ.pop('PARSING_RESULT_PG_DSN',None)
from deploy.release.application import create_app
from fastapi.testclient import TestClient
app=create_app()
reader=app.state.frontend_reader
pid='runtime-synthetic-'+uuid4().hex
reader.review=Mock()
reader.review.detail.return_value=dict(parse_id=pid,document_id='synthetic-doc',file_name='synthetic.pdf',
    parsing_status='needs_review',requires_review=True,source_location={'owner_id':'alice'},quality={},raw_text='original',
    markdown_content='original',original_result={'pages':[{'page_number':1}]})
auth={'Authorization':'Bearer '+'a'*32}
with TestClient(app) as client:
    assert client.get('/dashboard').status_code==200
    assert len(client.get('/api/openapi.json',headers=auth).json()['paths'])==30
    detail=client.get('/api/review/'+pid,headers=auth).json()
    assert detail['review_write_supported'] and detail['review_ledger']['available']
    response=client.post('/api/review/'+pid+'/approve',json={'base_result_id':pid,'expected_version':0},
        headers={**auth,'Idempotency-Key':uuid4().hex})
    assert response.status_code==200
    assert response.json()['publish_authorized'] is False
    detail=client.get('/api/review/'+pid,headers=auth).json()
    assert detail['raw_text']=='original' and detail['requires_review']
    assert detail['review_ledger']['status']=='approved'
print('isolated private runtime loading / deployment factory / MySQL write PASS')
