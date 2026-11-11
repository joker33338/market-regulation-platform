"""获明确授权后，在候选镜像内执行唯一公开合成auto场景；不连接数据库。"""
import argparse
import asyncio
from collections import Counter
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import time

SHA = '4722ea9314889ce3e0607b1818e326f0531ee92e75e9ec38d7b42c8aa849370e'


async def execute(state, private):
    sys.path.insert(0, '/app')
    import httpx
    from qa_core.document_parsing.config import ParsingConfig
    from qa_core.document_parsing.document_router import DocumentParser
    from qa_core.document_parsing.runtime import PaddleRuntime
    from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter
    from qa_core.document_parsing.mineru_config import MinerUConfig
    from qa_core.document_parsing.mineru_official import OfficialMinerUClient
    from qa_core.document_parsing.mineru_service import MinerUService
    from qa_core.document_parsing.mineru_repository import TaskRepository
    from qa_core.document_parsing.mineru_client import MinerUError
    from qa_core.document_parsing.test_batch_authorization import atomic_json
    import qa_core
    assert Path(qa_core.__file__).is_relative_to('/app/qa_core')
    plan = json.loads((state/'approved-plan.json').read_text('utf-8'))
    assert plan['cloud_authorization'] == 'USER_APPROVED_6_HTTP_CURRENT_CHAT'
    assert plan['sha256'] == SHA and plan['max_additional_http'] == 6
    source = state/'synthetic-auto-final.png'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SHA
    ledger = state/'finite-http-ledger.json'
    if ledger.exists():
        raise RuntimeError('本批次已启动，禁止重放或清空计数；读取既有证据')
    atomic_json(ledger, [])
    successes = []

    class RealRuntime(PaddleRuntime):
        def predict(self, method, path):
            value = super().predict(method, path)
            raw = value['raw'].get('res', value['raw'])
            if method == 'ocr' and any(str(x).strip() for x in raw.get('rec_texts', [])):
                successes.append(dict(method=method, nonempty_text=True))
                atomic_json(state/'local-inference-success.json', successes)
            return value

    class BudgetTransport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.inner = httpx.AsyncHTTPTransport(retries=0)

        async def handle_async_request(self, request):
            if not successes:
                raise MinerUError('qa_real_local_success_required', 409)
            events = json.loads(ledger.read_text('utf-8'))
            counts = Counter(x['method'] for x in events)
            method = request.method
            if len(events) >= 6 or method not in {'POST','PUT','GET'} or counts[method] >= {'POST':1,'PUT':1,'GET':4}[method]:
                raise MinerUError('qa_approved_budget_exhausted', 429)
            item = dict(method=method, host=request.url.host, response_status=None, outcome='attempt_reserved')
            events.append(item)
            atomic_json(ledger, events)  # 请求发送前持久化占位，不回退未知结果。
            try:
                response = await self.inner.handle_async_request(request)
                item.update(response_status=response.status_code, outcome='response_received')
                atomic_json(ledger, events)
                return response
            except Exception as exc:
                item.update(outcome='unknown', error_type=type(exc).__name__)
                atomic_json(ledger, events)
                raise

        async def aclose(self):
            await self.inner.aclose()

    key = json.loads(private.read_text('utf-8-sig'))['MINERU_API_KEY']
    remote = MinerUConfig(enabled=True, mode='remote', provider='official', api_url='https://mineru.net/api',
                         api_key=key, result_dir=state/'remote', connect_timeout=5, request_timeout=30,
                         poll_interval=15, max_polls=3, max_upload_retries=0, max_download_retries=0)
    config = ParsingConfig(model_root=Path('/models/ocr'), enable_tables=False, cpu_threads=2, worker_timeout=90)
    config.validate_models('ocr')
    owner = 'qa-finite-public'
    grants = {owner:{SHA:dict(authorization_id='user-approved-six-http-20261111', expires_at=time.time()+1800)}}
    router = DualEngineRouter(DualEngineConfig(enabled=True, cloud_enabled=True, max_cloud_calls=6,
                             max_task_calls=6, min_request_interval=1), remote, grants=grants,
                             parser_factory=lambda:DocumentParser(config, runtime=RealRuntime(config)),
                             client_factory=lambda c:OfficialMinerUClient(c, transport=BudgetTransport()))
    local = replace(remote, mode='local', provider='self_hosted', api_url='', result_dir=state/'tasks')
    repo = TaskRepository(state/'tasks.sqlite3')
    service = MinerUService(local, repo, dual_router=router)
    options = dict(strategy='auto', allow_cloud_fallback=True, sensitive=False)
    files = [(source.name, source, 'SYN-AUTO-FINAL-01')]
    task, created = await service.submit(owner, 'finite-auto-one', files, parse_options=options)
    assert created
    await service.run(task['id'])
    task = repo.get(task['id'], owner)
    file = task['files'][0]
    result_path = Path(file['local_result_path'])/'normalized.json' if file.get('local_result_path') else None
    result = json.loads(result_path.read_text('utf-8')) if result_path and result_path.exists() else {}
    trace = result.get('quality', {}).get('routing_trace', {})
    candidates = trace.get('raw_results', {})
    def valid(candidate):
        return bool(candidate.get('pages')) and any(p.get('raw_text','').strip() for p in candidate['pages'])
    checks = dict(real_local_success=bool(successes), task_completed=task['status']=='completed',
                  real_local_candidate=valid(candidates.get('local',{})),
                  real_remote_candidate=valid(candidates.get('remote',{})),
                  current_quality_trigger=bool(trace.get('fallback_reason')),
                  official_selected=trace.get('selected_engine')==['mineru_official'],
                  requires_review=result.get('requires_review') is True,
                  source_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==SHA,
                  local_source_link=candidates.get('local',{}).get('source_location',{}).get('source_file_id')=='SYN-AUTO-FINAL-01',
                  page_provenance=bool(trace.get('page_numbers')))
    before = len(json.loads(ledger.read_text('utf-8')))
    previous_inferences = len(successes)
    repeat, again = await service.submit(owner, 'finite-auto-one', files, parse_options=options)
    await service.run(repeat['id'])
    checks['idempotent'] = not again and repeat['id']==task['id'] and before==len(json.loads(ledger.read_text('utf-8'))) and len(successes)==previous_inferences
    atomic_json(state/'final-result.json', dict(source_commit=plan['source_commit'],
        status='PASS' if all(checks.values()) else 'BLOCKED', checks=checks, actual_http=before,
        task_status=task['status'], error=file.get('error'), route_reason=trace.get('route_reason'),
        fallback_reason=trace.get('fallback_reason'), failure_reason=trace.get('failure_reason'),
        business_import=str(qa_core.__file__), database_used=False, raw_trace_saved_in_normalized=True))
    print(json.dumps(dict(checks=checks, actual_http=before)))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-user-approved-six-http', action='store_true', required=True)
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True')
    raise SystemExit(asyncio.run(execute(Path('/state'), Path('/private/runtime.json'))))
