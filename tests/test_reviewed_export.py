"""整页正文修订只生成副本；旧记录不推定为整页替换。"""
from copy import deepcopy
import unittest
from qa_core.api.reviewed_export import export_reviewed_result
from qa_core.document_parsing.schemas import DocumentResult, PageResult, LayoutBlock
from qa_core.document_parsing.mineru_client import MinerUError


class ReviewedExportTests(unittest.TestCase):
    def source(self):
        result=DocumentResult("a"*64,"合成.pdf","pdf",{},pages=[
            PageResult(1,"synthetic",raw_text="第一条 原正文。",layout_blocks=[LayoutBlock("b","text","第一条 原正文。")]),
            PageResult(2,"synthetic",raw_text="第二条 后页。",layout_blocks=[LayoutBlock("c","text","第二条 后页。")])])
        return {"original_result":result.to_dict(),"raw_text":result.raw_text,"parse_id":"parse"}

    def ledger(self,events):
        class Ledger:
            def events(self,*args): return {"list":events,"total":len(events)}
        return Ledger()

    def test_page_replacement_preserves_original_and_other_pages(self):
        source=self.source();before=deepcopy(source)
        event={"action":"save-revision","revision_id":"rev","version":2,"operator_id":"reviewer",
               "request":{"page":1,"content":"第一条 修订正文。","revision_scope":"page_body_v1"}}
        exported=export_reviewed_result(source,{"current_revision":"rev","version":3},self.ledger([event]),"alice")
        self.assertEqual(exported.pages[0].raw_text,"第一条 修订正文。")
        self.assertEqual(exported.pages[1].raw_text,"第二条 后页。")
        self.assertEqual(source,before)
        self.assertEqual(exported.quality["reviewed_page_revisions"][0]["operator_id"],"reviewer")

    def test_legacy_revision_requires_explicit_confirmation(self):
        event={"action":"save-revision","revision_id":"legacy","version":2,
               "request":{"page":1,"content":"可能只是局部文本"}}
        with self.assertRaises(MinerUError):
            export_reviewed_result(self.source(),{"current_revision":"legacy","version":3},self.ledger([event]),"alice")

    def test_missing_or_mismatched_revision_fails_closed(self):
        with self.assertRaises(MinerUError):
            export_reviewed_result(self.source(),{"current_revision":"missing","version":3},self.ledger([]),"alice")

    def test_replacement_keeps_table_blocks_and_table_structures(self):
        source=self.source()
        source['original_result']['pages'][0]['layout_blocks'].append({'block_id':'table','kind':'table','raw_text':'合成表格','bbox':None,'confidence':None,'reading_order':None,'source_location':{}})
        before=deepcopy(source)
        event={'action':'save-revision','revision_id':'rev','version':1,'operator_id':'reviewer',
               'request':{'page':1,'content':'整页新正文','revision_scope':'page_body_v1'}}
        exported=export_reviewed_result(source,{'current_revision':'rev','version':2},self.ledger([event]),'alice')
        self.assertEqual([block.kind for block in exported.pages[0].layout_blocks],['text','table'])
        self.assertEqual(exported.pages[0].layout_blocks[1].raw_text,'合成表格')
        self.assertEqual(source,before)

    def test_latest_revision_on_each_page_is_selected_without_losing_other_page(self):
        events=[]
        for version,page,content in [(3,1,'第一页最新正文'),(2,2,'第二页修订正文'),(1,1,'第一页旧修订')]:
            events.append({'action':'save-revision','revision_id':'rev'+str(version),'version':version,'operator_id':'person'+str(version),
                           'request':{'page':page,'content':content,'revision_scope':'page_body_v1'}})
        exported=export_reviewed_result(self.source(),{'current_revision':'rev3','version':4},self.ledger(events),'alice')
        self.assertEqual([page.raw_text for page in exported.pages],['第一页最新正文','第二页修订正文'])
        self.assertEqual([item['operator_id'] for item in exported.quality['reviewed_page_revisions']],['person3','person2'])
