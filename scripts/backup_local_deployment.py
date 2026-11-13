"""备份本地部署数据库及状态文件；不修改现有库、任务、模型或授权。"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tarfile
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]

def command(args):
    result=subprocess.run(args,capture_output=True)
    if result.returncode:raise RuntimeError('备份命令失败；不回显可能包含连接信息的输出')
    return result.stdout

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--app',default='market-regulation-app-1')
    parser.add_argument('--postgres',default='market-regulation-db-1')
    parser.add_argument('--mysql',default='market-regulation-mysql-1')
    args=parser.parse_args()
    if not all(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*',x) for x in [args.app,args.postgres,args.mysql]):raise ValueError('容器名称无效')
    output=ROOT/'local/backups'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]);output.mkdir(parents=True)
    app=json.loads(command(['docker','inspect',args.app]))[0]
    mounts={x['Destination']:Path(x['Source']) for x in app['Mounts'] if x['Type']=='bind'}
    state=mounts['/state'];runtime=mounts['/private/runtime.json']
    (output/'postgres.dump').write_bytes(command(['docker','exec',args.postgres,'sh','-c','pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc']))
    (output/'market_review.sql').write_bytes(command(['docker','exec',args.mysql,'sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -u root --single-transaction --no-tablespaces --databases market_review']))
    task=state/'parsing/tasks.sqlite3';snapshot=output/'tasks.sqlite3'
    source=sqlite3.connect(task.as_uri()+'?mode=ro',uri=True);target=sqlite3.connect(snapshot)
    try:source.backup(target)
    finally:source.close();target.close()
    with tarfile.open(output/'state-and-runtime.tar.gz','w:gz',dereference=False) as archive:
        for path in sorted(state.rglob('*')):
            relative=path.relative_to(state)
            if path==task or path.name in ('tasks.sqlite3-wal','tasks.sqlite3-shm','tasks.sqlite3-journal'):continue
            archive.add(path,arcname='state/'+relative.as_posix(),recursive=False)
        archive.add(snapshot,arcname='state/parsing/tasks.sqlite3')
        archive.add(runtime,arcname='private/runtime.json')
    manifest={'app_container':app['Id'],'app_image':app['Image'],'created_utc':datetime.now(timezone.utc).isoformat(),'files':{}}
    for path in output.iterdir():
        if path.is_file():manifest['files'][path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'backup_directory':str(output.relative_to(ROOT)),'files':{k:v['bytes'] for k,v in manifest['files'].items()}}))

if __name__=='__main__':main()
