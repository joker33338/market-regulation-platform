"""纯合成双栏文档回归：增强失败时不得丢弃已有原生正文。"""
from pathlib import Path
import tempfile
import unittest
import fitz

from qa_core.document_parsing.document_router import DocumentParser, looks_multicolumn
from qa_core.document_parsing.native import pdf_page
from qa_core.utils import IngestionError


class RejectingEnhancement:
    def __init__(self):
        self.calls=[]

    def predict(self,method,path):
        self.calls.append(method)
        raise IngestionError('合成结构增强失败')

    def close(self):
        pass


class NativePreservationTests(unittest.TestCase):
    def test_Q021_001_failed_structure_keeps_readable_native_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic-columns.pdf'
            with fitz.open() as pdf:
                page=pdf.new_page(width=600,height=800)
                page.insert_textbox(fitz.Rect(40,40,260,300),'LEFTMARK\n'+('Native left column.\n'*6),fontsize=12)
                page.insert_textbox(fitz.Rect(340,40,560,300),'RIGHTMARK\n'+('Native right column.\n'*6),fontsize=12)
                pdf.save(path)
            with fitz.open(path) as pdf:
                self.assertTrue(looks_multicolumn(pdf[0]))
                native=pdf_page(pdf[0],1,{})
                self.assertFalse(native.tables)
                self.assertIn('LEFTMARK',native.raw_text)
                self.assertIn('RIGHTMARK',native.raw_text)
            runtime=RejectingEnhancement()
            with DocumentParser(runtime=runtime) as parser:
                result=parser.parse(path)
            self.assertEqual(runtime.calls,['structure'])
            retained=result.raw_text+' '+str(result.pages[0].raw_result)
            self.assertIn('LEFTMARK',retained,'已有原生正文应作为可追溯候选保留，增强失败不能清空')
            self.assertIn('RIGHTMARK',retained)
            self.assertTrue(result.requires_review,'回退保留不等于免除人工复核')
            diagnosis=str(result.pages[0].warnings)+' '+str(result.pages[0].raw_result)+' '+str(result.pages[0].error_message)
            self.assertIn('合成结构增强失败',diagnosis,'增强失败原因必须可追溯')


if __name__=='__main__':
    unittest.main()
