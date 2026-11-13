"""仅用于全新隔离PG的真实HTTP/浏览器链路服务，严禁加载正式runtime。"""
import json
import os
from pathlib import Path
import secrets


def main():
    if os.getenv('V023_REAL_PIPELINE')!='1':raise RuntimeError('需要明确隔离开关')
    from tests.test_frontend_workflow_pg import FrontendWorkflowPGTests
    FrontendWorkflowPGTests.setUpClass()
    admin=FrontendWorkflowPGTests.admin;runtime=FrontendWorkflowPGTests.runtime
    import psycopg2
    with psycopg2.connect(admin) as c,c.cursor() as q:
        q.execute('GRANT INSERT ON document_review.documents,document_review.pages,document_review.blocks,document_review.tables,document_review.cells TO frontend_api_test')
    mysql=FrontendWorkflowPGTests.mysql
    assert mysql['database'].startswith('market_review_test_')
    os.environ.update(PARSING_RESULT_PG_DSN=runtime,PG_DSN=runtime,KNOWLEDGE_WRITE_PG_DSN=runtime,
                      REVIEW_MYSQL_CONFIG_JSON=json.dumps(mysql),DUAL_OCR_ENABLED='0')
    root=Path('/tmp/v023-real-service');root.mkdir()
    from scripts.provision_auth_accounts import provision
    accounts=root/'accounts.json'
    provision(accounts,'synthetic-admin','Synthetic-Release-Only-2026')
    os.environ['AUTH_ACCOUNTS_FILE']=str(accounts)
    from qa_core.document_parsing.mineru_api import create_app
    from qa_core.document_parsing.mineru_config import MinerUConfig
    config=MinerUConfig(enabled=True,mode='local',provider='self_hosted',api_url='',result_dir=root/'parsing')
    app=create_app(config,tokens={})
    from deploy.release.application import VueFiles
    app.router.routes[:]=[r for r in app.routes if getattr(r,'path',None)!='/']
    app.mount('/',VueFiles(directory='/app/frontend/dist',html=True))
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=8180,log_level='warning',access_log=False)

if __name__=='__main__':main()
