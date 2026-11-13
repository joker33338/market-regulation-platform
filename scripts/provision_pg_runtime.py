"""获准后配置现有PG最小权限运行账号与来源校验；不修改业务数据。"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import secrets
import subprocess
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn,make_dsn

ROOT=Path(__file__).resolve().parents[1]
MARKER='market-regulation-v023-managed-runtime'

def snapshot(c):
    result={}
    with c.cursor() as q:
        q.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('public','document_review','business_library') ORDER BY 1,2")
        for schema,table in q.fetchall():
            q.execute(sql.SQL("SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM (SELECT md5(row_to_json(t)::text) h FROM {}.{} t)x").format(sql.Identifier(schema),sql.Identifier(table)))
            result[schema+'.'+table]=q.fetchone()
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply:raise SystemExit('仅在用户明确授权后使用--apply执行')
    info=json.loads(subprocess.check_output(['docker','inspect','market-regulation-app-1']))[0]
    runtime_path=Path(next(x['Source'] for x in info['Mounts'] if x['Destination']=='/private/runtime.json'))
    runtime=json.loads(runtime_path.read_text(encoding='utf-8-sig'));original=parse_dsn(runtime['PARSING_RESULT_PG_DSN'])
    database=original.get('dbname');assert database=='market_regulation'
    db=json.loads(subprocess.check_output(['docker','inspect','market-regulation-db-1']))[0]
    mapping=db['NetworkSettings']['Ports']['5432/tcp'];assert len(mapping)==1 and mapping[0]['HostIp']=='127.0.0.1'
    admin={**original,'host':'127.0.0.1','port':mapping[0]['HostPort']}
    output=ROOT/'local/release-v023/private';output.mkdir(parents=True,exist_ok=True)
    secret_file=output/'pg-credentials.json'
    roles=['market_api_v023','market_kb_writer_v023']
    if secret_file.exists():credentials=json.loads(secret_file.read_text(encoding='utf-8'))
    else:
        credentials={role:secrets.token_urlsafe(32) for role in roles}
        secret_file.write_text(json.dumps(credentials),encoding='utf-8')
    who=subprocess.check_output(['whoami'],text=True).strip()
    subprocess.run(['icacls',str(output),'/inheritance:r','/grant:r',who+':(OI)(CI)(F)'],check=True,capture_output=True)
    connection=psycopg2.connect(make_dsn(**admin),connect_timeout=5)
    try:
        before=snapshot(connection)
        with connection,connection.cursor() as q:
            q.execute('SELECT current_database()');assert q.fetchone()[0]==database
            for role in roles:
                q.execute("SELECT shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname=%s",(role,));existing=q.fetchone()
                if existing:
                    if existing[0]!=MARKER:raise RuntimeError('同名账号非本脚本管理，拒绝覆盖')
                else:
                    q.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %s').format(sql.Identifier(role)),(credentials[role],))
                    q.execute(sql.SQL('COMMENT ON ROLE {} IS %s').format(sql.Identifier(role)),(MARKER,))
                q.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database),sql.Identifier(role)))
                q.execute(sql.SQL('GRANT USAGE ON SCHEMA public,document_review,business_library TO {}').format(sql.Identifier(role)))
                q.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA public,document_review,business_library TO {}').format(sql.Identifier(role)))
            q.execute(sql.SQL('GRANT INSERT ON document_review.documents,document_review.pages,document_review.blocks,document_review.tables,document_review.cells TO {}').format(sql.Identifier(roles[0])))
            for statement in [
                'GRANT INSERT,UPDATE ON public.mr_kb_versions,public.mr_kb_documents,public.mr_active TO {}',
                'GRANT INSERT ON public.mr_document_versions,public.mr_chunks,public.mr_release_history TO {}',
                'GRANT INSERT,DELETE ON public.law_chunks,public.mr_active_chunk_map TO {}',
                'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}',
                'GRANT INSERT ON ALL TABLES IN SCHEMA business_library TO {}']:
                q.execute(sql.SQL(statement).format(sql.Identifier(roles[1])))
            migration=(ROOT/'scripts/sql/20261113_business_library_source_v2_up.sql').read_text(encoding='utf-8').replace('BEGIN;','').replace('COMMIT;','')
            q.execute(migration)
            if snapshot(connection)!=before:raise RuntimeError('业务数据摘要变化，回滚')
        validated={}
        for role in roles:
            test=psycopg2.connect(make_dsn(**{**admin,'user':role,'password':credentials[role]}),connect_timeout=5)
            try:
                with test,test.cursor() as q:
                    q.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=current_user");assert q.fetchone()==(False,False,False,False)
                    q.execute("SELECT has_table_privilege(current_user,'document_review.documents','UPDATE'),has_table_privilege(current_user,'document_review.documents','DELETE'),has_table_privilege(current_user,'public.mr_release_history','UPDATE'),has_table_privilege(current_user,'public.mr_release_history','DELETE'),has_schema_privilege(current_user,'public','CREATE')");assert q.fetchone()==(False,False,False,False,False)
                    validated[role]={'superuser':False,'raw_update_delete':False,'release_history_update_delete':False,'schema_create':False}
            finally:test.close()
        runtime['PARSING_RESULT_PG_DSN']=make_dsn(**{**original,'user':roles[0],'password':credentials[roles[0]]})
        runtime['KNOWLEDGE_WRITE_PG_DSN']=make_dsn(**{**original,'user':roles[1],'password':credentials[roles[1]]})
        target=output/'runtime-v023-final.json';target.write_text(json.dumps(runtime),encoding='utf-8')
        result={'database':database,'roles':validated,'source_schema':'business_library_source_v2','business_tables_unchanged':len(before),'runtime_prepared':True,'runtime_activated':False,'created_utc':datetime.now(timezone.utc).isoformat()}
        (output.parent/'pg-provision-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    finally:connection.close()

if __name__=='__main__':main()
