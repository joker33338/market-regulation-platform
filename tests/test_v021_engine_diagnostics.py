"""用合成异常验证不可用诊断；禁止模型、真实HTTP和系统策略改动。"""
import asyncio
from dataclasses import replace
import hashlib
import importlib
import json
from pathlib import Path
import pickle
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing import runtime
from qa_core.utils import IngestionError


def classify(error, component='paddle'):
    module = importlib.import_module('qa_core.document_parsing.diagnostics')
    return module.engine_unavailable(error, component=component)


def policy_error(code=577):
    error = OSError('合成私密路径与密钥不得进入结构化诊断')
    error.winerror = code
    return error


class EngineDiagnosticsContract(unittest.TestCase):
    def test_structured_winerror_577_identifies_policy(self):
        result = classify(policy_error())
        self.assertEqual(result['status'], 'LOCAL_ENGINE_UNAVAILABLE')
        self.assertEqual(result['reason'], 'WINDOWS_POLICY_BLOCKED')

    def test_chained_winerror_1260_identifies_policy(self):
        error = ImportError('合成导入失败')
        error.__cause__ = policy_error(1260)
        self.assertEqual(classify(error)['reason'], 'WINDOWS_POLICY_BLOCKED')

    def test_unproved_import_failure_is_dependency_error(self):
        result = classify(ImportError('合成依赖失败'), component='mineru_transport')
        self.assertEqual(result['reason'], 'LOCAL_DEPENDENCY_ERROR')
        self.assertEqual(result['component'], 'mineru_transport')

    def test_message_only_does_not_prove_policy(self):
        error = ImportError('WINDOWS_POLICY_BLOCKED 应用程序控制策略已阻止此文件')
        self.assertEqual(classify(error)['reason'], 'LOCAL_DEPENDENCY_ERROR')

    def test_diagnostic_contains_no_private_exception_message(self):
        result = classify(ImportError('PRIVATE_TOKEN synthetic/private/document.pdf'))
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn('PRIVATE_TOKEN', encoded)
        self.assertNotIn('document.pdf', encoded)
        self.assertEqual(set(result), {'status', 'reason', 'exception_type', 'component'})

    def test_page_retains_attached_safe_diagnostic(self):
        error = IngestionError('合成初始化失败')
        error.diagnostic = dict(status='LOCAL_ENGINE_UNAVAILABLE', reason='WINDOWS_POLICY_BLOCKED',
                                exception_type='ImportError', component='paddle')
        page = DocumentParser._error_page(1, 'ocr', {}, error)
        self.assertEqual(page.raw_result.get('engine_availability'), error.diagnostic)
        self.assertEqual(page.parsing_status, 'failed')

    def test_worker_wrapper_diagnostic_survives_exception_pickle(self):
        config = MagicMock()
        config.validate_models.return_value = {}
        config.cpu_threads = 1
        error = ImportError('合成模型包不可加载')
        error.__cause__ = policy_error()
        original_import = __import__
        def blocked_import(name, *args, **kwargs):
            if name == 'paddleocr':
                raise error
            return original_import(name, *args, **kwargs)
        with patch.object(runtime, 'install_offline_guard'), \
             patch.object(runtime.importlib.metadata, 'version', side_effect=lambda name: {
                 'paddleocr': '3.3.2', 'paddlex': '3.3.10', 'paddlepaddle': '3.2.2'}[name]), \
             patch('builtins.__import__', side_effect=blocked_import):
            with self.assertRaises(IngestionError) as caught:
                runtime._build_engine('ocr', config)
        restored = pickle.loads(pickle.dumps(caught.exception))
        self.assertEqual(getattr(restored, 'diagnostic', {}).get('reason'), 'WINDOWS_POLICY_BLOCKED')


class ConstructorFailureContract(unittest.IsolatedAsyncioTestCase):
    async def test_failed_local_constructor_kept_and_cloud_not_misreported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'synthetic.png'
            source.write_bytes(b'synthetic non-confidential fixture')
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            local_error = IngestionError('合成本地引擎无法初始化')
            local_error.diagnostic = dict(status='LOCAL_ENGINE_UNAVAILABLE', reason='WINDOWS_POLICY_BLOCKED',
                                         exception_type='ImportError', component='paddle')
            remote_config = MinerUConfig(enabled=True, mode='remote', provider='official',
                api_url='https://mineru.net/api', api_key='synthetic-only', result_dir=root)
            parser = MagicMock(side_effect=local_error)
            client = MagicMock(side_effect=ImportError('PRIVATE_TOKEN synthetic/ssl.dll'))
            router = DualEngineRouter(DualEngineConfig(enabled=True, cloud_enabled=True), remote_config,
                grants={'qa': {sha: dict(authorization_id='synthetic-approved', expires_at=time.time()+60)}},
                parser_factory=parser, client_factory=client)
            file = dict(id='file',file_name='synthetic.png',sha256=sha,source_path=str(source),source_file_id='source')
            task = dict(id='task',owner='qa',result_root=str(root),files=[file],
                        parse_options=dict(strategy='remote',allow_cloud_fallback=True,sensitive=False))
            async def save(value):
                pass
            result = await router.parse(task, file, save)
            trace = result.quality['routing_trace']
            self.assertEqual(trace['local_availability']['status'], 'LOCAL_ENGINE_UNAVAILABLE')
            self.assertEqual(trace['remote_availability']['status'], 'BLOCKED')
            self.assertEqual(trace['remote_availability']['api_status'], 'NOT_TESTED')
            self.assertEqual(trace['remote_availability']['reason'], 'LOCAL_DEPENDENCY_ERROR')
            self.assertEqual(trace['usage']['calls'], 0)
            self.assertEqual(client.call_count, 1)
            self.assertTrue((root/'task/file/local-candidate.json').is_file())
            self.assertTrue(result.requires_review)
            self.assertNotIn('PRIVATE_TOKEN', json.dumps(trace['remote_availability']))


if __name__ == '__main__':
    unittest.main()
