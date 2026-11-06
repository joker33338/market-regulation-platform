from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from qa_core.document_parsing.bridge import to_legal_document
from qa_core.document_parsing.config import ParsingConfig
from qa_core.document_parsing.document_router import DocumentParser, export_result
from qa_core.document_parsing.normalizer import normalize_text, table_from_html
from qa_core.document_parsing.paddle_ocr import PaddleOCRService
from qa_core.document_parsing.paddle_structure import PaddleStructureService
from qa_core.document_parsing.paddle_compat import share_table_ocr_pipeline, skip_disabled_chart_model
from qa_core.document_parsing.quality import assess_document
from qa_core.document_parsing.runtime import PaddleRuntime
from qa_core.document_parsing.schemas import DocumentResult, LayoutBlock, PageResult, TableResult, json_safe
from qa_core.utils import IngestionError


class FakeRuntime:
    def __init__(self):
        self.calls = []
        self.closed = False
        self.fail = False

    def close(self):
        self.closed = True

    def predict(self, method, image_path):
        self.calls.append(method)
        if self.fail:
            raise IngestionError("test engine failure")
        raw = {"rec_texts": ["第一条 原文金额500元。"], "rec_scores": [0.99],
               "rec_polys": [[[10, 10], [110, 10], [110, 40], [10, 40]]]}
        if method == "structure":
            raw = {"parsing_res_list": [
                {"block_id": 8, "block_order": 1, "block_label": "text", "block_content": "第二条 原文。", "block_bbox": [10, 60, 100, 90]},
                {"block_id": 2, "block_order": 0, "block_label": "doc_title", "block_content": "第一条 原文金额500元。", "block_bbox": [10, 10, 100, 40]},
            ], "overall_ocr_res": {"rec_scores": [0.98, 0.99]}, "table_res_list": []}
        return {"raw": {"res": raw}, "markdown": "# 第一条 原文金额500元。\n\n第二条 原文。" if method == "structure" else "",
                "model_load_time": 0.02, "processing_time": 0.1, "peak_memory_bytes": 12345,
                "network_blocked_attempts": 4}


class DocumentParsingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = FakeRuntime()
        self.parser = DocumentParser(ParsingConfig(), runtime=self.runtime)

    def tearDown(self):
        self.parser.close()
        self.temp.cleanup()

    def text(self, name="law.txt", value="测试法律\n第一条 金额500元。\n第二条 日期2026年11月6日。"):
        path = self.root / name
        path.write_text(value, encoding="utf-8")
        return path

    def image(self, name="scan.png"):
        from PIL import Image, ImageDraw
        path = self.root / name
        image = Image.new("RGB", (300, 300), "white")
        ImageDraw.Draw(image).text((20, 20), "scanned text", fill="black")
        image.save(path)
        return path

    def test_import_and_construction_are_lazy(self):
        check = subprocess.run([sys.executable, "-c",
            "import sys; from qa_core.document_parsing.document_router import DocumentParser;"
            "p=DocumentParser(); assert 'paddleocr' not in sys.modules; assert 'paddle' not in sys.modules;"
            "assert p.runtime._executor is None; p.close()"], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_disabled_chart_compatibility_does_not_load_optional_model(self):
        class Pipeline:
            use_chart_recognition = False
            def create_model(self, config, **kwargs):
                return config["model_name"]
        original = Pipeline.create_model
        with skip_disabled_chart_model(Pipeline):
            self.assertIsNone(Pipeline().create_model({"model_name": "PP-Chart2Table"}))
            self.assertEqual(Pipeline().create_model({"model_name": "PP-DocLayout-M"}), "PP-DocLayout-M")
            enabled = Pipeline()
            enabled.use_chart_recognition = True
            self.assertEqual(enabled.create_model({"model_name": "PP-Chart2Table"}), "PP-Chart2Table")
        self.assertIs(Pipeline.create_model, original)

    def test_chart_compatibility_restores_inherited_method_on_failure(self):
        class Base:
            def create_model(self, config):
                return config["model_name"]
        class Pipeline(Base):
            use_chart_recognition = False
        with self.assertRaises(RuntimeError):
            with skip_disabled_chart_model(Pipeline):
                raise RuntimeError("engine construction failed")
        self.assertNotIn("create_model", Pipeline.__dict__)
        self.assertEqual(Pipeline().create_model({"model_name": "PP-Chart2Table"}), "PP-Chart2Table")

    def test_table_cell_ocr_reuses_parent_recognizer_without_replacing_existing_one(self):
        from types import SimpleNamespace
        recognizer = object()
        table = SimpleNamespace(general_ocr_pipeline=None)
        engine = SimpleNamespace(paddlex_pipeline=SimpleNamespace(
            use_table_recognition=True, general_ocr_pipeline=recognizer,
            table_recognition_pipeline=SimpleNamespace(_pipeline=table)))
        self.assertIs(share_table_ocr_pipeline(engine), engine)
        self.assertIs(table.general_ocr_pipeline, recognizer)
        own = object()
        table.general_ocr_pipeline = own
        share_table_ocr_pipeline(engine)
        self.assertIs(table.general_ocr_pipeline, own)

    def test_text_uses_native_without_runtime_and_preserves_original(self):
        path = self.text()
        result = self.parser.parse(path)
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(result.pages[0].parsing_method, "native_text")
        self.assertEqual(result.raw_text, path.read_text(encoding="utf-8"))
        self.assertIn("500元", result.raw_text)

    def test_scan_image_outputs_coordinates_confidence_and_provenance(self):
        result = self.parser.parse(self.image(), "ocr")
        page = result.pages[0]
        self.assertEqual(page.confidence, 0.99)
        self.assertEqual(page.layout_blocks[0].bbox[0], [10, 10])
        self.assertIn("file_path", page.source_location)
        self.assertTrue(result.requires_review)
        self.assertEqual(page.network_blocked_attempts, 4)
        self.assertEqual(page.raw_result["res"]["rec_texts"], ["第一条 原文金额500元。"])

    def test_structure_honors_engine_reading_order(self):
        result = self.parser.parse(self.image(), "structure")
        blocks = result.pages[0].layout_blocks
        self.assertEqual([block.block_id for block in blocks], ["2", "8"])
        self.assertEqual(self.runtime.calls, ["structure"])
        self.assertIn("# 第一条", result.markdown_content)

    def test_mixed_pdf_routes_each_page(self):
        import fitz
        path = self.root / "mixed.pdf"
        image = self.image()
        with fitz.open() as pdf:
            page = pdf.new_page()
            page.insert_text((72, 72), "Native text paragraph with sufficient content for extraction.")
            page = pdf.new_page()
            page.insert_image(page.rect, filename=str(image))
            pdf.save(path)
        result = self.parser.parse(path)
        self.assertEqual([page.parsing_method for page in result.pages], ["native_pdf", "ocr"])
        self.assertEqual(self.runtime.calls, ["ocr"])
        self.assertIn("pdf_polygon", result.pages[1].layout_blocks[0].source_location)

    def test_short_native_pdf_is_not_unnecessarily_rasterized(self):
        import fitz
        path = self.root / "short.pdf"
        with fitz.open() as pdf:
            pdf.new_page().insert_text((72, 72), "Short.")
            pdf.save(path)
        result = self.parser.parse(path)
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(result.pages[0].parsing_method, "native_pdf")

    def test_scan_with_hidden_ocr_layer_is_rerecognized_and_original_preserved(self):
        import fitz
        path = self.root / "hidden-layer.pdf"
        old = "Unverified old OCR text. " * 12
        with fitz.open() as pdf:
            page = pdf.new_page()
            page.insert_image(page.rect, filename=str(self.image()), keep_proportion=False)
            page.insert_textbox(fitz.Rect(40, 40, 550, 800), old, render_mode=3)
            pdf.save(path)
        with patch("qa_core.document_parsing.document_router.has_grid", return_value=False):
            result = self.parser.parse(path)
        self.assertEqual(self.runtime.calls, ["ocr"])
        self.assertIn("500元", result.raw_text)
        self.assertIn("Unverified old OCR", result.pages[0].raw_result["pdf_text_layer"])
        self.assertTrue(result.pages[0].warnings)

    def test_empty_pdf_does_not_load_models(self):
        import fitz
        path = self.root / "blank.pdf"
        with fitz.open() as pdf:
            pdf.new_page()
            pdf.save(path)
        result = self.parser.parse(path)
        self.assertEqual(self.runtime.calls, [])
        self.assertIn("空白页", result.pages[0].warnings[0])

    def test_native_pdf_table_preserves_grid(self):
        import fitz
        path = self.root / "table.pdf"
        with fitz.open() as pdf:
            page = pdf.new_page()
            for y in [100, 150, 200, 250]:
                page.draw_line((50, y), (450, y))
            for x in [50, 250, 450]:
                page.draw_line((x, 100), (x, 250))
            for index, (left, right) in enumerate([("Header", "Amount"), ("Case A", "500"), ("Case B", "1000")]):
                page.insert_text((60, 130 + index * 50), left)
                page.insert_text((260, 130 + index * 50), right)
            pdf.save(path)
        result = self.parser.parse(path)
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(result.pages[0].tables[0].rows[1], ["Case A", "500"])
        self.assertIn("Case A\t500", result.raw_text)
        self.assertIn("|", result.markdown_content)

    def test_docx_table_stays_in_body_order_and_never_ocr(self):
        path = self.root / "table.docx"
        xml = """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
        <w:p><w:r><w:t>第一条 表前。</w:t></w:r></w:p>
        <w:tbl><w:tr><w:tc><w:p><w:r><w:t>项目</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>金额</w:t></w:r></w:p></w:tc></w:tr>
        <w:tr><w:tc><w:p><w:r><w:t>甲</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>500元</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
        <w:p><w:r><w:t>第二条 表后。</w:t></w:r></w:p></w:body></w:document>"""
        with ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", xml)
        result = self.parser.parse(path)
        page = result.pages[0]
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(page.tables[0].rows[1], ["甲", "500元"])
        self.assertLess(page.markdown_content.index("表前"), page.markdown_content.index("金额"))
        self.assertLess(page.markdown_content.index("金额"), page.markdown_content.index("表后"))

    def test_failures_keep_successful_pages_in_batch(self):
        self.runtime.fail = True
        results = self.parser.parse_batch([self.text(), self.image(), self.root / "missing.pdf"])
        self.assertEqual([result.parsing_status for result in results], ["success", "failed", "failed"])
        self.assertEqual(results[1].pages[0].error_message, "test engine failure")

    def test_file_size_and_page_limits(self):
        tiny = DocumentParser(ParsingConfig(max_file_bytes=1), runtime=self.runtime)
        with self.assertRaises(IngestionError):
            tiny.parse(self.text())
        import fitz
        path = self.root / "pages.pdf"
        with fitz.open() as pdf:
            pdf.new_page()
            pdf.new_page()
            pdf.save(path)
        small = DocumentParser(ParsingConfig(max_pages=1), runtime=self.runtime)
        with self.assertRaises(IngestionError):
            small.parse(path)

    def test_selected_pdf_pages_preserve_original_numbers_and_reject_out_of_range(self):
        import fitz
        path = self.root / "selected.pdf"
        with fitz.open() as pdf:
            for number in range(3):
                pdf.new_page().insert_text((72, 72), "Page " + str(number + 1))
            pdf.save(path)
        result = self.parser.parse(path, page_numbers=[3, 1, 3])
        self.assertEqual([page.page_number for page in result.pages], [1, 3])
        self.assertEqual(result.source_location["selected_pages"], [1, 3])
        with self.assertRaises(IngestionError):
            self.parser.parse(path, page_numbers=[4])

    def test_remote_urls_and_unsupported_formats_are_rejected(self):
        with self.assertRaises(IngestionError):
            self.parser.parse("https://example.com/document.pdf")
        bad = self.root / "document.exe"
        bad.write_bytes(b"not a document")
        with self.assertRaises(IngestionError):
            self.parser.parse(bad)

    def test_batch_count_limit(self):
        limited = DocumentParser(ParsingConfig(max_files=1), runtime=self.runtime)
        with self.assertRaises(IngestionError):
            limited.parse_batch([self.text(), self.text("other.txt")])

    def test_missing_models_fail_before_process_start(self):
        runtime = PaddleRuntime(ParsingConfig(model_root=self.root / "missing"))
        with self.assertRaisesRegex(IngestionError, "PP-OCRv5_mobile_det"):
            runtime.predict("ocr", "unused.png")
        self.assertIsNone(runtime._executor)

    def test_offline_network_guard_blocks_real_socket_call_in_child(self):
        check = subprocess.run([sys.executable, "-c",
            "import socket; from qa_core.document_parsing.runtime import install_offline_guard;"
            "install_offline_guard();"
            "\ntry: socket.create_connection(('198.51.100.1',443),timeout=0.1)"
            "\nexcept OSError as e: assert 'network is disabled' in str(e); print('BLOCKED')"
            "\nelse: raise AssertionError('network was not blocked')"], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("BLOCKED", check.stdout)

    def test_normalization_does_not_rewrite_legal_numbers(self):
        raw = "\ufeff第一条 罚款500元；不得处罚。\r\n（一）2026年11月6日。  "
        self.assertEqual(normalize_text(raw), "第一条 罚款500元；不得处罚。\n（一）2026年11月6日。")

    def test_json_safety_and_export_uses_hash_not_filename(self):
        result = self.parser.parse(self.text())
        result.file_name = "../../escape"
        result.pages[0].confidence = float("nan")
        decoded = json.loads(result.to_json())
        self.assertIsNone(decoded["pages"][0]["confidence"])
        export = export_result(result, self.root / "output")
        self.assertTrue(Path(export["json"]).resolve().is_relative_to((self.root / "output").resolve()))
        self.assertTrue(Path(export["markdown"]).is_file())
        restored = DocumentResult.from_dict(result.to_dict())
        self.assertEqual(restored.to_dict(), result.to_dict())

    def test_merged_table_retains_spans_and_html(self):
        table = table_from_html("<table><tr><th colspan='2'>标题</th></tr><tr><td>甲</td><td>500元</td></tr></table>", "t")
        self.assertEqual(table.cells[0]["colspan"], 2)
        self.assertTrue(table.markdown.startswith("<table>"))
        self.assertEqual(table.rows[1], ["甲", "500元"])

    def test_export_preserves_pdf_photo_assets_and_rejects_changed_source(self):
        import fitz
        from qa_core.utils import file_sha256
        path = self.root / "photo.pdf"
        with fitz.open() as pdf:
            pdf.new_page(width=100, height=100).insert_image(fitz.Rect(0, 0, 100, 100), filename=str(self.image()))
            pdf.save(path)
        page = PageResult(1, "structure", markdown_content='<img src="imgs/img_in_image_box_0_0_100_100.jpg" />',
                          source_location={"pdf_scale_x": 1, "pdf_scale_y": 1})
        result = DocumentResult(file_sha256(path), path.name, ".pdf", {"file_path": str(path)}, pages=[page])
        exported = export_result(result, self.root / "exports")
        self.assertEqual(len(exported["images"]), 1)
        self.assertTrue(Path(exported["images"][0]).is_file())
        self.assertIn("images/page-0001-01.png", Path(exported["markdown"]).read_text(encoding="utf-8"))
        restored = DocumentResult.from_dict(json.loads(Path(exported["json"]).read_text(encoding="utf-8")))
        repeated = export_result(restored, self.root / "exports-again")
        self.assertTrue(Path(repeated["images"][0]).is_file())
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(IngestionError):
            export_result(restored, self.root / "changed")

    def test_quality_reports_duplicate_and_low_confidence(self):
        result = DocumentResult("id", "law.pdf", ".pdf", {}, pages=[
            PageResult(1, "ocr", "第一条 原文。\n附则", confidence=0.6),
            PageResult(2, "ocr", "第一条 重复。\n修订日期2026年11月6日。"),
        ], requires_review=True)
        quality = assess_document(result)
        codes = [finding["code"] for finding in quality["findings"]]
        self.assertIn("duplicate_article_number", codes)
        self.assertIn("low_confidence", codes)
        self.assertTrue(quality["features"]["has_supplement"])

    def test_case_dossier_does_not_report_cross_page_articles_without_article_heading(self):
        result = DocumentResult("id", "case.pdf", ".pdf", {}, pages=[
            PageResult(1, "native_pdf", "案件来源登记表\n办案日期"),
            PageResult(2, "native_pdf", "询问笔录\n调查记录"),
        ])
        self.assertNotIn("possible_cross_page_article", [finding["code"] for finding in assess_document(result)["findings"]])

    def test_real_article_continuation_remains_flagged(self):
        result = DocumentResult("id", "law.pdf", ".pdf", {}, pages=[
            PageResult(1, "native_pdf", "第一条 本条前段"),
            PageResult(2, "native_pdf", "本条的后续文字。"),
        ])
        self.assertIn("possible_cross_page_article", [finding["code"] for finding in assess_document(result)["findings"]])

    def test_structure_table_text_and_coordinates_are_retained(self):
        markup = "<table><tr><td>项目</td><td>金额</td></tr><tr><td>甲</td><td>500元</td></tr></table>"
        payload = {"raw": {"res": {
            "parsing_res_list": [{"block_label": "table", "block_content": markup,
                                  "block_bbox": [10, 20, 210, 120]}],
            "table_res_list": [{"pred_html": markup, "cell_box_list": [
                [10, 20, 110, 70], [110, 20, 210, 70], [10, 70, 110, 120], [110, 70, 210, 120]]}],
        }}, "markdown": markup, "processing_time": 0.1, "model_load_time": 0,
                   "network_blocked_attempts": 0, "peak_memory_bytes": 100}
        with patch.object(self.runtime, "predict", return_value=payload):
            page = self.parser.structure.parse_image("unused.png", 1, {"pdf_scale_x": 2, "pdf_scale_y": 2})
        self.assertIn("甲\t500元", page.raw_text)
        self.assertNotIn("<table>", page.raw_text)
        self.assertEqual(page.tables[0].bbox, [10, 20, 210, 120])
        self.assertEqual(page.tables[0].source_location["pdf_bbox"], [5, 10, 105, 60])
        self.assertEqual(page.tables[0].cells[-1]["source_location"]["pdf_bbox"], [55, 35, 105, 60])

    def test_photo_without_text_requires_review(self):
        payload = {"raw": {"res": {"parsing_res_list": [
            {"block_label": "image", "block_content": "", "block_bbox": [0, 0, 100, 100]}]}},
                   "markdown": "", "processing_time": 0.1, "model_load_time": 0,
                   "network_blocked_attempts": 0, "peak_memory_bytes": 100}
        with patch.object(self.runtime, "predict", return_value=payload):
            page = self.parser.structure.parse_image("unused.png", 1, {})
        self.assertEqual(page.parsing_status, "needs_review")
        self.assertTrue(page.warnings)

    def test_bridge_requires_reviewer_and_never_flattens_tables(self):
        result = self.parser.parse(self.text())
        with self.assertRaises(IngestionError):
            to_legal_document(result, reviewer="", law_name="测试法律")
        legal = to_legal_document(result, reviewer="tester", law_name="测试法律")
        self.assertEqual(legal.lines[1].page, 1)
        self.assertEqual(legal.metadata["file_sha256"], result.document_id)
        result.pages[0].tables.append(TableResult("t"))
        with self.assertRaises(IngestionError):
            to_legal_document(result, reviewer="tester", law_name="测试法律")

    def test_reviewed_output_changes_when_parser_output_changes(self):
        result = self.parser.parse(self.text())
        first = to_legal_document(result, reviewer="tester", law_name="测试法律")
        result.pages[0].layout_blocks[1].raw_text += "新增原文"
        second = to_legal_document(result, reviewer="tester", law_name="测试法律")
        self.assertNotEqual(first.source_hash, second.source_hash)


if __name__ == "__main__":
    unittest.main()

