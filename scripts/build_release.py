"""从已提交源码构建同源Vue/FastAPI镜像；不复制runtime或真实数据。"""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]

def run(args,**kwargs):
    """执行既有构建步骤，失败立即停止，不自动安装或升级依赖。"""
    return subprocess.run(args,check=True,**kwargs)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--revision',default='HEAD')
    parser.add_argument('--base-image',default='market-regulation-runtime:v0.2.3-py312')
    parser.add_argument('--tag')
    parser.add_argument('--node',default=os.getenv('NODE_BINARY') or shutil.which('node'))
    args=parser.parse_args()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip():
        raise SystemExit('工作区未提交，停止构建')
    revision=subprocess.check_output(['git','rev-parse',args.revision+'^{commit}'],cwd=ROOT).decode().strip()
    if not args.node:raise SystemExit('需要已有Node解释器，不自动安装依赖')
    output=ROOT/'local'/'release-build'/(revision[:12]+'-'+uuid4().hex[:8]);output.mkdir(parents=True)
    context=output/'context';context.mkdir()
    paths=['qa_core','deploy/release','scripts/provision_auth_accounts.py','scripts/sql','requirements.txt','requirements-review.txt','frontend']
    archive=subprocess.check_output(['git','archive','--format=tar',revision,*paths],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:source.extractall(context,filter='data')
    work=context/'frontend';dependencies=ROOT/'frontend'/'node_modules'
    if not dependencies.is_dir():raise SystemExit('请先按锁文件准备前端依赖')
    for tool,options in [('typescript/bin/tsc',['--noEmit']),('vite/bin/vite.js',['build'])]:
        with (output/('frontend-'+tool.split('/')[0]+'.log')).open('wb') as log:
            # 仅链接已安装依赖，不复制其他工作区产物。
            if not (work/'node_modules').exists():
                if os.name=='nt':run(['powershell','-NoProfile','-Command','New-Item -ItemType Junction -Path "'+str(work/'node_modules')+'" -Target "'+str(dependencies)+'" | Out-Null'])
                else:(work/'node_modules').symlink_to(dependencies,target_is_directory=True)
            run([args.node,str(dependencies/tool),*options],cwd=work,stdout=log,stderr=subprocess.STDOUT)
    tag=args.tag or 'market-regulation-workbench:sha-'+revision
    old=subprocess.run(['docker','image','inspect',tag],capture_output=True)
    if old.returncode==0:
        existing=json.loads(old.stdout)[0]
        if existing['Config']['Labels'].get('org.opencontainers.image.revision')!=revision:
            raise SystemExit('目标镜像标签已存在且源码不同，拒绝覆盖')
    with (output/'build.log').open('wb') as log:
        run(['docker','build','--network=none','-f',str(context/'deploy/release/Dockerfile'),
             '--build-arg','LOCAL_BASE_IMAGE='+args.base_image,'--build-arg','SOURCE_COMMIT='+revision,
             '--build-arg','FRONTEND_COMMIT='+revision,'-t',tag,str(context)],stdout=log,stderr=subprocess.STDOUT)
    image=json.loads(subprocess.check_output(['docker','image','inspect',tag]))[0]
    assert image['Config']['Labels']['org.opencontainers.image.revision']==revision
    info={'source_sha':revision,'frontend_sha':revision,'tag':tag,'image_id':image['Id'],'created':image['Created'],'output':str(output)}
    (output/'identity.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(info,ensure_ascii=False))

if __name__=='__main__':main()
