"""Opt-in existing document_review schema tests; no DDL or data deletion."""
import os
import unittest
from uuid import uuid4

from qa_core.document_parsing.schemas import DocumentResult, PageResult, LayoutBlock
from qa_core.storage.parsing_results import PostgresResultSink
from qa_core.utils import stable_hash


@unittest.skipUnless(os.getenv("PARSING_TEST_PG_DSN"), "Explicit existing test schema required")
class ParsingPostgresTests(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ["PARSING_TEST_PG_DSN"]
        self.task = {"id": uuid4().hex, "owner": "synthetic-qa"}
        self.file = {"id": uuid4().hex}
        self.result = DocumentResult("synthetic-sha", "synthetic-fixture.pdf", ".pdf", {}, pages=[
            PageResult(1, "fixture", raw_text="synthetic database integration", layout_blocks=[LayoutBlock("b", "text", "synthetic")])])

    def count(self, parse_id):
        import psycopg2
        connection = psycopg2.connect(self.dsn)
        try:
            connection.set_session(readonly=True)
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM document_review.documents WHERE parse_id=%s", (parse_id,))
                return cursor.fetchone()[0]
        finally:
            connection.close()

    def test_transactional_insert_idempotency_and_existing_rows_preserved(self):
        sink = PostgresResultSink(self.dsn)
        first = sink.save(self.task, self.file, self.result)
        self.assertEqual(sink.save(self.task, self.file, self.result), first)
        self.assertEqual(self.count(first), 1)

    def test_child_failure_rolls_back_parent_insert(self):
        import psycopg2
        self.result.pages[0].parsing_method = None
        parse_id = stable_hash("parsing-result-v1", self.task["owner"], self.task["id"], self.file["id"])
        with self.assertRaises(psycopg2.IntegrityError):
            PostgresResultSink(self.dsn).save(self.task, self.file, self.result)
        self.assertEqual(self.count(parse_id), 0)
