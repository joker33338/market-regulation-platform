"""验证跨存储状态合并，不把解析完成当作发布。"""
import unittest
from qa_core.api.workbench_documents import combine_documents


class WorkbenchDocumentTests(unittest.TestCase):
    def base(self):
        return {"file_id": "a"*32, "owner_id": "alice", "file_name": "材料.pdf", "status": "completed"}

    def test_completed_parse_requires_review_even_if_ocr_did_not_raise_warning(self):
        row = combine_documents([self.base()], {"a"*32: {"parse_id": "p"}}, {}, {})[0]
        self.assertEqual(row["stage"], "awaiting_review")

    def test_approval_and_publication_have_distinct_states(self):
        parses = {"a"*32: {"parse_id": "p"}}
        reviews = {"p": {"status": "approved", "version": 2}}
        row = combine_documents([self.base()], parses, reviews, {})[0]
        self.assertEqual(row["stage"], "ready_to_build")
        self.assertEqual(row["review_version"], 2)
        self.assertEqual(combine_documents([self.base()], parses, reviews, {"p": "STAGED"})[0]["stage"], "awaiting_publish")
        self.assertEqual(combine_documents([self.base()], parses, reviews, {"p": "ACTIVE"})[0]["stage"], "published")

    def test_unavailable_review_ledger_never_becomes_approved(self):
        row = combine_documents([self.base()], {"a"*32: {"parse_id": "p"}}, None, {})[0]
        self.assertEqual(row["stage"], "state_unavailable")

    def test_approved_revision_waits_for_build_protocol_validation(self):
        row = combine_documents([self.base()], {"a"*32: {"parse_id": "p"}},
                                {"p": {"status": "approved", "version": 2, "current_revision": "revision"}}, {})[0]
        self.assertEqual(row["stage"], "ready_to_build")
        self.assertIsNone(row["blocked_reason"])

    def test_file_with_two_entries_is_not_fully_published_when_one_is_pending(self):
        import tempfile
        from pathlib import Path
        from qa_core.api.private_operations import OperationStore
        from qa_core.api.principals import Principal
        from qa_core.api.workbench_documents import add_job_metadata
        with tempfile.TemporaryDirectory() as directory:
            store=OperationStore(Path(directory));store.root=store.root.parent/'.file-knowledge-jobs'
            with store.locked():
                for index,status in enumerate(['published','awaiting_publish']):
                    store.save({'operation_id':str(index)*64,'job_id':str(index)*64,'owner_id':'alice','file_id':'a'*32,
                        'source_sha256':'b'*64,'source_parse_id':'p','review_version':2,'title':'篇'+str(index),'document_type':'law',
                        'source_range':{'start':index*10,'end':(index+1)*10},'status':status,
                        'created_at':str(index),'doc_version_id':'dv'+str(index)})
            row={**self.base(),'sha256':'b'*64,'parse_id':'p','review_version':2,'stage':'published',
                 'published_doc_version_ids':['dv0']}
            identity=Principal('person','alice',frozenset({'USER'}),(),'active')
            add_job_metadata([row],identity,Path(directory))
            self.assertEqual(row['stage'],'awaiting_publish')
            self.assertEqual(row['child_document_count'],2)
            self.assertEqual(row['published_document_count'],1)
