"""汇编拆分只提出建议，确认后按真实字符范围生成副本。"""
from copy import deepcopy
import hashlib
import unittest

from qa_core.api.source_segments import suggest_segments, slice_result
from qa_core.document_parsing.schemas import DocumentResult, PageResult, LayoutBlock
from qa_core.document_parsing.mineru_client import MinerUError


class SourceSegmentTests(unittest.TestCase):
    def result(self):
        text="合成甲管理办法\n第一条 甲正文。\n合成乙管理条例\n第一条 乙正文。"
        return DocumentResult("a"*64,"合成汇编.pdf","pdf",{},pages=[
            PageResult(1,"synthetic",raw_text=text,layout_blocks=[LayoutBlock("block","text",text)])])

    def test_suggestions_keep_real_ranges_and_require_confirmation(self):
        result=self.result();parts=suggest_segments(result.raw_text)
        self.assertEqual(len(parts),2)
        self.assertTrue(all(part["requires_confirmation"] for part in parts))
        self.assertIn("甲正文",result.raw_text[parts[0]["start"]:parts[0]["end"]])
        self.assertNotIn("乙正文",result.raw_text[parts[0]["start"]:parts[0]["end"]])

    def test_same_page_parts_preserve_original_block_and_source_positions(self):
        result=self.result();before=deepcopy(result.to_dict())
        part=suggest_segments(result.raw_text)[1]
        selected=slice_result(result,part)
        self.assertIn("乙正文",selected.raw_text)
        self.assertNotIn("甲正文",selected.raw_text)
        self.assertEqual(selected.pages[0].page_number,1)
        self.assertEqual(selected.pages[0].layout_blocks[0].source_location["original_block_id"],"block")
        self.assertEqual(result.to_dict(),before)

    def test_stale_text_or_out_of_bounds_scope_is_rejected(self):
        result=self.result();part=suggest_segments(result.raw_text)[0]
        part["expected_text_sha256"]="0"*64
        with self.assertRaises(MinerUError):slice_result(result,part)
        part["expected_text_sha256"]=hashlib.sha256(result.raw_text.encode()).hexdigest()
        part["end"]=len(result.raw_text)+1
        with self.assertRaises(MinerUError):slice_result(result,part)
