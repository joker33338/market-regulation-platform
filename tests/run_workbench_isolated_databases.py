"""短生命周期隔离PG验证；仅复用既有MySQL测试库，保留容器、卷和私密原始证据。"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

import psycopg2


def docker(*args):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf-8')
    if result.returncode:raise RuntimeError('isolated_docker_command_failed')
    return result.stdout.strip()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--image',required=True)
    parser.add_argument('--mysql-test-config',type=Path,required=True)
    parser.add_argument('--suite',action='append')
    args=parser.parse_args()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',args.image):raise RuntimeError('immutable_pg_image_required')
    config=json.loads(args.mysql_test_config.read_text(encoding='utf-8-sig'))
    if not str(config.get('database','')).startswith('market_review_test_'):raise RuntimeError('isolated_mysql_only')
    evidence=Path('local/workbench-evidence/databases')/uuid4().hex[:12]
    private=evidence/'private';private.mkdir(parents=True)
    config.update(host='127.0.0.1',port=13306)
    mysql_copy=private/'mysql-test.json';mysql_copy.write_text(json.dumps(config),encoding='utf-8')
    suites=args.suite or ['tests/test_business_library_pg.py','tests/test_frontend_workflow_pg.py','tests/test_workbench_real_pg.py']
    records=[]
    for index,suite in enumerate(suites):
        name='workbench-pg-test-'+uuid4().hex[:12]
        volume=name+'-data'
        docker('volume','create','--label','purpose=workbench-isolated-test',volume)
        container=None
        record={'suite':suite,'container':name,'volume':volume,'pg_image':args.image,'status':'SETUP'}
        try:
            container=docker('run','--pull','never','-d','--name',name,'--label','purpose=workbench-isolated-test',
                '-e','POSTGRES_DB=qa_round01','-e','POSTGRES_HOST_AUTH_METHOD=trust',
                '--publish','127.0.0.1::5432','--mount','type=volume,source='+volume+',target=/var/lib/postgresql/data',args.image)
            if not re.fullmatch(r'[a-f0-9]{64}',container):raise RuntimeError('unexpected_container_identity')
            port=docker('port',container,'5432/tcp').splitlines()[0].rsplit(':',1)[1]
            admin='host=127.0.0.1 port='+port+' user=postgres dbname=qa_round01 connect_timeout=3'
            deadline=time.monotonic()+40
            while True:
                try:
                    with psycopg2.connect(admin) as connection:pass
                    break
                except psycopg2.OperationalError:
                    if time.monotonic()>deadline:raise RuntimeError('isolated_pg_not_ready')
                    time.sleep(1)
            env=os.environ.copy();env['PYTHONUTF8']='1'
            for key in ('PG_DSN','PARSING_RESULT_PG_DSN','KNOWLEDGE_WRITE_PG_DSN','REVIEW_MYSQL_CONFIG_JSON','AUTH_ACCOUNTS_FILE'):
                env.pop(key,None)
            env.update(LIBRARY_ISOLATED_PG='1',LIBRARY_TEST_DSN=admin,DELETE_PG_FIXTURE_ISOLATED='1',
                FRONTEND_WORKFLOW_TEST_PG_ADMIN_DSN=admin,
                FRONTEND_WORKFLOW_TEST_PG_DSN=admin.replace('user=postgres','user=frontend_api_test'),
                REVIEW_MYSQL_TEST_CONFIG=str(mysql_copy.resolve()))
            report=evidence/('suite-'+str(index)+'.xml')
            print('RUN',suite,flush=True)
            result=subprocess.run([sys.executable,'-m','pytest',suite,'-q','-p','no:cacheprovider','--junitxml='+str(report)],
                capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,timeout=240)
            (private/('suite-'+str(index)+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
            record.update(status='PASS' if result.returncode==0 else 'FAIL',returncode=result.returncode)
            if report.exists():
                root=ET.parse(report).getroot()
                record['tests']=sum(int(suite.attrib.get('tests',0)) for suite in root.iter('testsuite'))
                record['failures']=sum(int(suite.attrib.get('failures',0)) for suite in root.iter('testsuite'))
                record['errors']=sum(int(suite.attrib.get('errors',0)) for suite in root.iter('testsuite'))
                record['skipped']=sum(int(suite.attrib.get('skipped',0)) for suite in root.iter('testsuite'))
            print(json.dumps(record),flush=True)
        finally:
            if container:
                purpose=docker('inspect','--format','{{index .Config.Labels "purpose"}}',container)
                if purpose!='workbench-isolated-test':raise RuntimeError('unexpected_test_container_label')
                (private/(name+'-log.txt')).write_text(docker('logs',container),encoding='utf-8')
                docker('stop','--time','10',container)
                record['container_state']='stopped'
            records.append(record)
            (evidence/'result.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    if any(record['status']!='PASS' for record in records):raise SystemExit(1)


if __name__=='__main__':
    main()
