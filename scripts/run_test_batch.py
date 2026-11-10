"""受限测试批次入口：默认仅预检，明确execute才调用既有官方链路。"""
import argparse
import asyncio
from dataclasses import replace
import json
import logging
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qa_core.utils import file_sha256, stable_hash
from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService
from qa_core.document_parsing.test_batch_authorization import TrustedTestBatch, atomic_json


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--usage-path', type=Path, help='复用已登记的原始调用账本；不得用新账本重置预算')
    p.add_argument('--owner', required=True)
    p.add_argument('--batch-id', required=True)
    p.add_argument('--input', type=Path, nargs='+', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--strategy', choices=('auto', 'remote'), nargs='+', default=['auto', 'remote'])
    p.add_argument('--execute', action='store_true', help='需协调器明确放行，仅在test环境生效')
    p.add_argument('--generate-candidates', action='store_true', help='仅生成未知资格清单，绝不自动批准')
    return p


async def run(args):
    if not 1 <= len(args.input) <= 3:
        raise ValueError('首批仅允许1至3个顺序文件')
    if os.getenv('DUAL_OCR_ENVIRONMENT') != 'test' or os.getenv('DUAL_OCR_AUTHORIZATION_MODE') != 'TEST_BATCH':
        raise ValueError('须明确设置test环境与TEST_BATCH授权模式')
    if not args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1] / 'local'):
        raise ValueError('输出必须位于当前工作树忽略的local目录')
    args.output.mkdir(parents=True, exist_ok=True)
    sources = [(p.resolve(), file_sha256(p)) for p in args.input]
    if len({sha for _, sha in sources}) != len(sources):
        raise ValueError('首批输入存在重复内容，请按唯一SHA选择样本')
    if args.generate_candidates:
        if args.execute or args.manifest.exists() or not args.manifest.resolve().is_relative_to(args.output.resolve()):
            raise ValueError('候选生成不能执行或覆盖已有清单')
        value = dict(version=1, owner=args.owner, batch_id=args.batch_id, expires_at=time.time()+3600,
                     revoked=False, entries=[dict(sha256=sha, source_qualified=False,
                     sensitivity_confirmed=False, sensitive='UNKNOWN', third_party_transfer_rights_confirmed=False,
                     source_evidence='') for _, sha in sources])
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(args.manifest, value)
        return dict(status='BLOCKED', reason='候选资格未知，须可信操作方确认；未执行HTTP')
    authority = TrustedTestBatch(args.manifest, owner=args.owner, batch_id=args.batch_id,
                                 usage_path=args.usage_path)
    preflight = []
    for source, sha in sources:
        task = dict(owner=args.owner, parse_options=dict(allow_cloud_fallback=True, sensitive=False))
        authority.bind_task(task)
        allowed, reason = authority.authorize(task, dict(source_path=str(source), sha256=sha))
        if source.suffix.lower() == '.docx':
            allowed, reason = False, 'cloud_page_count_unknown'
        preflight.append(dict(sample_id='sample-'+sha[:16], eligible=allowed, reason=reason))
    plan = dict(status='READY' if all(item['eligible'] for item in preflight) else 'BLOCKED',
                execute=args.execute, files=preflight, max_calls=32, max_files=3)
    atomic_json(args.output/'preflight.json', plan)
    if not args.execute or plan['status'] != 'READY':
        return plan
    # 使用现有调用预算与较长轮询间隔，不扩大请求次数或绕过域名检查。
    config = MinerUConfig.from_env()
    remote = replace(config, enabled=True, mode='remote', provider='official', api_url='https://mineru.net/api',
                     result_dir=args.output, poll_interval=max(config.poll_interval, 10))
    if not remote.api_key:
        return dict(status='BLOCKED', reason='cloud_token_unconfigured')
    policy = DualEngineConfig.from_env()
    if not policy.enabled or not policy.cloud_enabled:
        return dict(status='BLOCKED', reason='dual_engine_cloud_not_enabled')
    router = DualEngineRouter(policy, remote, batch_authorizer=authority)
    local = replace(remote, mode='local', provider='self_hosted', api_url='')
    service = MinerUService(local, TaskRepository(args.output/'tasks.sqlite3'), dual_router=router)
    outcomes = []
    for source, sha in sources:
        for strategy in dict.fromkeys(args.strategy):
            key = stable_hash('TEST_BATCH', args.owner, args.batch_id, sha, strategy)
            name = authority.remote_name(dict(source_path=str(source), sha256=sha))
            task, created = await service.submit(args.owner, key, [(name, source)],
                parse_options=dict(strategy=strategy, allow_cloud_fallback=True, sensitive=False))
            if created:
                await service.run(task['id'])
            # 恢复入口不盲目重新提交未完成或结果不确定的任务。
            task = service.repository.get(task['id'], args.owner)
            file = task['files'][0]
            trace = {}
            if file.get('local_result_path'):
                normalized = json.loads((Path(file['local_result_path'])/'normalized.json').read_text('utf-8'))
                trace = normalized.get('quality', {}).get('routing_trace', {})
            outcome = dict(sample_id='sample-'+sha[:16], strategy=strategy, task_id=task['id'],
                           status=task['status'], failure_reason=trace.get('failure_reason'),
                           selected_engine=trace.get('selected_engine'), reused=not created)
            outcomes.append(outcome)
            atomic_json(args.output/'execution.json', dict(outcomes=outcomes))
            if task['status'] != 'completed' or trace.get('failure_reason'):
                return dict(status='BLOCKED', outcomes=outcomes)
    return dict(status='COMPLETED', outcomes=outcomes)


def main(argv=None):
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    args = parser().parse_args(argv)
    try:
        result = asyncio.run(run(args))
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['status'] in {'READY', 'COMPLETED'} else 2
    except Exception as exc:
        # 异常可能含真实文件名或URL，仅输出类型，不输出敏感原文。
        print(json.dumps(dict(status='BLOCKED', error_type=type(exc).__name__), ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
