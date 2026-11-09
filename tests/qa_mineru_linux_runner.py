"""隔离Linux中的独立官方对照；复用真实解析器、授权器及持久预算。"""
import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
import logging
import os
from pathlib import Path
import ssl
import sys
import time
from urllib.parse import urlsplit

sys.path.insert(0, '/source')


def select_unreserved_rows(plan, only, usage):
    """仅选择批准计划的显式子集；已预留POST的任务永久拒绝再次提交。"""
    rows = plan['selected']
    ids = [row['sample_id'] for row in rows]
    chosen = ids if only is None else list(only)
    if not chosen or len(set(chosen)) != len(chosen) or not set(chosen) <= set(ids):
        raise ValueError('执行子集不在批准计划内或重复')
    if usage:
        if usage.get('owner') != plan['owner'] or usage.get('batch_id') != plan['batch_id']:
            raise ValueError('原账本身份不匹配')
        if type(usage.get('calls')) is not int or not 0 <= usage['calls'] <= 32:
            raise ValueError('原账本调用数无效')
        if not set(usage.get('files', [])) <= {row['sha256'] for row in rows}:
            raise ValueError('原账本文件超出批准范围')
    submissions = usage.get('submissions', {})
    selected = [row for row in rows if row['sample_id'] in chosen]
    if any(submissions.get(row['sha256']+':remote') for row in selected):
        raise ValueError('已有POST预留，禁止重新提交')
    return selected


