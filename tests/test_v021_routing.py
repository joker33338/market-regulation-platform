"""专项最小合成路由回归，不读取真实语料或调用云端。"""
import tempfile
from pathlib import Path
import unittest
import fitz
from qa_core.document_parsing.config import ParsingConfig
from qa_core.document_parsing.document_router import DocumentParser
from tests.test_document_parsing import FakeRuntime


class RoutingQualityTests(unittest.TestCase):
    def test_short_visible_text_stays_native(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic.pdf'
            with fitz.open() as pdf:
                p=pdf.new_page();p.insert_text((40,40),'Short native text');pdf.save(path)
            runtime=FakeRuntime()
            with DocumentParser(runtime=runtime) as parser:result=parser.parse(path)
            self.assertEqual(result.pages[0].parsing_method,'native_pdf')
            self.assertEqual(runtime.calls,[])

    def test_blank_page_does_not_load_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic.pdf'
            with fitz.open() as pdf:pdf.new_page();pdf.save(path)
            runtime=FakeRuntime()
            with DocumentParser(runtime=runtime) as parser:result=parser.parse(path)
            self.assertEqual(runtime.calls,[])
            self.assertEqual(result.pages[0].parsing_method,'native_pdf')

    def test_table_models_are_required_only_when_enabled(self):
        self.assertFalse(ParsingConfig().enable_tables)
        self.assertGreater(len(ParsingConfig(enable_tables=True).required_models('structure')),
                           len(ParsingConfig(enable_tables=False).required_models('structure')))


if __name__=='__main__':unittest.main()
