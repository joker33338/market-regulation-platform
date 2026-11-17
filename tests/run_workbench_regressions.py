"""定向回归入口：只接受既有MySQL测试库，SQLite使用各测试临时目录。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mysql-test-config',type=Path,required=True)
    args=parser.parse_args()
    config=json.loads(args.mysql_test_config.read_text(encoding='utf-8-sig'))
    if not config.get('database','').startswith('market_review_test_'):
        raise RuntimeError('isolated_mysql_only')
    config.update(host='127.0.0.1',port=13306)
    evidence=Path('local/workbench-evidence/regression');evidence.mkdir(parents=True,exist_ok=True)
    filename=evidence/'mysql-test.json';filename.write_text(json.dumps(config),encoding='utf-8')
    env=os.environ.copy();env.update(PYTHONUTF8='1',REVIEW_MYSQL_TEST_CONFIG=str(filename.resolve()))
    for key in ('PG_DSN','PARSING_RESULT_PG_DSN','KNOWLEDGE_WRITE_PG_DSN','REVIEW_MYSQL_CONFIG_JSON',
                'AUTH_ACCOUNTS_FILE','LIBRARY_TEST_DSN','LIBRARY_ISOLATED_PG',
                'FRONTEND_WORKFLOW_TEST_PG_ADMIN_DSN','DELETE_PG_FIXTURE_ISOLATED'):
        env.pop(key,None)
    tests=[str(p) for p in sorted(Path('tests').glob('test_workbench_*.py'))
           if p.name not in ('test_workbench_real_pg.py','test_workbench_browser_pg.py')]
    tests+=['tests/test_reviewed_export.py','tests/test_source_segments.py','tests/test_case_ingestion.py',
            'tests/test_frontend_api.py','tests/test_ingestion_api.py','tests/test_document_delete.py',
            'tests/test_principal_rbac.py','tests/test_mysql_review.py','tests/test_password_accounts.py','tests/test_mineru_api.py']
    report=evidence/'result.xml'
    run=subprocess.run([sys.executable,'-m','pytest',*tests,'-q','-p','no:cacheprovider','--junitxml='+str(report)],
                       env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
    (evidence/'execution.log').write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
    root=ET.parse(report).getroot()
    summary={field:sum(int(s.attrib.get(field,0)) for s in root.iter('testsuite'))
             for field in ('tests','failures','errors','skipped')}
    summary.update(returncode=run.returncode,skipped_cases=[{'name':case.attrib['name'],'reason':case.find('skipped').attrib.get('message')}
        for case in root.iter('testcase') if case.find('skipped') is not None])
    (evidence/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    raise SystemExit(run.returncode)


if __name__=='__main__':
    main()
