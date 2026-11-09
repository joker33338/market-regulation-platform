"""QA protocol adapter: exercise production routing; replace only OCR/HTTP inputs.

case_id is deliberately unused. Observations come from persisted production tasks,
candidate JSON, real sink queries and the existing review/ingestion/retrieval path.
"""
import asyncio
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time
import unittest
from uuid import uuid4

import httpx

from qa_core.document_parsing.config import ParsingConfig
from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_official import OfficialMinerUClient
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService
from qa_core.document_parsing.schemas import DocumentResult
from qa_core.storage.parsing_results import PostgresResultSink
from tests.test_document_parsing import FakeRuntime
from tests.test_mineru_official import official_bundle


class ScenarioRuntime(FakeRuntime):
    def __init__(self, options):
        super().__init__()
        self.options = options

    def predict(self, method, path):
        payload = super().predict(method, path)
        raw = payload['raw']['res']
        if method == 'ocr':
            text = self.options.get('local_text', '第一条 本地合成识别结果，金额100元。')
            raw.update(rec_texts=[text] if text else [],
                       rec_scores=[self.options.get('local_confidence', 0.99)] if text else [],
                       rec_polys=[[[1, 1], [200, 1], [200, 20], [1, 20]]] if text else [])
        return payload


class OfficialFixture:
    def __init__(self, failure=None):
        self.failure, self.calls, self.submissions = failure, [], 0
        self.manifest, self.uploaded = [], False

    def handle(self, request):
        self.calls.append((request.method, request.url.path))
        if request.method == 'POST':
            self.submissions += 1
            if self.failure == 'timeout':
                raise httpx.ReadTimeout('synthetic timeout', request=request)
            if self.failure in {'429', '500'}:
                return httpx.Response(int(self.failure))
            self.manifest = json.loads(request.content)['files']
            return httpx.Response(200, json={'code': 0, 'data': {'batch_id': 'synthetic-batch',
                'file_urls': ['https://mineru.oss-cn-shanghai.aliyuncs.com/input']}})
        if request.method == 'PUT':
            self.uploaded = True
            return httpx.Response(200)
        if request.url.host == 'cdn-mineru.openxlab.org.cn':
            return httpx.Response(200, content=official_bundle())
        return httpx.Response(200, json={'code': 0, 'data': {'batch_id': 'synthetic-batch', 'extract_result': [
            {'data_id': self.manifest[0]['data_id'], 'file_name': self.manifest[0]['name'],
             'state': 'done' if self.uploaded else 'waiting-file',
             'full_zip_url': 'https://cdn-mineru.openxlab.org.cn/result.zip'}]}})


def run_scenario(options, source):
    return asyncio.run(exercise(options, source))


