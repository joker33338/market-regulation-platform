"""Quality-guided local parsing with explicitly authorized official-cloud fallback.

Candidates are durable before selection. The existing sink receives only the final
immutable result; remote subtasks reuse the existing resumable MinerU lifecycle.
"""
import asyncio
from dataclasses import dataclass, field, replace
import json
import math
import os
from pathlib import Path
import tempfile
import time

from qa_core.utils import file_sha256
from .document_router import DocumentParser
from .mineru_client import MinerUError
from .mineru_official import OfficialMinerUClient
from .mineru_repository import TaskRepository
from .quality import RoutingThresholds, assess_document
from .schemas import DocumentResult


def persist_result(path, result):
    """Crash-safe checkpoint; only generated files in the task output directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.candidate-', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(result.to_json().encode('utf-8'))
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class DualEngineConfig:
    enabled: bool = False
    cloud_enabled: bool = False
    max_fallbacks: int = 1
    max_cloud_calls: int = 8
    max_task_calls: int = 32
    max_cloud_files: int = 2
    max_cloud_pages: int = 50
    min_request_interval: float = 0.25
    thresholds: RoutingThresholds = field(default_factory=RoutingThresholds)

    def __post_init__(self):
        if (self.max_fallbacks not in {0, 1} or min(self.max_cloud_calls, self.max_task_calls,
                self.max_cloud_files, self.max_cloud_pages) < 1 or self.min_request_interval < 0):
            raise ValueError("Invalid dual-engine budgets")

    @classmethod
    def from_env(cls):
        values = {name: int(os.environ['DUAL_OCR_' + name.upper()]) for name in
                  ('max_fallbacks', 'max_cloud_calls', 'max_task_calls', 'max_cloud_files', 'max_cloud_pages')
                  if 'DUAL_OCR_' + name.upper() in os.environ}
        return cls(enabled=os.getenv('DUAL_OCR_ENABLED', '0') == '1',
                   cloud_enabled=os.getenv('DUAL_OCR_CLOUD_ENABLED', '0') == '1',
                   thresholds=RoutingThresholds(
                       low_confidence=float(os.getenv('DUAL_OCR_LOW_CONFIDENCE', '0.8')),
                       min_page_characters=int(os.getenv('DUAL_OCR_MIN_PAGE_CHARACTERS', '12')),
                       max_invalid_ratio=float(os.getenv('DUAL_OCR_MAX_INVALID_RATIO', '0.02'))), **values)


class DualEngineRouter:
    def __init__(self, config, remote_config, *, grants=None, parser_factory=DocumentParser,
                 client_factory=OfficialMinerUClient):
        self.config, self.remote_config = config, remote_config
        self.grants = grants if grants is not None else {}
        self.parser_factory, self.client_factory = parser_factory, client_factory
        self._rate_lock = asyncio.Lock()
        self._last_call = 0.0
        if remote_config.provider != 'official' or remote_config.mode != 'remote':
            raise ValueError('Dual-engine fallback requires the official v4 provider')

    def authorization(self, task, file):
        options = task.get('parse_options', {})
        # A browser flag, authentication token or API key never grants transfer.
        owner_grants = self.grants.get(task['owner'], {}) if isinstance(self.grants, dict) else {}
        grant = owner_grants.get(file['sha256'], {}) if isinstance(owner_grants, dict) else {}
        if not isinstance(grant, dict):
            return False, 'file_authorization_required'
        sensitive = options.get('sensitive', False) or grant.get('sensitive', False)
        corpus = os.getenv('MARKET_REGULATION_TEST_CORPUS')
        if corpus and Path(file['source_path']).resolve().is_relative_to(Path(corpus).resolve()):
            return False, 'corpus_transfer_denied'
        if not self.config.cloud_enabled or options.get('allow_cloud_fallback') is not True:
            return False, 'cloud_disabled_or_not_requested'
        if (not grant.get('authorization_id') or type(grant.get('expires_at')) not in {int, float}
                or not math.isfinite(grant['expires_at']) or grant['expires_at'] <= time.time()):
            return False, 'file_authorization_required'
        if sensitive and grant.get('allow_sensitive') is not True:
            return False, 'sensitive_transfer_denied'
        if not self.remote_config.api_key:
            return False, 'cloud_token_unconfigured'
        return True, grant['authorization_id']

    @staticmethod
    def engines(result):
        return sorted({('native' if page.parsing_method.startswith('native') else
                        {'ocr': 'paddle_ocr', 'structure': 'pp_structure', 'mineru': 'mineru_official'}.get(
                            page.parsing_method, page.parsing_method)) for page in result.pages})

    async def parse(self, task, file, save):
        directory = Path(task['result_root']) / task['id'] / file['id']
        directory.mkdir(parents=True, exist_ok=True)
        checkpoint = directory / 'local-candidate.json'
        if checkpoint.is_file():
            local = DocumentResult.from_dict(json.loads(checkpoint.read_text(encoding='utf-8')))
        else:
            def parse_local():
                with self.parser_factory() as parser:
                    try:
                        return parser.parse(file['source_path'])
                    except Exception as exc:
                        # Preserve the failure type, never confidential exception text.
                        return DocumentResult(file['sha256'], file['file_name'], Path(file['file_name']).suffix,
                                              {'file_path': file['source_path'], 'file_sha256': file['sha256']},
                                              parsing_status='failed', error_message=type(exc).__name__, requires_review=True)
            local = await asyncio.to_thread(parse_local)
            local.file_name = file['file_name']
            await asyncio.to_thread(persist_result, checkpoint, local)
        if local.document_id != file['sha256'] or await asyncio.to_thread(file_sha256, file['source_path']) != file['sha256']:
            raise MinerUError('source_integrity_mismatch', 409)
        local.source_location['source_file_id'] = file['source_file_id']
        local_quality = assess_document(local, thresholds=self.config.thresholds)
        state = file.setdefault('routing_state', {'calls': 0, 'submissions': 0, 'fallbacks': 0})
        await save(task)
        allowed, authorization = self.authorization(task, file)
        strategy = task.get('parse_options', {}).get('strategy', 'auto')
        candidate = strategy == 'remote' or (strategy == 'auto' and local_quality['routing']['fallback_recommended'])
        route = {'initial_engine': self.engines(local), 'selected_engine': self.engines(local),
                 'fallback_engine': None, 'fallback_reason': local_quality['routing']['reasons'],
                 'route_reason': 'local_quality_sufficient', 'cloud_transfer_authorized': allowed,
                 'authorization_id': authorization if allowed else None,
                 'input_sha256': file['sha256'], 'source_file_id': file['source_file_id'],
                 'local_quality': local_quality, 'remote_quality': None, 'remote_task_id': None,
                 'raw_results': {'local': local.to_dict()}, 'parser_versions': {},
                 'version_unavailable_reason': 'Candidates without parser_version did not report a verified version; model_version is not parser_version.',
                 'page_numbers': [page.page_number for page in local.pages],
                 'requires_review': local_quality['review_required']}
        for engine in self.engines(local):
            route['parser_versions'][engine] = None
        selected = local
        if candidate:
            route['route_reason'] = 'local_quality_requires_review'
            route['requires_review'] = True
            if not allowed:
                route['failure_reason'] = authorization
            elif not self.config.max_fallbacks:
                route['failure_reason'] = 'fallback_budget_exhausted'
            else:
                try:
                    route['fallback_engine'] = 'mineru_official'
                    remote = await self._remote(task, file, save)
                    route['remote_task_id'] = state.get('remote_task_id')
                    route['fallback_engine'] = 'mineru_official'
                    route['raw_results']['remote'] = remote.to_dict()
                    route['page_numbers'] = sorted(set(route['page_numbers']) | {page.page_number for page in remote.pages})
                    remote_quality = assess_document(remote, thresholds=self.config.thresholds)
                    route['remote_quality'] = remote_quality
                    route['parser_versions']['mineru_official'] = remote.source_location.get('parser_version')
                    if (remote.raw_text.strip() and remote.parsing_status not in {'failed', 'partial'} and
                            len(remote_quality['routing']['reasons']) <= len(local_quality['routing']['reasons'])):
                        selected = remote
                        route['selected_engine'] = ['mineru_official']
                        route['route_reason'] = 'authorized_cloud_quality_selection'
                    else:
                        route['failure_reason'] = 'remote_quality_insufficient'
                except Exception as exc:
                    route['failure_reason'] = exc.code if isinstance(exc, MinerUError) else type(exc).__name__
                    route['route_reason'] = 'cloud_failed_local_preserved'
        route['remote_task_id'] = state.get('remote_task_id')
        route['usage'] = {**state, 'estimated_cost': None, 'cost_unavailable_reason': 'Provider billing is not returned by the API.'}
        # Do not mutate either candidate when adding the final routing decision.
        result = DocumentResult.from_dict(selected.to_dict())
        result.quality.update(assess_document(result, thresholds=self.config.thresholds))
        result.quality['routing_trace'] = route
        result.requires_review = route['requires_review'] or bool(result.quality.get('review_required'))
        result.quality['review_required'] = result.requires_review
        result.source_location.update(input_sha256=file['sha256'], source_file_id=file['source_file_id'],
                                      selected_engine=route['selected_engine'], remote_task_id=route['remote_task_id'])
        if route.get('failure_reason') and result.parsing_status == 'success':
            result.parsing_status = 'needs_review'
        return result

    async def _remote(self, task, file, save):
        from .mineru_service import MinerUService
        state = file['routing_state']
        allowed, _ = self.authorization(task, file)
        if not allowed:
            raise MinerUError('file_authorization_required', 403)
        if not state.get('reserved_pages'):
            if Path(file['source_path']).suffix.lower() == '.pdf':
                import fitz
                with fitz.open(file['source_path']) as document:
                    pages = len(document)
            elif Path(file['source_path']).suffix.lower() == '.docx':
                # No reliable physical page count without rendering. Do not bypass page budgets.
                raise MinerUError('cloud_page_count_unknown', 409)
            else:
                pages = 1
            states = [item.get('routing_state', {}) for item in task['files']]
            if (sum(item.get('fallbacks', 0) for item in states) >= self.config.max_cloud_files or
                    sum(item.get('reserved_pages', 0) for item in states) + pages > self.config.max_cloud_pages):
                raise MinerUError('cloud_task_budget_exhausted', 429)
            state.update(reserved_pages=pages, fallbacks=1)
            await save(task)
        config = replace(self.remote_config, result_dir=Path(task['result_root']) / 'cloud',
                         max_polls=min(self.remote_config.max_polls, self.config.max_cloud_calls))
        client = self.client_factory(config)
        async def before_request(method, url):
            allowed, _ = self.authorization(task, file)
            if not allowed:
                raise MinerUError('file_authorization_revoked', 403)
            if await asyncio.to_thread(file_sha256, file['source_path']) != file['sha256']:
                raise MinerUError('source_integrity_mismatch', 409)
            total = sum(item.get('routing_state', {}).get('calls', 0) for item in task['files'])
            if state['calls'] >= self.config.max_cloud_calls or total >= self.config.max_task_calls:
                raise MinerUError('cloud_call_budget_exhausted', 429)
            if method == 'POST':
                if state['submissions']:
                    raise MinerUError('submission_outcome_unknown', 409)
                state['submissions'] += 1
            state['calls'] += 1
            await save(task)  # charge before sending, including uncertain outcomes
            if task.get('cancel_requested'):
                raise MinerUError('task_canceled', 409)
            async with self._rate_lock:
                await asyncio.sleep(max(0, self.config.min_request_interval - (time.monotonic() - self._last_call)))
                self._last_call = time.monotonic()
        client.before_request = before_request
        try:
            service = MinerUService(config, TaskRepository(config.result_dir / 'tasks.sqlite3'), client)
            child, _ = await service.submit(task['owner'], task['id'] + ':' + file['id'],
                                            [(file['file_name'], Path(file['source_path']), file['source_file_id'])])
            state['remote_task_id'] = child.get('remote_id')
            state['child_task_id'] = child['id']
            await save(task)
            if child['status'] == 'timed_out':
                await service.resume(child['id'], task['owner'])
            await service.run(child['id'])
            child = service.repository.get(child['id'], task['owner'])
            state['remote_task_id'] = child.get('remote_id')
            await save(task)
            remote_file = child['files'][0]
            if child['status'] != 'completed' or not remote_file.get('result_path'):
                error = remote_file.get('error') or child.get('error') or {'code': 'remote_parse_failed'}
                raise MinerUError(error['code'])
            payload = (Path(remote_file['result_path']) / 'normalized.json').read_text(encoding='utf-8')
            result = DocumentResult.from_dict(json.loads(payload))
            import httpx
            if isinstance(client.http._transport, httpx.MockTransport):
                result.quality['mock'] = True
            if result.document_id != file['sha256']:
                raise MinerUError('source_integrity_mismatch', 409)
            return result
        finally:
            await client.close()
