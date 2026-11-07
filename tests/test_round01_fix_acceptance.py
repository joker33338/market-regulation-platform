"""Independent QA regression against Fix, with synthetic local fixtures only.

At the original QA baseline these cases skip because the new modules are absent.
Use run_round01_validation.py --source <isolated-fix-checkout> to test Fix.
"""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


HAS_FIX = importlib.util.find_spec('qa_core.document_parsing.mineru_service') is not None


@unittest.skipUnless(HAS_FIX, 'Fix implementation required; run against recorded Fix checkout')
class Round01FixAcceptance(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from qa_core.document_parsing.mineru_config import MinerUConfig
        from qa_core.document_parsing.mineru_repository import TaskRepository
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = MinerUConfig(enabled=True, result_dir=self.root, poll_interval=0, max_polls=3)
        self.repository = TaskRepository(self.root / 'tasks.sqlite3')

    async def test_local_database_failure_remains_visible_on_error_api(self):
        from qa_core.document_parsing.mineru_api import public
        from qa_core.document_parsing.mineru_client import MinerUClient
        from qa_core.document_parsing.mineru_mock import mock_transport
        from qa_core.document_parsing.mineru_service import MinerUService

        class FailedSink:
            def save(self, task, file, result):
                raise RuntimeError('synthetic database failure')

        client = MinerUClient(self.config, transport=mock_transport())
        self.addAsyncCleanup(client.close)
        service = MinerUService(self.config, self.repository, client, result_sink=FailedSink())
        source = self.root / 'fixture.pdf'
        source.write_bytes(b'%PDF-1.7 synthetic')
        task, _ = await service.submit('qa-owner', 'failure-key', [('fixture.pdf', source)])
        await service.run(task['id'])
        stored = self.repository.get(task['id'])
        self.assertEqual(stored['status'], 'failed')
        self.assertEqual(stored['files'][0]['error'], {'code': 'RuntimeError'})
        # Both GET status and GET errors call this exact public serializer.
        self.assertEqual(public(stored)['files'][0]['error'], {'code': 'RuntimeError'})

    async def test_R01_004_case_variant_archive_cannot_replace_original_artifact(self):
        import os
        from qa_core.document_parsing.mineru_artifacts import store_artifacts
        from qa_core.document_parsing.mineru_client import MinerUError
        if os.name != 'nt':
            self.skipTest('Windows case-insensitive filesystem regression')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('markdown.md', 'synthetic')
            archive.writestr('structured_content.json', json.dumps({'pages': []}))
            archive.writestr('middle_json.json', '{}')
            archive.writestr('ARTIFACT.BIN', b'synthetic replacement')
        payload = buffer.getvalue()
        directory = self.root / 'output'
        try:
            store_artifacts(payload, directory, self.config)
        except MinerUError:
            return  # Controlled rejection is also acceptable.
        self.assertEqual((directory / 'artifact.bin').read_bytes(), payload,
                         'reserved raw artifact must retain original download bytes')

    async def test_R01_005_local_batch_bad_pdf_does_not_block_valid_sibling(self):
        from dataclasses import replace
        import fitz
        from qa_core.document_parsing.mineru_service import MinerUService
        bad, good = self.root / 'bad.pdf', self.root / 'good.pdf'
        bad.write_bytes(b'%PDF-1.7 broken synthetic container')
        with fitz.open() as pdf:
            page = pdf.new_page()
            page.insert_text((50, 50), 'Synthetic native PDF content for QA. No OCR required.')
            pdf.save(good)
        for key, inputs in [('bad-first', [('bad.pdf', bad), ('good.pdf', good)]),
                            ('good-first', [('good.pdf', good), ('bad.pdf', bad)])]:
            with self.subTest(order=key):
                service = MinerUService(replace(self.config, mode='local'), self.repository)
                task, _ = await service.submit('qa-owner', key, inputs)
                await service.run(task['id'])
                stored = self.repository.get(task['id'])
                by_name = {file['file_name']: file for file in stored['files']}
                self.assertEqual(by_name['good.pdf']['status'], 'completed',
                                 'valid sibling must still be parsed after corrupt input')
                self.assertEqual(stored['status'], 'partial')
                self.assertEqual(by_name['bad.pdf']['status'], 'failed')

    async def test_failed_database_result_can_resume_without_new_remote_task(self):
        from qa_core.document_parsing.mineru_client import MinerUClient
        from qa_core.document_parsing.mineru_mock import mock_transport
        from qa_core.document_parsing.mineru_service import MinerUService

        class FlakySink:
            calls = 0
            def save(self, task, file, result):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError('synthetic transient failure')
                return 'synthetic-parse-id'

        sink = FlakySink()
        client = MinerUClient(self.config, transport=mock_transport())
        self.addAsyncCleanup(client.close)
        service = MinerUService(self.config, self.repository, client, result_sink=sink)
        source = self.root / 'fixture.pdf'
        source.write_bytes(b'%PDF-1.7 synthetic')
        task, _ = await service.submit('qa-owner', 'resume-key', [('fixture.pdf', source)])
        await service.run(task['id'])
        failed = self.repository.get(task['id'])
        self.assertEqual(failed['status'], 'failed')
        await service.resume(task['id'], 'qa-owner')
        await service.run(task['id'])
        recovered = self.repository.get(task['id'])
        self.assertEqual(recovered['status'], 'completed')
        self.assertEqual(recovered['remote_id'], failed['remote_id'])
        self.assertEqual(recovered['files'][0]['database_parse_id'], 'synthetic-parse-id')
        self.assertEqual(sink.calls, 2)