async def exercise(options, source):
    source = Path(source)
    root = source.parent / uuid4().hex
    root.mkdir()
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    owner = 'synthetic-dual-qa'
    fixture = OfficialFixture(options.get('remote_failure'))
    remote = MinerUConfig(enabled=True, mode='remote', provider='official', api_url='https://mineru.net/api',
                          api_key='synthetic-token', result_dir=root, poll_interval=0, max_polls=3)
    policy = DualEngineConfig(enabled=True, cloud_enabled=True, min_request_interval=0,
                             max_cloud_calls=options.get('max_cloud_calls', 8))
    grants = {owner: {sha: {'authorization_id': 'synthetic-consent', 'expires_at': time.time() + 300}}} if options.get('authorized_cloud') else {}
    runtime = ScenarioRuntime(options)
    router = DualEngineRouter(policy, remote, grants=grants,
        parser_factory=lambda: DocumentParser(ParsingConfig(enable_tables=True), runtime=runtime),
        client_factory=lambda config: OfficialMinerUClient(config, transport=httpx.MockTransport(fixture.handle)))
    config = replace(remote, mode='local', provider='self_hosted', api_url='')
    sink, counts, sentinel, dsn = None, {}, None, None
    if options.get('inject_database_failure'):
        dsn = os.getenv('QA_ISOLATED_PG_DSN')
        if not dsn:
            raise unittest.SkipTest('DE-I requires QA_ISOLATED_PG_DSN in a dedicated test database')
        sink = PostgresResultSink(dsn)
        sentinel = sink.save({'id': uuid4().hex, 'owner': owner}, {'id': uuid4().hex},
                             DocumentResult(sha, source.name, source.suffix, {}))

        class CommittedThenInterrupted:
            failed = False

            def save(self, task, file, result):
                value = sink.save(task, file, result)
                if not self.failed:
                    self.failed = True
                    raise ConnectionError('synthetic loss after database commit')
                return value
        result_sink = CommittedThenInterrupted()
    else:
        result_sink = None
    service = MinerUService(config, TaskRepository(root / 'tasks.sqlite3'), result_sink=result_sink, dual_router=router)
    inputs = [(source.name, source, 'synthetic-source-id')]
    parse_options = {'allow_cloud_fallback': bool(options.get('authorized_cloud')), 'sensitive': bool(options.get('sensitive'))}
    task, _ = await service.submit(owner, 'qa-synthetic', inputs, parse_options=parse_options)
    await service.run(task['id'])
    task = service.repository.get(task['id'])
    if dsn:
        import psycopg2
        def rows():
            connection = psycopg2.connect(dsn)
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT parse_id, report_sha256 FROM document_review.documents WHERE source_location->>\'local_task_id\'=%s OR parse_id=%s ORDER BY parse_id', (task['id'], sentinel))
                    return cursor.fetchall()
            finally:
                connection.close()
        first = rows()
        await service.resume(task['id'], owner)
        await service.run(task['id'])
        repeated, created = await service.submit(owner, 'qa-synthetic', inputs, parse_options=parse_options)
        assert not created and repeated['id'] == task['id']
        await service.run(repeated['id'])
        after = rows()
        counts = {'database_backend': 'isolated_postgres', 'rows_after_first': len(first),
                  'rows_after_repeat': len(after), 'prior_record_preserved': first == after}
        task = service.repository.get(task['id'])
    file = task['files'][0]
    directory = root / task['id'] / file['id']
    local = json.loads((directory / 'local-candidate.json').read_text(encoding='utf-8'))
    final = DocumentResult.from_dict(json.loads((directory / 'normalized.json').read_text(encoding='utf-8')))
    trace = final.quality['routing_trace']
    engines = set(trace['initial_engine'])
    if trace['raw_results'].get('remote'):
        engines.add('mineru_official')
    observed = {'source_sha256': final.document_id, 'engines': sorted(engines),
        'cloud_calls': len(fixture.calls), 'cloud_submissions': fixture.submissions,
        'complex_layout_detected': any(page.source_location.get('complex_layout') for page in final.pages),
        'layout_preserved': any(page.layout_blocks or page.tables for page in final.pages),
        'route_reason': trace['route_reason'], 'warnings': trace['local_quality']['findings'],
        'local_result_preserved': local['raw_text'] == trace['raw_results']['local']['raw_text'],
        'original_text_preserved': final.raw_text == local['raw_text'], 'review_required': final.requires_review,
        'failure_reason': trace.get('failure_reason'),
        'provenance': {'route_reason': trace['route_reason'], 'quality': trace['local_quality'],
                       'raw_results': trace['raw_results'], 'page_numbers': trace['page_numbers'],
                       'source_file_id': trace['source_file_id'], 'parser_versions': trace['parser_versions'],
                       'version_unavailable_reason': trace['version_unavailable_reason']}, **counts}
    if options.get('review_approved'):
        from qa_core.config.settings import Settings
        from qa_core.document_parsing.mineru_artifacts import reviewed_legal_document
        from qa_core.indexing.service import ingest_documents
        from qa_core.retrieval.models import DemoEmbeddings
        from qa_core.retrieval.store import retrieve
        from qa_core.storage.database import Database
        database = Database(sqlite_path=root / 'reviewed-kb.sqlite3')
        try:
            database.initialize()
            observed['ingestions_before_review'] = database.one('SELECT COUNT(*) AS n FROM law_chunks')['n']
            with unittest.TestCase().assertRaises(ValueError):
                reviewed_legal_document(final, reviewer='', law_name='合成法规')
            legal = reviewed_legal_document(final, reviewer='synthetic-reviewer', law_name='合成法规')
            embed = DemoEmbeddings()
            ingest_documents([legal], database=database, embeddings=embed,
                             settings=Settings(embedding_backend='demo', embedding_dimension=embed.dimension), version='synthetic-v1')
            database.publish('synthetic-v1')
            hits = retrieve(database, embed, '合成验收材料')
            observed.update(hits_after_review=len(hits), source_association_preserved=bool(hits) and
                            all(hit['source_path'] == str(source.resolve()) for hit in hits) and
                            legal.metadata['file_sha256'] == sha)
        finally:
            database.close()
    return observed
