"""显式授权后的六项补跑；保留原测试方法，仅适配目标身份及安全夹具。"""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch


TABLES = ('law_chunks','mr_kb_versions','mr_document_versions','mr_chunks','mr_kb_documents',
          'mr_active','mr_active_chunk_map','mr_release_history')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--qa-tests',type=Path,required=True)
    parser.add_argument('--scope',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run-user-authorized-business-tests',action='store_true')
    args=parser.parse_args()
    if not args.run_user_authorized_business_tests:
        parser.error('必须明确启用用户授权的业务库测试；默认不连接、不写入')
    scope=json.loads(args.scope.read_text('utf-8'))
    if (scope.get('authorization')!='user-confirmed-current-chat-2026-11-10' or
        scope.get('database')!='market_regulation' or scope.get('source_commit')!='8ecff8866232ca33d0e350e6ead311fe8570aa89'):
        parser.error('授权目标或冻结版本不匹配')
    source=args.source.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((source/'snapshot-identity.json').read_text('utf-8'))
    if manifest['source_commit']!=scope['source_commit']:raise RuntimeError('快照SHA错误')
    for record in manifest['files']:
        data=(source/record['path']).read_bytes()
        if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=record['blob']:
            raise RuntimeError('冻结源码摘要变化')
    sys.dont_write_bytecode=True;sys.path.insert(0,str(source))
    package=types.ModuleType('tests');package.__path__=[str(args.qa_tests.resolve()),str(source/'tests')]
    sys.modules['tests']=package
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import parse_dsn
    dsn=os.environ['OFFLINE_APPROVED_PG_DSN'];parameters=parse_dsn(dsn)
    if any(parameters.get(k)!=scope[k] for k in ['host','dbname','user','port']):
        raise RuntimeError('连接参数与批准目标不匹配')
    connection=psycopg2.connect(dsn,connect_timeout=5,application_name='qa_offline_scope_audit')
    connection.autocommit=True
    connection.set_session(readonly=True)
    def select(query,params=()):
        with connection.cursor() as cursor:
            cursor.execute(query,params);return cursor.fetchall()
    identity=select('SELECT current_database(),current_user,inet_server_addr()::text,inet_server_port()')[0]
    if identity!=(scope['database'],scope['user'],scope['host'],int(scope['port'])):
        raise RuntimeError('实际数据库身份错误')
    extension=select("SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'")
    if extension!=[('public',)]:raise RuntimeError('必须已有public.vector，禁止自动安装/迁移')
    for name in ['documents','pages','blocks','tables','cells']:
        if select('SELECT to_regclass(%s)::text',('document_review.'+name,))[0][0] is None:
            raise RuntimeError('既有解析结果Schema不完整，禁止自动迁移')
    existing=select("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname IN ('public','document_review') AND c.relkind IN ('r','p') ORDER BY 1,2")
    def snapshot():
        value={}
        for namespace,name in existing:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL('SELECT md5(row_to_json(t)::text) FROM {}.{} t ORDER BY 1').format(sql.Identifier(namespace),sql.Identifier(name)))
                digests=[]
                while True:
                    batch=cursor.fetchmany(2000)
                    if not batch:break
                    digests.extend(r[0] for r in batch)
                value[namespace+'.'+name]=dict(Counter(digests))
        return value
    before=snapshot();(output/'business-before.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    before_parse_ids={r[0] for r in select('SELECT parse_id FROM document_review.documents')}
    planned=set();successful=set();retained=[];events=[]
    from qa_core.utils import stable_hash
    from qa_core.storage.parsing_results import PostgresResultSink
    original_save=PostgresResultSink.save
    def synthetic_save(self,task,file,result):
        if task['owner'] not in {'synthetic-qa','synthetic-dual-qa'} or not re.fullmatch('[0-9a-f]{32}',task['id']) or not re.fullmatch('[0-9a-f]{32}',file['id']):
            raise RuntimeError('拒绝非本轮合成任务')
        if not result.file_name.startswith('synthetic') or parse_dsn(self.dsn)!=parameters:
            raise RuntimeError('合成来源或连接不匹配')
        pid=stable_hash('parsing-result-v1',task['owner'],task['id'],file['id'])
        if pid not in planned:
            if select('SELECT 1 FROM document_review.documents WHERE parse_id=%s',(pid,)):
                raise RuntimeError('随机测试ID与已有记录冲突')
            planned.add(pid)
        saved=original_save(self,task,file,result);successful.add(saved);return saved
    from qa_core.storage.database import Database
    class ScopedLifecycleDatabase(Database):
        def __init__(self,**kwargs):
            if parse_dsn(kwargs.get('pg_dsn',''))!=parameters:raise RuntimeError('生命周期连接不匹配')
            super().__init__(**kwargs);self.owned=None;self.ready=False
        def own_bindings(self):
            for table in TABLES:
                with self.connection.cursor() as cursor:
                    cursor.execute('SELECT n.nspname AS schema FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=to_regclass(%s)',(table,))
                    record=cursor.fetchone()
                if not record or record['schema']!=self.owned:raise RuntimeError('关系解析回退至业务对象：'+table)
        def execute(self,query,params=None):
            text=' '.join(query.split());upper=text.upper()
            if upper.startswith('CREATE SCHEMA '):
                name=text[len('CREATE SCHEMA '):]
                if self.owned or not re.fullmatch('mvp_test_[0-9a-f]{32}',name):raise RuntimeError('拒绝不安全Schema')
                if select('SELECT 1 FROM pg_namespace WHERE nspname=%s',(name,)):raise RuntimeError('测试Schema已存在')
                value=super().execute(query,params);self.owned=name;retained.append(name);events.append('CREATE_OWN_SCHEMA');return value
            if upper.startswith('SET SEARCH_PATH TO '):
                if text not in ['SET search_path TO '+str(self.owned)+', public','SET search_path TO public']:
                    raise RuntimeError('非法search_path')
                return super().execute(query,params)
            if upper.startswith('DROP '):
                if text=='DROP SCHEMA '+str(self.owned)+' CASCADE':
                    events.append('SUPPRESSED_DROP_OWN_SCHEMA');return super().execute('SELECT 1')
                raise RuntimeError('不允许删除Schema或表')
            if upper=='CREATE EXTENSION IF NOT EXISTS VECTOR':
                events.append('REUSED_EXISTING_VECTOR');return super().execute('SELECT 1')
            if upper.startswith(('ALTER ','TRUNCATE ','GRANT ','REVOKE ','CREATE EXTENSION')) or re.search(r'\b(?:public|document_review)\s*\.',query,re.I):
                raise RuntimeError('禁止改变现有业务对象')
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT current_schema() AS schema');current=cursor.fetchone()['schema']
            if not self.owned or current!=self.owned:raise RuntimeError('SQL不在本次测试Schema')
            if self.ready:self.own_bindings()
            if upper.startswith(('INSERT ','UPDATE ','DELETE ','CREATE TABLE','CREATE INDEX','LOCK TABLE')):
                events.append(upper.split()[0]+'_OWN_SCHEMA')
            return super().execute(query,params)
        def initialize(self):
            super().initialize();self.own_bindings();self.ready=True
        def publish(self,*args,**kwargs):
            self.own_bindings();return super().publish(*args,**kwargs)
    for key in ['PARSING_TEST_PG_DSN','QA_ISOLATED_PG_DSN','MVP_TEST_PG_DSN']:os.environ[key]=dsn
    os.environ['MARKET_REGULATION_DUAL_ENGINE_TEST_ADAPTER']='tests.dual_engine_adapter:run_scenario'
    from tests import test_round01_postgres_acceptance as acceptance
    from tests import test_postgres_integration as lifecycle
    from tests.run_round01_validation import RecordingResult
    def approved_setup(self):
        self.dsn=dsn;self.connection=psycopg2.connect(dsn,connect_timeout=5)
        self.addCleanup(self.connection.close)
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT current_database(),current_user,inet_server_addr()::text,inet_server_port()')
            self.assertEqual(cursor.fetchone(),identity)
        self.connection.rollback()
    suite=unittest.TestSuite()
    for name in ['tests.test_parsing_postgres','tests.test_round01_postgres_acceptance',
                 'tests.test_v02_dual_engine.DualEngineAcceptance.test_I_repeat_and_failure_do_not_duplicate_or_replace_database_rows',
                 'tests.test_postgres_integration']:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    with ExitStack() as stack:
        stack.enter_context(patch.object(PostgresResultSink,'save',synthetic_save))
        stack.enter_context(patch.object(acceptance.Round01PostgresAcceptance,'setUp',approved_setup))
        stack.enter_context(patch.object(lifecycle,'Database',ScopedLifecycleDatabase))
        result=unittest.TextTestRunner(verbosity=2,resultclass=RecordingResult).run(suite)
    # 原CLI实际读取本轮合成记录；只读连接，不向结果库写入。
    preview_status='BLOCKED_NO_SYNTHETIC_ROW'
    candidates=[]
    for pid in sorted(successful):
        raw=select('SELECT original_result FROM document_review.documents WHERE parse_id=%s',(pid,))[0][0]
        if any(b.get('kind') not in {'table','image','header','footer','number','footnote'} and b.get('raw_text','').strip()
               for p in raw.get('pages',[]) for b in p.get('layout_blocks',[])):
            candidates.append(pid)
    if candidates:
        chosen=candidates[0];config=output/'private-runtime.json'
        config.write_text(json.dumps({'PARSING_RESULT_PG_DSN':dsn}),encoding='utf-8')
        spec=importlib.util.spec_from_file_location('offline_business_cli',source/'scripts/preview_offline_ingestion.py')
        cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
        code=cli.main(['--parse-id',chosen,'--config',str(config),'--document-type','case','--output',str(output/'read-preview')])
        preview_status='PASS' if code==0 else 'FAIL'
    after=snapshot();unchanged=True;additions={}
    for table,old in before.items():
        current=after[table]
        if table.startswith('public.'):
            if current!=old:unchanged=False
        elif any(current.get(digest,0)<count for digest,count in old.items()):unchanged=False
        additions[table]=sum(current.values())-sum(old.values())
    all_parse_ids={row[0] for row in select('SELECT parse_id FROM document_review.documents')}
    new_ids=all_parse_ids-before_parse_ids
    if not new_ids.issubset(planned):unchanged=False
    if select("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname IN ('public','document_review') AND c.relkind IN ('r','p') ORDER BY 1,2")!=existing:
        unchanged=False
    for name in retained:
        if not select('SELECT 1 FROM pg_namespace WHERE nspname=%s',(name,)):unchanged=False
    bindings={n:m.__file__ for n,m in sys.modules.copy().items() if n.startswith('qa_core') and getattr(m,'__file__',None)}
    assert all(Path(p).resolve().is_relative_to(source) for p in bindings.values())
    summary=dict(source_commit=scope['source_commit'],handoff_commit=scope['handoff_commit'],qa_commit=scope['qa_commit'],
                 identity=dict(database=identity[0],user=identity[1],server_address=identity[2],port=identity[3]),
                 total=result.testsRun,outcomes=result.outcomes,failures=len(result.failures),errors=len(result.errors),
                 skips=[dict(test=t.id(),reason=r) for t,r in result.skipped],
                 existing_business_rows_unchanged=unchanged,additions=additions,
                 retained_schemas=retained,lifecycle_events=dict(Counter(events)),
                 synthetic_parse_ids=sorted(successful),all_new_ids_registered=new_ids.issubset(planned),
                 database_cli_preview=preview_status,bindings=bindings,
                 ddl_executed=bool(retained),test_projection_delete_executed='DELETE_OWN_SCHEMA' in events,
                 dropped_schema=False,real_business_publish_executed=False)
    (output/'business-after.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
    (output/'database-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    connection.close()
    return 0 if result.wasSuccessful() and not result.skipped and unchanged and preview_status=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
