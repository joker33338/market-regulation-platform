"""v0.2.0验收：复用能力可执行；新策略等待绑定真实业务适配器。

场景字典与观察字典仅是QA测试协议，不是现有HTTP请求/响应字段。
适配器通过环境变量显式指定；缺少实现时逐项SKIP，不伪造PASS。
"""
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZipFile


def make_source(root, kind='pdf', text='Synthetic QA document, amount 100, date 2026-11-07.',complex_layout=False):
    path=root/('synthetic.'+kind)
    if kind=='docx':
        with ZipFile(path,'w') as archive:
            archive.writestr('word/document.xml',
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
                +escape(text)+'</w:t></w:r></w:p></w:body></w:document>')
    elif kind=='png':
        from PIL import Image,ImageDraw
        image=Image.new('RGB',(400,200),'white')
        ImageDraw.Draw(image).text((10,40),'Synthetic QA scan',fill='black')
        image.save(path)
    else:
        import fitz
        with fitz.open() as pdf:
            page=pdf.new_page()
            page.insert_text((40,50),text)
            if complex_layout:
                page.insert_text((330,50),'Synthetic second column')
                for y in [150,190,230]:
                    page.draw_line((40,y),(540,y))
                for x in [40,290,540]:
                    page.draw_line((x,150),(x,230))
            pdf.save(path)
    return path


