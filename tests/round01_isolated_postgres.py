"""使用已有镜像创建QA专用内部数据库；不访问业务库，不删除数据库卷。"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4


def command(*args, **kwargs):
    result = subprocess.run(args, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError('QA专用容器操作失败；详情保留在本地执行环境')
    return result.stdout


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--include-v02',action='store_true',help='同时执行双引擎A–J，包括真实独立PostgreSQL场景')
    args=parser.parse_args()
    qa=Path(__file__).resolve().parents[1]
    source=args.source.resolve()
    output=args.output.resolve()
    if not output.is_relative_to(qa/'local'):
        parser.error('输出必须位于QA工作树的local忽略目录')
    output.mkdir(parents=True,exist_ok=True)
    source_sha=command('git','-C',str(source),'rev-parse','HEAD').decode().strip()
    test_sha=command('git','-C',str(qa),'rev-parse','HEAD').decode().strip()
    if command('git','-C',str(source),'status','--porcelain').strip():
        parser.error('验证源码工作树必须干净')
    pg_image=command('docker','image','inspect','pgvector/pgvector:pg16','--format','{{.Id}}').decode().strip()
    app_image=command('docker','image','inspect','market-regulation-app:local','--format','{{.Id}}').decode().strip()
    suffix=uuid4().hex[:12]
    network='qa-round01-net-'+suffix
    container='qa-round01-pg-'+suffix
    password=secrets.token_hex(24)
    pg_env=output/'postgres.env'
    pg_env.write_text(f'POSTGRES_DB=qa_round01\nPOSTGRES_USER=postgres\nPOSTGRES_PASSWORD={password}\n',encoding='utf-8')
    dsn=f'dbname=qa_round01 user=postgres password={password} host=qa-postgres port=5432 sslmode=disable'
    runner_env=output/'runner.env'
    runner_env.write_text('\n'.join([f'{key}={dsn}' for key in [
        'MVP_TEST_PG_DSN','PARSING_TEST_PG_DSN','QA_ISOLATED_PG_DSN']])+\
        '\nPYTHONDONTWRITEBYTECODE=1\nHF_HUB_OFFLINE=1\nTRANSFORMERS_OFFLINE=1\n',encoding='utf-8')
    if args.include_v02:
        with runner_env.open('a',encoding='utf-8') as stream:
            stream.write('MARKET_REGULATION_DUAL_ENGINE_TEST_ADAPTER=tests.dual_engine_adapter:run_scenario\n')
    metadata={'source_commit':source_sha,'qa_test_commit':test_sha,'container':container,'network':network,
              'postgres_image':pg_image,'runtime_image':app_image,'host_ports':[], 'database_data_retained':True}
    created=False
    try:
        command('docker','network','create','--internal','--label','market-qa=round01',network)
        command('docker','run','-d','--name',container,'--label','market-qa=round01',
                '--network',network,'--network-alias','qa-postgres','--env-file',str(pg_env),pg_image)
        created=True
        for _ in range(45):
            ready=subprocess.run(['docker','exec',container,'pg_isready','-U','postgres','-d','qa_round01'],capture_output=True)
            if ready.returncode==0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('QA专用数据库未在限定时间内就绪')
        fixture=(qa/'tests/fixtures/round01_document_review.sql').read_bytes()
        command('docker','exec','-i',container,'psql','-v','ON_ERROR_STOP=1','-U','postgres','-d','qa_round01',input=fixture)
        args_run=['docker','run','--rm','--network',network,'--env-file',str(runner_env),
                  '--mount',f'type=bind,source={source.as_posix()},target=/source,readonly',
                  '--mount',f'type=bind,source={(qa/"tests").as_posix()},target=/qa-tests,readonly',
                  '--mount',f'type=bind,source={output.as_posix()},target=/qa-output',
                  '--workdir','/source','--entrypoint','python',app_image,'-B','/qa-tests/run_round01_validation.py',
                  '--source','/source','--database-only','--source-commit',source_sha,'--qa-test-commit',test_sha,
                  '--result-json','/qa-output/database-execution.json']
        if args.include_v02:
            args_run.append('--include-v02')
        execution=subprocess.run(args_run,capture_output=True)
        (output/'database-tests.log').write_bytes(execution.stdout+execution.stderr)
        metadata['exit_code']=execution.returncode
        print('独立PostgreSQL测试退出码：'+str(execution.returncode))
        return execution.returncode
    finally:
        if created:
            stopped=subprocess.run(['docker','stop',container],capture_output=True)
            metadata['test_database_stopped']=stopped.returncode==0
        (output/'resources.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        # 保留测试数据库及资源标识，避免未经授权删除数据库数据。


if __name__=='__main__':
    raise SystemExit(main())
