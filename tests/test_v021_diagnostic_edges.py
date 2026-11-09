"""安全诊断的脱敏、上下文与失败恢复边界，全部使用合成异常。"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from qa_core.document_parsing.diagnostics import attached_diagnostic, engine_unavailable, safe_diagnostic
from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing import runtime
from qa_core.utils import IngestionError


class DiagnosticSafetyEdges(unittest.TestCase):
    def test_oserror_is_dependency_only_in_explicit_loading_boundary(self):
        error = FileNotFoundError('合成依赖文件缺失')
        self.assertIsNone(attached_diagnostic(error, component='paddle'))
        diagnostic = attached_diagnostic(error, component='paddle', loading=True)
        self.assertEqual(diagnostic['reason'], 'LOCAL_DEPENDENCY_ERROR')

    def test_context_policy_cycle_is_bounded(self):
        outer = ImportError('合成失败')
        inner = OSError('合成拒绝')
        inner.winerror = 1260
        outer.__context__ = inner
        inner.__context__ = outer
        self.assertEqual(engine_unavailable(outer, component='paddle')['reason'], 'WINDOWS_POLICY_BLOCKED')

    def test_attachment_extra_fields_and_bad_type_are_sanitized(self):
        error = IngestionError('PRIVATE_TOKEN synthetic/private.dll')
        error.diagnostic = dict(status='LOCAL_ENGINE_UNAVAILABLE', reason='LOCAL_DEPENDENCY_ERROR',
                                exception_type=['PRIVATE_TOKEN'], component='paddle', path='private/path')
        page = DocumentParser._error_page(1, 'ocr', {}, error)
        diagnostic = page.raw_result['engine_availability']
        self.assertEqual(set(diagnostic), {'status', 'reason', 'exception_type', 'component'})
        self.assertEqual(diagnostic['exception_type'], 'Exception')
        self.assertNotIn('PRIVATE_TOKEN', json.dumps(page.raw_result) + page.error_message)
        self.assertIsNone(safe_diagnostic(dict(error.diagnostic, reason=['PRIVATE_TOKEN'])))

    def test_algorithm_error_is_not_dependency_failure(self):
        page = DocumentParser._error_page(1, 'structure', {}, ValueError('合成算法异常'))
        self.assertEqual(page.parsing_status, 'failed')
        self.assertNotIn('engine_availability', page.raw_result)

    def test_worker_engine_initialization_dependency_is_classified(self):
        error = OSError('合成引擎初始化失败')
        error.winerror = 577
        with patch.object(runtime, '_LOGGING_CONFIGURED', True), \
             patch.object(runtime, '_ENGINES', {}), \
             patch.object(runtime, '_build_engine', side_effect=error):
            with self.assertRaises(IngestionError) as caught:
                runtime._worker_predict('ocr', 'synthetic.png', object())
        self.assertEqual(caught.exception.diagnostic['reason'], 'WINDOWS_POLICY_BLOCKED')

    def test_native_candidate_keeps_enhancement_unavailability(self):
        import fitz
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic-columns.pdf'
            with fitz.open() as pdf:
                page = pdf.new_page(width=600, height=800)
                page.insert_textbox(fitz.Rect(40, 40, 260, 300), 'LEFTMARK\n' * 6, fontsize=12)
                page.insert_textbox(fitz.Rect(340, 40, 560, 300), 'RIGHTMARK\n' * 6, fontsize=12)
                pdf.save(path)
            worker = MagicMock()
            worker.predict.side_effect = ImportError('PRIVATE_TOKEN synthetic/private.dll')
            with DocumentParser(runtime=worker) as parser:
                result = parser.parse(path)
            self.assertIn('LEFTMARK', result.raw_text)
            self.assertIn('RIGHTMARK', result.raw_text)
            self.assertTrue(result.requires_review)
            self.assertEqual(result.pages[0].raw_result['engine_availability']['reason'], 'LOCAL_DEPENDENCY_ERROR')
            self.assertNotIn('PRIVATE_TOKEN', json.dumps(result.to_dict()))


class LocalContextFailureEdges(unittest.IsolatedAsyncioTestCase):
    async def test_enter_failure_is_checkpointed_and_reused_without_cloud(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'synthetic.png'
            source.write_bytes(b'synthetic-only')
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            parser = MagicMock()
            parser.__enter__.side_effect = ImportError('PRIVATE_TOKEN synthetic/private.dll')
            factory = MagicMock(return_value=parser)
            client = MagicMock()
            config = MinerUConfig(enabled=True, mode='remote', provider='official',
                                 api_url='https://mineru.net/api', api_key='synthetic-only', result_dir=root)
            router = DualEngineRouter(DualEngineConfig(enabled=True), config,
                                      parser_factory=factory, client_factory=client)
            file = dict(id='file', file_name=source.name, sha256=sha, source_path=str(source), source_file_id='source')
            task = dict(id='task', owner='qa', result_root=str(root), files=[file],
                        parse_options=dict(strategy='local', allow_cloud_fallback=False, sensitive=False))
            async def save(value):
                pass
            for _ in range(2):
                result = await router.parse(task, file, save)
                self.assertEqual(result.parsing_status, 'failed')
                self.assertTrue(result.requires_review)
                trace = result.quality['routing_trace']
                self.assertEqual(trace['local_availability']['reason'], 'LOCAL_DEPENDENCY_ERROR')
                self.assertEqual(trace['usage']['calls'], 0)
                self.assertNotIn('PRIVATE_TOKEN', json.dumps(trace))
            self.assertEqual(factory.call_count, 1)
            client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
