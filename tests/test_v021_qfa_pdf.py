"""空白整文、混合空白页与 PDF 内容类型的合成边界。"""
import tempfile
from pathlib import Path
import unittest

import fitz
from PIL import Image

from qa_core.document_parsing.document_router import DocumentParser
from qa_core.utils import IngestionError
from tests.test_document_parsing import FakeRuntime


class PdfAcceptanceBoundaries(unittest.TestCase):
    def test_blank_document_requires_review_without_loading_models(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "blank.pdf"
            with fitz.open() as pdf:
                pdf.new_page()
                pdf.new_page()
                pdf.save(path)
            runtime = FakeRuntime()
            with DocumentParser(runtime=runtime) as parser:
                result = parser.parse(path)
            self.assertEqual(result.parsing_status, "needs_review")
            self.assertTrue(result.requires_review)
            self.assertEqual(runtime.calls, [])
            self.assertEqual([p.page_number for p in result.pages], [1, 2])
            self.assertEqual(result.pages[0].source_location["file_sha256"], result.document_id)
            self.assertIn("empty_page", {item["code"] for item in result.quality["findings"]})

    def test_blank_page_in_readable_document_keeps_native_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mixed-blank.pdf"
            with fitz.open() as pdf:
                pdf.new_page()
                pdf.new_page().insert_text((72, 72), "Readable native content.")
                pdf.save(path)
            runtime = FakeRuntime()
            with DocumentParser(runtime=runtime) as parser:
                result = parser.parse(path)
                blank_selection = parser.parse(path, page_numbers=[1])
            self.assertEqual(result.parsing_status, "success")
            self.assertEqual(result.pages[0].parsing_status, "success")
            self.assertEqual(runtime.calls, [])
            self.assertIn("Readable", result.raw_text)
            self.assertEqual(blank_selection.parsing_status, "needs_review")

    def test_disguised_image_is_rejected_before_any_inference_in_every_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "disguised.pdf"
            Image.new("RGB", (80, 80), "white").save(path, format="PNG")
            runtime = FakeRuntime()
            with DocumentParser(runtime=runtime) as parser:
                for mode in ("auto", "ocr", "structure"):
                    with self.subTest(mode=mode), self.assertRaisesRegex(IngestionError, "不是 PDF"):
                        parser.parse(path, mode=mode)
            self.assertEqual(runtime.calls, [])

    def test_legitimate_image_still_uses_image_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scan.png"
            Image.new("RGB", (80, 80), "white").save(path)
            runtime = FakeRuntime()
            with DocumentParser(runtime=runtime) as parser:
                result = parser.parse(path, mode="ocr")
            self.assertEqual(result.parsing_status, "success")
            self.assertEqual(runtime.calls, ["ocr"])
