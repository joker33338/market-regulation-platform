from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from qa_core.indexing.document_loaders import load_file
from qa_core.indexing.ocr_documents import approve_candidate, recognize_file
from qa_core.indexing.service import prepare_document
from qa_core.utils import IngestionError


class OptionalLoaders(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "PyMuPDF optional dependency")
    def test_real_pdf_loader_preserves_both_pages(self):
        import fitz
        path = self.root / "source.pdf"
        with fitz.open() as pdf:
            for value in ["first page", "second page"]:
                pdf.new_page().insert_text((72, 72), value)
            pdf.save(path)
        document = load_file(path, law_name="PDF sample")
        self.assertEqual({line.page for line in document.lines}, {1, 2})
        self.assertTrue(all(line.bbox is not None for line in document.lines))

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "PyMuPDF optional dependency")
    def test_empty_pdf_page_requires_ocr(self):
        import fitz
        path = self.root / "scan.pdf"
        with fitz.open() as pdf:
            pdf.new_page()
            pdf.save(path)
        with self.assertRaises(IngestionError):
            load_file(path)

    def test_ocr_candidate_review_and_source_span_end_to_end(self):
        class Engine:
            def ocr(self, path, cls=True):
                return [[
                    [[[0, 0], [10, 0], [10, 10], [0, 10]], ("测试办法", 0.99)],
                    [[[0, 10], [10, 10], [10, 20], [0, 20]], ("第一条 测试内容。", 0.98)],
                ]]
        source = self.root / "scan.png"
        source.write_bytes(b"test input; engine mocked")
        result = recognize_file(source, self.root / "ocr", Engine())
        candidate = Path(result["candidate"])
        with self.assertRaises(IngestionError):
            load_file(candidate)
        approve_candidate(candidate, "test-reviewer")
        document = load_file(candidate)
        _, _, chunks, _ = prepare_document(document, model_signature="test", max_chars=800)
        self.assertEqual(chunks[0].article_no, "第一条")
        self.assertEqual(chunks[0].metadata["source_spans"][0]["page"], 1)
        self.assertIn("bbox", chunks[0].metadata["source_spans"][0])


if __name__ == "__main__":
    unittest.main()

