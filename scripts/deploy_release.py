"""受控本地更新：零活动任务、持久化挂载保留、健康失败自动回滚。"""
import argparse
from contextlib import closing
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
NAME='market-regulation-app-1'


def command(*args):
    """执行 Docker 操作并捕获输出；失败使用固定提示，避免泄露私密配置。"""
    result=subprocess.run(['docker',*args],capture_output=True)
    if result.returncode:raise RuntimeError('Docker操作失败；未输出私密配置')
    return result.stdout


def inspect(name):
    """读取本机容器或镜像配置，调用方只展示筛选后的身份信息。"""
    return json.loads(command('inspect',name))[0]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--image',required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--runtime',type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--rollback',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',args.revision):raise ValueError('revision必须为完整SHA')
    old=inspect(NAME);image=json.loads(command('image','inspect',args.image))[0]
    labels=image['Config'].get('Labels') or {}
    if labels.get('org.opencontainers.image.revision')!=args.revision:raise RuntimeError('镜像与目标源码不符')
    if not args.rollback and labels.get('cn.market-regulation.frontend.revision')!=args.revision:raise RuntimeError('前后端不同源')
    mounts={m['Destination']:m for m in old['Mounts']}
    if not {'/state','/models','/private/runtime.json','/app/reports'}<=mounts.keys():raise RuntimeError('持久化挂载不完整')
    if any(m['Type']!='bind' for m in mounts.values()):raise RuntimeError('需要人工核对非bind挂载')
    current_runtime=Path(mounts['/private/runtime.json']['Source'])
    runtime=(args.runtime or current_runtime).resolve(strict=True)
    if subprocess.run(['git','check-ignore','--quiet','--',str(runtime)],cwd=ROOT,capture_output=True).returncode!=0:raise RuntimeError('runtime必须位于Git忽略的私密目录')
    previous=json.loads(current_runtime.read_text(encoding='utf-8-sig'));target=json.loads(runtime.read_text(encoding='utf-8-sig'))
    for key in ('PARSING_API_TOKENS_JSON','AUTH_ACCOUNTS_FILE','REVIEW_MYSQL_CONFIG_JSON','MINERU_API_KEY'):
        if previous.get(key)!=target.get(key):raise RuntimeError('认证/审核/MinerU配置变化不在本次切换范围')
    networks=list(old['NetworkSettings']['Networks'])
    if len(networks)!=1:raise RuntimeError('网络拓扑需要人工核对')
    state=Path(mounts['/state']['Source']);task_file=state/'parsing/tasks.sqlite3'
    with closing(sqlite3.connect(task_file.as_uri()+'?mode=ro',uri=True)) as c:
        if c.execute("SELECT count(*) FROM parse_tasks WHERE status NOT IN ('completed','failed','partial','canceled','timed_out')").fetchone()[0]:raise RuntimeError('存在活动任务，拒绝切换')
    if not args.apply:
        print(json.dumps({'preflight':True,'target_revision':args.revision,'image_id':image['Id'],'active_tasks':0,'runtime_changed':runtime!=current_runtime.resolve(),'applied':False}));return
    output=ROOT/'local/release-switch'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');output.mkdir(parents=True)
    (output/'before-container.private.json').write_text(json.dumps(old),encoding='utf-8')
    backup=NAME+'-pre-v023-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stopped=False;renamed=False;created=False;connection=sqlite3.connect(task_file,timeout=5)
    try:
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute("SELECT count(*) FROM parse_tasks WHERE status NOT IN ('completed','failed','partial','canceled','timed_out')").fetchone()[0]:raise RuntimeError('检查后出现活动任务')
        if inspect(NAME)['Id']!=old['Id']:raise RuntimeError('运行容器已变化')
        command('stop','--time','60',NAME);stopped=True
        command('rename',NAME,backup);renamed=True
        connection.rollback();connection.close();connection=None
        run=['run','-d','--name',NAME,'--restart','unless-stopped','--init','--network',networks[0],'--network-alias','app','-p','127.0.0.1:8180:8180','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--label','cn.market-regulation.deployment.status=V023_LOCAL_RELEASE']
        run+=['--health-cmd',"python -B -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8180/', timeout=5).close()\"",'--health-interval','15s','--health-timeout','6s','--health-start-period','20s','--health-retries','4']
        for key,value in (old['HostConfig'].get('Tmpfs') or {'/tmp':'rw,nosuid,size=1g,mode=1777'}).items():run+=['--tmpfs',key+':'+value]
        for key,value in (old['Config'].get('Labels') or {}).items():
            if key in ('com.docker.compose.project','com.docker.compose.service'):run+=['--label',key+'='+value]
        for destination,m in mounts.items():
            source=str(runtime) if destination=='/private/runtime.json' else m['Source']
            run+=['--mount','type=bind,source='+source+',target='+destination+(',readonly' if not m['RW'] else '')]
        run+=[image['Id']];command(*run);created=True
        for _ in range(90):
            live=inspect(NAME)
            if live['State']['Status']!='running':raise RuntimeError('目标容器退出')
            if live['State'].get('Health',{}).get('Status')=='healthy':break
            time.sleep(1)
        else:raise RuntimeError('目标容器健康超时')
        if live['Image']!=image['Id']:raise RuntimeError('运行镜像身份不符')
        receipt={'revision':args.revision,'image_id':image['Id'],'container_id':live['Id'],'health':'healthy','rollback_container':backup,'runtime_changed':runtime!=current_runtime.resolve()}
        (output/'result.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))
    except BaseException:
        if connection is not None:connection.rollback();connection.close()
        found=subprocess.run(['docker','inspect',NAME],capture_output=True)
        if renamed and found.returncode==0:
            candidate=json.loads(found.stdout)[0]
            if candidate['Image']==image['Id']:
                command('stop','--time','15',NAME);command('rename',NAME,backup+'-failed')
            else:raise RuntimeError('容器身份异常，保留现场') from None
        if renamed:command('rename',backup,NAME)
        if stopped:command('start',NAME)
        raise


if __name__=='__main__':main()