class ExistingCapabilities(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_A_native_word_and_pdf_do_not_invoke_inference(self):
        from qa_core.document_parsing.document_router import DocumentParser
        class NoInference:
            def close(self): pass
            def predict(self,*args): raise AssertionError('原生文档不应调用OCR')
        for kind,method in [('docx','native_docx'),('pdf','native_pdf')]:
            with self.subTest(kind=kind),DocumentParser(runtime=NoInference()) as parser:
                result=parser.parse(make_source(self.root,kind))
                self.assertEqual(result.pages[0].parsing_method,method)
                self.assertTrue(result.raw_text.strip())

    def test_B_existing_scan_route_uses_paddle_ocr(self):
        from qa_core.document_parsing.document_router import DocumentParser
        from tests.test_document_parsing import FakeRuntime
        runtime=FakeRuntime()
        with DocumentParser(runtime=runtime) as parser:
            result=parser.parse(make_source(self.root,'png'))
        self.assertEqual(runtime.calls,['ocr'])
        self.assertEqual(result.pages[0].parsing_method,'ocr')
        self.assertIsNotNone(result.pages[0].confidence)

    def test_C_structure_preserves_layout_and_table(self):
        from qa_core.document_parsing.paddle_structure import PaddleStructureService
        from tests.test_document_parsing import FakeRuntime
        class TableRuntime(FakeRuntime):
            def predict(self,method,path):
                payload=super().predict(method,path)
                payload['raw']['res']['table_res_list']=[{'pred_html':'<table><tr><td>100</td></tr></table>'}]
                return payload
        runtime=TableRuntime()
        result=PaddleStructureService(runtime,True).parse_image('synthetic-not-read',1,{'source_id':'synthetic'})
        self.assertEqual(runtime.calls,['structure'])
        self.assertTrue(result.layout_blocks)
        self.assertEqual(result.tables[0].rows,[['100']])
        self.assertTrue(result.raw_result)

    def test_E_quality_marks_anomalies_without_rewriting_original(self):
        from qa_core.document_parsing.schemas import DocumentResult,PageResult
        from qa_core.document_parsing.quality import assess_document
        original='第一条 金额100元。\n第一条 日期2026年11月7日。'
        result=DocumentResult('synthetic','synthetic.pdf','.pdf',{},pages=[PageResult(1,'ocr',raw_text=original,confidence=0.2)])
        quality=assess_document(result)
        codes={item['code'] for item in quality['findings']}
        self.assertTrue({'low_confidence','duplicate_article_number'}<=codes)
        self.assertTrue(quality['review_required'])
        self.assertEqual(result.raw_text,original)

    def test_J_existing_legal_gate_rejects_mock_and_missing_reviewer(self):
        from qa_core.document_parsing.schemas import DocumentResult,PageResult
        from qa_core.document_parsing.mineru_artifacts import reviewed_legal_document
        from qa_core.document_parsing.bridge import to_legal_document
        result=DocumentResult('synthetic','synthetic.pdf','.pdf',{'file_path':'synthetic'},
                              pages=[PageResult(1,'ocr',raw_text='第一条 合成正文。')],quality={'mock':True})
        with self.assertRaises(ValueError):
            reviewed_legal_document(result,reviewer='qa',law_name='合成法规')
        with self.assertRaises(ValueError):
            to_legal_document(result,reviewer='',law_name='合成法规')


ADAPTER=os.getenv('MARKET_REGULATION_DUAL_ENGINE_TEST_ADAPTER','')


@unittest.skipUnless(ADAPTER,'待Fix实现双引擎后，由QA绑定真实业务测试适配器；不能用参考替身宣称PASS')
class DualEngineAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        # HTTP MockTransport/ASGITransport可用，禁止误走真实HTTP传输。
        self.enterContext(patch('httpx.HTTPTransport.handle_request',side_effect=AssertionError('验收禁止真实外网HTTP')))
        self.enterContext(patch('httpx.AsyncHTTPTransport.handle_async_request',side_effect=AssertionError('验收禁止真实外网HTTP')))
        self.enterContext(patch('urllib.request.urlopen',side_effect=AssertionError('验收禁止真实外网HTTP')))
        module,sep,name=ADAPTER.partition(':')
        if not sep or not module.startswith('tests.'):
            self.fail('适配器必须是已审查的tests.module:function')
        self.run_scenario=getattr(importlib.import_module(module),name)

    def observe(self,case_id,kind='pdf',**options):
        path=make_source(self.root,kind,text=options.get('text','Synthetic QA document.'),
                         complex_layout=options.get('complex_layout',False))
        original=hashlib.sha256(path.read_bytes()).hexdigest()
        scenario={'case_id':case_id,'cloud_mode':'mock','authorized_cloud':False,'sensitive':False,
                  'max_cloud_calls':8,'review_approved':False,**options}
        result=self.run_scenario(scenario,path)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),original,'不得修改原文件')
        self.assertIsInstance(result,dict)
        self.assertEqual(result['source_sha256'],original)
        return result

    def test_A_native_word_and_text_pdf_never_submit_cloud(self):
        for kind in ['docx','pdf']:
            with self.subTest(kind=kind):
                result=self.observe('DE-A',kind,authorized_cloud=True)
                self.assertIn('native',result['engines'])
                self.assertEqual(result['cloud_submissions'],0)

    def test_B_simple_scan_prefers_local_paddle(self):
        result=self.observe('DE-B','png',local_confidence=0.99)
        self.assertIn('paddle_ocr',result['engines'])
        self.assertEqual(result['cloud_submissions'],0)

    def test_C_complex_layout_preserves_structure(self):
        result=self.observe('DE-C',complex_layout=True,authorized_cloud=True)
        self.assertTrue(result['complex_layout_detected'])
        self.assertTrue(result['layout_preserved'])
        self.assertTrue(set(result['engines'])&{'native','pp_structure','mineru_official'})
        self.assertTrue(result['route_reason'])

    def test_D_empty_or_low_quality_requires_permission_before_fallback(self):
        for allowed in [False,True]:
            with self.subTest(allowed=allowed):
                result=self.observe('DE-D','png',local_text='',local_confidence=0.1,authorized_cloud=allowed)
                self.assertTrue(result['warnings'])
                self.assertTrue(result['local_result_preserved'])
                self.assertEqual(result['cloud_submissions'],1 if allowed else 0)

    def test_E_legal_number_amount_date_anomalies_are_review_only(self):
        for anomaly in ['duplicate_article','uncertain_amount','invalid_date']:
            with self.subTest(anomaly=anomaly):
                result=self.observe('DE-E','docx',anomaly=anomaly,text='第一条 金额不确定，日期2026年13月40日。\n第一条 合成重复条号。')
                self.assertTrue(result['review_required'])
                self.assertTrue(result['original_text_preserved'])
                self.assertTrue(result['warnings'])

    def test_F_remote_failures_are_bounded_and_keep_local_output(self):
        for failure in ['timeout','429','500']:
            with self.subTest(failure=failure):
                result=self.observe('DE-F','png',local_confidence=0.1,authorized_cloud=True,remote_failure=failure)
                self.assertLessEqual(result['cloud_calls'],8)
                self.assertLessEqual(result['cloud_submissions'],1)
                self.assertTrue(result['local_result_preserved'])
                self.assertTrue(result['failure_reason'])

    def test_G_default_and_sensitive_files_cannot_export_without_authorization(self):
        for sensitive in [False,True]:
            with self.subTest(sensitive=sensitive):
                result=self.observe('DE-G','png',local_confidence=0.1,sensitive=sensitive)
                self.assertEqual(result['cloud_submissions'],0)
                self.assertTrue(result['local_result_preserved'])

    def test_H_dual_result_provenance_is_complete(self):
        result=self.observe('DE-H','png',local_confidence=0.1,authorized_cloud=True)
        self.assertTrue({'paddle_ocr','mineru_official'}<=set(result['engines']))
        provenance=result['provenance']
        for key in ['route_reason','quality','raw_results','page_numbers','source_file_id','parser_versions']:
            self.assertTrue(provenance[key])
        if any(value is None for value in provenance['parser_versions'].values()):
            self.assertTrue(provenance['version_unavailable_reason'],'版本缺失需明确说明，不能编造')

    def test_I_repeat_and_failure_do_not_duplicate_or_replace_database_rows(self):
        result=self.observe('DE-I',repeat=True,inject_database_failure=True)
        self.assertEqual(result['database_backend'],'isolated_postgres')
        self.assertEqual(result['rows_after_first'],result['rows_after_repeat'])
        self.assertTrue(result['prior_record_preserved'])

    def test_J_review_is_required_before_existing_rag_ingestion(self):
        result=self.observe('DE-J','docx',review_approved=True,text='第一条 合成验收材料。')
        self.assertEqual(result['ingestions_before_review'],0)
        self.assertGreater(result['hits_after_review'],0)
        self.assertTrue(result['source_association_preserved'])
