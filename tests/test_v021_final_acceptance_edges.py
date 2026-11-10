"""扩展真值所对应的最小合成回归；不包含真实文档或人工真值正文。"""
import tempfile
from pathlib import Path
import unittest
from zipfile import ZipFile

import fitz

from qa_core.document_parsing.document_router import DocumentParser
from qa_core.utils import IngestionError


class FinalAcceptanceEdges(unittest.TestCase):
    def test_png_disguised_as_pdf_is_rejected(self):
        """QFA-003：文件类型应按内容校验，不能把伪造 PDF 交给 OCR 报成功。"""
        from PIL import Image
        from tests.test_document_parsing import FakeRuntime
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'synthetic-disguised.pdf'
            Image.new('RGB', (240, 120), 'white').save(path, format='PNG')
            try:
                with DocumentParser(runtime=FakeRuntime()) as parser:
                    result = parser.parse(path)
            except IngestionError:
                return
            self.assertEqual(result.parsing_status, 'failed',
                             '伪造扩展名的负例应拒绝或失败')

    def test_blank_negative_pdf_cannot_report_success(self):
        """QFA-001：异常样本契约明确不允许空白负例返回成功。"""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'synthetic-blank.pdf'
            with fitz.open() as pdf:
                pdf.new_page()
                pdf.save(path)
            try:
                with DocumentParser() as parser:
                    result = parser.parse(path)
            except IngestionError:
                return
            self.assertNotEqual(result.parsing_status, 'success',
                                '空白负例不能仅附复核告警仍报告解析成功')

    def test_native_docx_preserves_vertical_merge_span(self):
        """QFA-002：DOCX 表格结构必须表达 OOXML 已声明的纵向合并。"""
        xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body><w:tbl><w:tblGrid><w:gridCol w:w="1000"/></w:tblGrid>
<w:tr><w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr><w:p><w:r><w:t>合成单元格</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr><w:p/></w:tc></w:tr>
</w:tbl></w:body></w:document>'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'synthetic-merge.docx'
            with ZipFile(path, 'w') as archive:
                archive.writestr('word/document.xml', xml)
            with DocumentParser() as parser:
                result = parser.parse(path)
            cells = result.pages[0].tables[0].cells
            self.assertEqual(len(cells), 1, '合并后的逻辑单元格应仅有一个锚点')
            self.assertEqual(cells[0]['rowspan'], 2)


if __name__ == '__main__':
    unittest.main()
