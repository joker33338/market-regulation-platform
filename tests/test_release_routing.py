"""CLOSE-03 的路由和复核一致性回归；不加载模型、不调用远端。"""
from pathlib import Path
import tempfile
import unittest

import fitz

from qa_core.document_parsing.config import ParsingConfig
from qa_core.document_parsing.document_router import DocumentParser
from tests.test_document_parsing import FakeRuntime


class ReleaseRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = FakeRuntime()

    def tearDown(self):
        self.temp.cleanup()

    def table_pdf(self):
        source = self.root / 'aligned.pdf'
        with fitz.open() as pdf:
            page = pdf.new_page()
            for row in range(7):
                for column in range(4):
                    text = f'Field{column}' if row == 0 else str(row * 100 + column)
                    page.insert_text((50 + column * 100, 60 + row * 25), text)
            pdf.save(source)
        return source

    def test_enabled_wireless_table_uses_structure(self):
        source = self.table_pdf()
        before = source.read_bytes()
        with DocumentParser(ParsingConfig(enable_tables=True), runtime=self.runtime) as parser:
            result = parser.parse(source)
        self.assertEqual(self.runtime.calls, ['structure'])
        self.assertEqual(result.pages[0].parsing_method, 'structure')
        self.assertTrue(result.pages[0].source_location['text_table_hint'])
        self.assertTrue(result.requires_review)
        self.assertEqual(source.read_bytes(), before)

    def test_disabled_tables_and_ordinary_text_remain_native(self):
        source = self.table_pdf()
        with DocumentParser(ParsingConfig(enable_tables=False), runtime=self.runtime) as parser:
            self.assertEqual(parser.parse(source).pages[0].parsing_method, 'native_pdf')
        ordinary = self.root / 'ordinary.pdf'
        with fitz.open() as pdf:
            page = pdf.new_page()
            page.insert_text((50, 60), 'This is ordinary continuous text without aligned numeric columns.')
            page.insert_text((50, 85), 'A second paragraph keeps the native extraction priority.')
            pdf.save(ordinary)
        with DocumentParser(ParsingConfig(enable_tables=True), runtime=self.runtime) as parser:
            self.assertEqual(parser.parse(ordinary).pages[0].parsing_method, 'native_pdf')
        self.assertEqual(self.runtime.calls, [])

    def test_structure_failure_preserves_native_candidate_and_review(self):
        source = self.table_pdf()
        self.runtime.fail = True
        with DocumentParser(ParsingConfig(enable_tables=True), runtime=self.runtime) as parser:
            result = parser.parse(source)
        self.assertEqual(self.runtime.calls, ['structure'])
        self.assertIn('Field0', result.raw_text)
        self.assertEqual(result.pages[0].parsing_method, 'native_pdf')
        self.assertEqual(result.parsing_status, 'needs_review')
        self.assertIn('enhancement_failure', result.pages[0].raw_result)
        self.assertTrue(result.requires_review)

    def test_native_quality_findings_set_top_level_review(self):
        source = self.root / 'synthetic.txt'
        source.write_text('第一条 测试条文。\n第一条 重复条号需要复核。', encoding='utf-8')
        with DocumentParser(ParsingConfig(), runtime=self.runtime) as parser:
            result = parser.parse(source)
        self.assertTrue(result.quality['review_required'])
        self.assertTrue(result.requires_review)
        self.assertIn('duplicate_article_number', [item['code'] for item in result.quality['findings']])
        self.assertEqual(self.runtime.calls, [])
