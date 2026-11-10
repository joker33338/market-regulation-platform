"""合成 OOXML 表格的混合合并、终止、异常与多表保留。"""
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from qa_core.document_parsing.document_router import DocumentParser
from tests.test_document_parsing import FakeRuntime


def cell(text="", *, merge=None, span=1):
    props = f'<w:gridSpan w:val="{span}"/>' if span != 1 else ""
    if merge is not None:
        props += f'<w:vMerge w:val="{merge}"/>' if merge else "<w:vMerge/>"
    return f"<w:tc><w:tcPr>{props}</w:tcPr><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"


def table(*rows):
    return "<w:tbl>" + "".join("<w:tr>" + row + "</w:tr>" for row in rows) + "</w:tbl>"


class DocxMergeBoundaries(unittest.TestCase):
    def parse(self, body):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.docx"
            with ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                                 + "<w:body>" + body + "</w:body></w:document>")
            runtime = FakeRuntime()
            with DocumentParser(runtime=runtime) as parser:
                result = parser.parse(path)
            self.assertEqual(runtime.calls, [])
            self.assertEqual(result.parsing_status, "success")
            return result

    def test_mixed_horizontal_vertical_spans_preserve_columns_and_source(self):
        result = self.parse(table(cell("合并锚点", merge="restart", span=2) + cell("右上"),
                                  cell(merge="continue", span=2) + cell("右中"),
                                  cell(merge="", span=2) + cell("右下")))
        page = result.pages[0]
        value = page.tables[0]
        self.assertEqual([(c["row"], c["column"], c["rowspan"], c["colspan"]) for c in value.cells],
                         [(0, 0, 3, 2), (0, 2, 1, 1), (1, 2, 1, 1), (2, 2, 1, 1)])
        self.assertEqual([row[2] for row in value.rows], ["右上", "右中", "右下"])
        self.assertIn('rowspan="3" colspan="2"', value.html)
        self.assertEqual(value.markdown, value.html)
        self.assertEqual(value.source_location["body_index"], 0)
        self.assertEqual(value.source_location["file_sha256"], result.document_id)
        self.assertIn("vMerge", page.raw_result["body_xml"])

    def test_merge_ends_on_independent_cell_and_restarts_without_cross_table_leak(self):
        body = table(cell("A", merge="restart"), cell(merge=""), cell("B"),
                     cell("C", merge="restart"), cell(merge=""))
        result = self.parse(body + table(cell("D", span=2), cell("E") + cell("F")))
        first, second = result.pages[0].tables
        self.assertEqual([(c["text"], c["row"], c["rowspan"]) for c in first.cells],
                         [("A", 0, 2), ("B", 2, 1), ("C", 3, 2)])
        self.assertEqual([(c["text"], c["colspan"], c["rowspan"]) for c in second.cells],
                         [("D", 2, 1), ("E", 1, 1), ("F", 1, 1)])
        self.assertEqual(second.table_id, "1")

    def test_orphan_or_changed_span_preserves_cells_with_warning(self):
        result = self.parse(table(cell("孤立", merge="continue"),
                                  cell("起点", merge="restart", span=2),
                                  cell("跨度不符", merge="continue")))
        value = result.pages[0].tables[0]
        self.assertEqual([c["text"] for c in value.cells], ["孤立", "起点", "跨度不符"])
        self.assertTrue(any("没有匹配" in warning for warning in value.warnings))

    def test_nonempty_continuation_does_not_discard_text(self):
        result = self.parse(table(cell("起点", merge="restart"), cell("延续正文", merge="")))
        value = result.pages[0].tables[0]
        self.assertEqual(len(value.cells), 1)
        self.assertEqual(value.cells[0]["text"], "起点\n延续正文")
        self.assertEqual(value.cells[0]["rowspan"], 2)
        self.assertTrue(any("延续格含正文" in warning for warning in value.warnings))
