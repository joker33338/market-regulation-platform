"""文档或临时页I/O失败不得被误报为引擎依赖不可用。"""
import errno
import unittest
from unittest.mock import MagicMock, patch

from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing import runtime
from qa_core.utils import IngestionError


class DocumentIOClassification(unittest.TestCase):
    def test_missing_page_file_does_not_mark_engine_unavailable(self):
        page = DocumentParser._error_page(1, 'ocr', {}, FileNotFoundError(errno.ENOENT, '合成页面已不存在'))
        self.assertEqual(page.parsing_status, 'failed')
        self.assertNotIn('engine_availability', page.raw_result)

    def test_document_access_denied_does_not_mark_engine_unavailable(self):
        page = DocumentParser._error_page(1, 'structure', {}, PermissionError(errno.EACCES, '合成文档无读取权限'))
        self.assertEqual(page.parsing_status, 'failed')
        self.assertNotIn('engine_availability', page.raw_result)

    def test_ready_engine_input_io_does_not_mark_dependency_failure(self):
        config = object()
        engine = MagicMock()
        engine.predict.side_effect = FileNotFoundError(errno.ENOENT, '合成临时页面不存在')
        with patch.object(runtime, '_LOGGING_CONFIGURED', True), \
             patch.object(runtime, '_ENGINES', {('ocr', config): engine}):
            with self.assertRaises(IngestionError) as caught:
                runtime._worker_predict('ocr', 'synthetic-missing.png', config)
        self.assertFalse(getattr(caught.exception, 'diagnostic', None))


if __name__ == '__main__':
    unittest.main()
