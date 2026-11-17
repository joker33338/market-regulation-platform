"""案例正式切分扩展：保留来源、不把引用条文当作法规。"""
import unittest
from qa_core.document_parsing.case_bridge import to_case_document
from qa_core.document_parsing.schemas import DocumentResult, LayoutBlock, PageResult
from qa_core.indexing.service import prepare_document
from qa_core.utils import IngestionError


class CaseIngestionTests(unittest.TestCase):
    def result(self):
        text = "行政处罚决定书\n当事人：合成主体。\n违法事实\n该主体存在合成违法行为。\n处罚依据\n依据某法第一条规定。\n处罚决定\n给予警告。"
        return DocumentResult("a"*64, "合成案例.pdf", "pdf", {}, pages=[
            PageResult(1, "synthetic", raw_text=text,
                       layout_blocks=[LayoutBlock("body", "text", text)])])

    def test_case_is_retrievable_as_case_material_with_full_source_spans(self):
        result = self.result()
        before = result.to_dict()
        doc = to_case_document(result, reviewer="reviewer", title="合成处罚案例", business_id="case-1")
        _, _, chunks, metadata = prepare_document(doc, model_signature="synthetic", max_chars=200)
        self.assertEqual(metadata["document_type"], "case")
        self.assertTrue(chunks)
        self.assertTrue(all(c.metadata["document_type"] == "case" for c in chunks))
        self.assertTrue(all(c.metadata["evidence_kind"] == "case_material" for c in chunks))
        self.assertTrue(all(c.metadata["source_spans"] for c in chunks))
        self.assertTrue(any("依据某法第一条规定" in c.content for c in chunks))
        self.assertEqual(result.to_dict(), before)

    def test_case_does_not_require_normative_article_headings(self):
        result = self.result()
        doc = to_case_document(result, reviewer="reviewer", title="合成案例", business_id="case-1")
        self.assertEqual(prepare_document(doc, model_signature="synthetic", max_chars=200)[3]["quality"]["passed"], True)

    def test_failed_and_missing_body_cases_fail_closed(self):
        result = self.result()
        result.parsing_status = "failed"
        with self.assertRaises(IngestionError):
            to_case_document(result, reviewer="reviewer", title="合成案例", business_id="case-1")

    def test_different_review_snapshots_do_not_reuse_an_old_provenance_revision(self):
        doc=to_case_document(self.result(),reviewer="reviewer",title="合成案例",business_id="case-1")
        doc.metadata["api_review_reference"]={"parse_id":"parse-a","version":1}
        first=prepare_document(doc,model_signature="synthetic",max_chars=200)[1]
        doc.metadata["api_review_reference"]={"parse_id":"parse-b","version":2}
        second=prepare_document(doc,model_signature="synthetic",max_chars=200)[1]
        self.assertNotEqual(first,second)