def kernel_guard(path, gateway):
    if os.name != 'posix' or os.geteuid() == 0:
        raise ValueError('必须Linux非root')
    status = Path('/proc/self/status').read_text()
    fields = dict(line.split(':',1) for line in status.splitlines() if ':' in line)
    if fields['NoNewPrivs'].strip() != '1' or any(int(fields[name].strip(),16) for name in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')):
        raise ValueError('运行期capabilities必须为零')
    stat = path.stat()
    if stat.st_uid != 0 or stat.st_mode & 0o022:
        raise ValueError('内核证明权限不符合要求')
    record = json.loads(path.read_text('utf-8'))
    if (record.get('network_namespace') != os.readlink('/proc/self/ns/net') or
            record.get('ipv4_default_drop') is not True or record.get('ipv6_default_drop') is not True or
            record.get('dns_after_init') is not False or record.get('allowed_addresses') != [gateway] or
            record.get('allowed_new_tcp_ports') != [8080]):
        raise ValueError('客户端内核隔离证明不匹配')


async def run(args, control):
    kernel_guard(args.attestation, args.gateway_ip)
    os.environ.update(OCR_MODEL_ROOT='/no-models', OCR_ENABLE_TABLES='1',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True')
    # 禁止本次纯云环境导入模型包；网络只可到固定代理，内核还需独立实测。
    def audit(event, values):
        if event == 'import' and str(values[0]).split('.')[0] in {'paddle','paddleocr','paddlex','sklearn'}:
            raise ImportError('独立云对照不加载本地模型包')
        if event in {'socket.getaddrinfo','socket.gethostbyname'} and str(values[0]) != args.gateway_ip:
            raise OSError('客户端禁止通用DNS')
        if event == 'socket.connect':
            target = values[1]
            if isinstance(target, tuple) and target[0] not in {'127.0.0.1','::1'} and target[:2] != (args.gateway_ip,8080):
                raise OSError('客户端仅允许指定代理')
    sys.addaudithook(audit)
    import httpx
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter
    from qa_core.document_parsing.mineru_config import MinerUConfig
    from qa_core.document_parsing.mineru_client import MinerUError
    from qa_core.document_parsing.mineru_official import OfficialMinerUClient
    from qa_core.document_parsing.mineru_service import MinerUService
    from qa_core.document_parsing.mineru_repository import TaskRepository
    from qa_core.document_parsing.test_batch_authorization import TrustedTestBatch, atomic_json
    from qa_core.utils import stable_hash
    metadata = json.loads(args.integrity.read_text('utf-8'))
    if metadata['source_commit'] != '67709c4989781594dd6c4723666fdb2c21caaa7b':
        raise ValueError('业务源码不是冻结版本')
    for name, expected in metadata['sha256'].items():
        path = Path('/source')/name
        if hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest() != expected:
            raise ValueError('业务源码完整性不符')
    plan = json.loads(args.plan.read_text('utf-8'))
    registration = json.loads(args.registration.read_text('utf-8'))
    if (registration.get('batch_id') != plan['batch_id'] or registration.get('owner') != plan['owner'] or
            registration.get('canonical_ledger_container_path') != str(args.ledger.resolve()) or
            registration.get('old_default_ledger_forbidden') is not True or
            registration.get('selected_sha256') != [row['sha256'] for row in plan['selected']]):
        raise ValueError('必须沿用已登记的唯一账本与批准范围')
    if len(plan['selected']) != 3 or sum(row['pages'] for row in plan['selected']) != 13:
        raise ValueError('首批范围不符')
    usage=json.loads(args.ledger.read_text('utf-8')) if args.ledger.exists() else {}
    selected=select_unreserved_rows(plan,args.only,usage)
    authority = TrustedTestBatch(args.manifest,owner=plan['owner'],batch_id=plan['batch_id'],
        usage_path=args.ledger,max_calls=32,max_files=3)
    checks=[]
    for row in plan['selected']:
        path=Path('/inputs')/(row['sample_id']+'.pdf')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('批准文件内容已变化')
        task=dict(owner=plan['owner'],parse_options=dict(allow_cloud_fallback=True,sensitive=False))
        authority.bind_task(task)
        allowed,reason=authority.authorize(task,dict(source_path=str(path),sha256=row['sha256']))
        checks.append(dict(sample_id=row['sample_id'],pages=row['pages'],eligible=allowed,reason=reason))
    if not all(row['eligible'] for row in checks):
        return dict(status='BLOCKED',checks=checks)
    if not args.execute:
        return dict(status='READY',execute=False,checks=checks,execution_subset=[row['sample_id'] for row in selected],
            preserved_call_reservations=usage.get('calls',0),real_http_requests=0,
            environment=dict(source_commit=metadata['source_commit'],python=sys.version,openssl=ssl.OPENSSL_VERSION,
                httpx=httpx.__version__,model_modules=[name for name in sys.modules if name.split('.')[0] in {'paddle','paddleocr','paddlex','sklearn'}]))
    token=control.get('api_key')
    if not isinstance(token,str) or not token:
        return dict(status='BLOCKED',reason='cloud_token_unconfigured')
    args.output.mkdir(parents=True,exist_ok=True)
    remote=MinerUConfig(enabled=True,mode='remote',provider='official',api_url='https://mineru.net/api',
        api_key=token,result_dir=args.output,poll_interval=10,max_polls=8)
    stop=dict(blocked=False)
    audit_path=args.output/'http-audit.jsonl'
    def client_factory(config):
        transport=httpx.AsyncHTTPTransport(proxy='http://'+args.gateway_ip+':8080',
            verify=ssl.create_default_context(),trust_env=False,retries=0)
        client=OfficialMinerUClient(config,transport=transport)
        original=client.request
        async def request(method,url,**kwargs):
            if stop['blocked']:
                raise MinerUError('qa_stopped_after_uncertain_post_or_429',409)
            event=dict(at=time.time(),method=method,origin=urlsplit(url).scheme+'://'+urlsplit(url).netloc)
            try:
                response=await original(method,url,**kwargs)
                event.update(status=response[0],outcome='RESPONSE')
                return response
            except Exception as exc:
                event.update(outcome='ERROR',exception_type=type(exc).__name__)
                if isinstance(exc,MinerUError):
                    event.update(status=exc.status,code=exc.code)
                    if exc.status==429 or exc.code in {'test_batch_budget_exhausted','cloud_call_budget_exhausted'}:
                        stop['blocked']=True
                if method=='POST' and isinstance(exc,(httpx.TransportError,TimeoutError)):
                    stop['blocked']=True
                raise
            finally:
                with audit_path.open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(event)+'\n')
                print('QA_HTTP '+json.dumps(event),flush=True)
        client.request=request
        return client
    policy=DualEngineConfig(enabled=True,cloud_enabled=True,environment='test',authorization_mode='TEST_BATCH',
        max_cloud_calls=8,max_task_calls=32,max_cloud_files=2,max_cloud_pages=50)
    router=DualEngineRouter(policy,remote,batch_authorizer=authority,client_factory=client_factory)
    service=MinerUService(replace(remote,mode='local',provider='self_hosted',api_url=''),
        TaskRepository(args.output/'tasks.sqlite3'),dual_router=router)
    previous_path=args.output/'execution.json'
    outcomes=json.loads(previous_path.read_text('utf-8')).get('outcomes',[]) if previous_path.exists() else []
    for row in plan['selected']:
        if row not in selected:
            print('QA_SKIP '+json.dumps(dict(sample_id=row['sample_id'],status='SKIPPED_RESERVED_NO_REPLAY',
                previous_post_reserved=bool(usage.get('submissions',{}).get(row['sha256']+':remote')))),flush=True)
    for row in selected:
        path=Path('/inputs')/(row['sample_id']+'.pdf')
        key=stable_hash('TEST_BATCH',plan['owner'],plan['batch_id'],row['sha256'],'remote')
        task,created=await service.submit(plan['owner'],key,[(authority.remote_name(dict(source_path=str(path),sha256=row['sha256'])),path)],
            parse_options=dict(strategy='remote',allow_cloud_fallback=True,sensitive=False))
        if created:
            await service.run(task['id'])
        task=service.repository.get(task['id'],plan['owner'])
        file=task['files'][0]
        trace={}
        if file.get('local_result_path'):
            trace=json.loads((Path(file['local_result_path'])/'normalized.json').read_text('utf-8')).get('quality',{}).get('routing_trace',{})
        result=dict(sample_id=row['sample_id'],strategy='remote',task_id=task['id'],task_status=task['status'],
            selected_engine=trace.get('selected_engine'),failure_reason=trace.get('failure_reason'),
            reused=not created,cloud_calls=trace.get('usage',{}).get('calls',0),local_environment='MODELS_NOT_MOUNTED',
            local_engine_status='BLOCKED',dual_engine_status='BLOCKED')
        outcomes.append(result)
        atomic_json(args.output/'execution.json',dict(source_commit=metadata['source_commit'],outcomes=outcomes))
        print('QA_TASK '+json.dumps(result),flush=True)
        if task['status']!='completed' or trace.get('failure_reason') or stop['blocked']:
            return dict(status='BLOCKED',outcomes=outcomes)
    return dict(status='COMPLETED_REMOTE_SUBSET' if args.only is not None else 'COMPLETED_REMOTE_ONLY',
        execution_subset=[row['sample_id'] for row in selected],outcomes=outcomes,dual_engine_status='BLOCKED',
        previous_task_failures_preserved=sum(row.get('task_status')!='completed' for row in outcomes))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('attestation','integrity','plan','manifest','ledger','output','registration'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--gateway-ip',required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--only',nargs='+',help='仅执行已批准计划内且未有POST预留的样本ID')
    args=parser.parse_args(argv)
    try:
        # 权限与当前命名空间证明核验之后才读取stdin机密，不放入Docker环境。
        kernel_guard(args.attestation,args.gateway_ip)
        control=json.loads(sys.stdin.read()) if args.execute else {}
        result=asyncio.run(run(args,control))
        print(json.dumps(result),flush=True)
        return 0 if result['status'] in {'READY','COMPLETED_REMOTE_ONLY','COMPLETED_REMOTE_SUBSET'} else 2
    except Exception as exc:
        print(json.dumps(dict(status='BLOCKED',exception_type=type(exc).__name__)),flush=True)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
