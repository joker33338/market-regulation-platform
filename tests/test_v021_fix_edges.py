"""原生候选兜底的页级隔离与复核边界，不调用真实模型。"""
from pathlib import Path
import tempfile
import unittest
import fitz

from qa_core.document_parsing.document_router import DocumentParser
from tests.test_document_parsing import FakeRuntime
from tests.test_v021_native_preservation import RejectingEnhancement


class NativeFallbackEdges(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic-pages.pdf'
        with fitz.open() as document:
            page = document.new_page(width=600, height=800)
            page.insert_textbox(fitz.Rect(40, 40, 260, 300), 'LEFTMARK\n' + 'Native left column.\n' * 6, fontsize=12)
            page.insert_textbox(fitz.Rect(340, 40, 560, 300), 'RIGHTMARK\n' + 'Native right column.\n' * 6, fontsize=12)
            page = document.new_page(width=600, height=800)
            page.draw_rect(fitz.Rect(50, 50, 150, 150))
            document.save(self.path)

    def test_fallback_requires_review_and_does_not_leak_into_next_page(self):
        with DocumentParser(runtime=RejectingEnhancement()) as parser:
            result = parser.parse(self.path)
        self.assertEqual(result.pages[0].parsing_method, 'native_pdf')
        self.assertEqual(result.pages[0].parsing_status, 'needs_review')
        self.assertEqual(result.pages[0].source_location['coordinate_space'], 'pdf_point')
        self.assertIn('text_blocks', result.pages[0].raw_result)
        self.assertIn('layout_enhancement_failed', result.quality['routing']['reasons'])
        self.assertTrue(result.quality['routing']['fallback_recommended'])
        self.assertTrue(result.quality['review_required'])
        self.assertEqual(result.pages[1].parsing_status, 'failed')
        self.assertEqual(result.pages[1].raw_text, '')
        self.assertNotIn('enhancement_failure', result.pages[1].raw_result)

    def test_forced_structure_without_native_candidate_keeps_failure(self):
        with DocumentParser(runtime=RejectingEnhancement()) as parser:
            result = parser.parse(self.path, mode='structure', page_numbers=[1])
        self.assertEqual(result.parsing_status, 'failed')
        self.assertEqual(result.pages[0].raw_text, '')
        self.assertNotIn('enhancement_failure', result.pages[0].raw_result)

    def test_successful_enhancement_does_not_use_native_fallback(self):
        with DocumentParser(runtime=FakeRuntime()) as parser:
            result = parser.parse(self.path, page_numbers=[1])
        self.assertEqual(result.pages[0].parsing_method, 'structure')
        self.assertNotIn('enhancement_failure', result.pages[0].raw_result)
        self.assertNotIn('layout_enhancement_failed', result.quality['routing']['reasons'])


if __name__ == '__main__':
    unittest.main()
