"""只验证工厂配置守卫，不发送HTTP，不读取真实Token。"""
from pathlib import Path
import tempfile
import unittest
from qa_core.document_parsing.dual_engine import DualEngineConfig
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_api import create_app
from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.document_parsing.mineru_service import MinerUService
from qa_core.document_parsing.mineru_repository import TaskRepository


class BatchStartupGuard(unittest.TestCase):
    def test_QTB001_disabled_dual_must_not_fall_into_direct_official_service(self):
        with tempfile.TemporaryDirectory() as folder:
            remote=MinerUConfig(enabled=True,mode='remote',provider='official',api_url='https://mineru.net/api',
                                api_key='synthetic-token',result_dir=Path(folder))
            policy=DualEngineConfig(enabled=False,cloud_enabled=False,environment='test',authorization_mode='TEST_BATCH')
            with self.assertRaises((MinerUError,ValueError),msg='TEST_BATCH必须failclosed，不能因dual disabled改走直接官方服务'):
                create_app(remote,tokens={'a'*32:'alice'},dual_config=policy)

    def test_production_file_sha_legacy_factory_remains_available(self):
        with tempfile.TemporaryDirectory() as folder:
            remote=MinerUConfig(enabled=True,mode='remote',provider='official',api_url='https://mineru.net/api',
                                api_key='synthetic-token',result_dir=Path(folder))
            app=create_app(remote,tokens={'a'*32:'alice'},dual_config=DualEngineConfig(enabled=False))
            self.assertIsNotNone(app)

    def test_QTB001_enabled_batch_cannot_inject_unbound_direct_service(self):
        with tempfile.TemporaryDirectory() as folder:
            remote=MinerUConfig(enabled=True,mode='remote',provider='official',api_url='https://mineru.net/api',
                                api_key='synthetic-token',result_dir=Path(folder))
            service=MinerUService(remote,TaskRepository(Path(folder)/'tasks.sqlite3'))
            policy=DualEngineConfig(enabled=True,cloud_enabled=True,environment='test',authorization_mode='TEST_BATCH')
            with self.assertRaises((MinerUError,ValueError)):
                create_app(remote,tokens={'a'*32:'alice'},dual_config=policy,service=service)

    def test_QTB001_disabled_batch_cannot_bypass_guard_with_injected_service(self):
        with tempfile.TemporaryDirectory() as folder:
            remote=MinerUConfig(enabled=True,mode='remote',provider='official',api_url='https://mineru.net/api',
                                api_key='synthetic-token',result_dir=Path(folder))
            service=MinerUService(remote,TaskRepository(Path(folder)/'tasks.sqlite3'))
            policy=DualEngineConfig(enabled=False,environment='test',authorization_mode='TEST_BATCH')
            with self.assertRaises((MinerUError,ValueError)):
                create_app(remote,tokens={'a'*32:'alice'},dual_config=policy,service=service)

    def test_production_injected_legacy_service_is_not_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            remote=MinerUConfig(enabled=True,mode='remote',provider='official',api_url='https://mineru.net/api',
                                api_key='synthetic-token',result_dir=Path(folder))
            service=MinerUService(remote,TaskRepository(Path(folder)/'tasks.sqlite3'))
            app=create_app(remote,tokens={'a'*32:'alice'},dual_config=DualEngineConfig(enabled=False),service=service)
            self.assertIsNotNone(app)


if __name__=='__main__':unittest.main()
