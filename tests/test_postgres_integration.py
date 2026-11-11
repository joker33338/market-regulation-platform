"""Opt-in test against an explicitly supplied test database, never PG_DSN."""
from __future__ import annotations

import os
import unittest
from uuid import uuid4

from qa_core.config.settings import Settings
from qa_core.indexing.models import LegalDocument, SourceLine
from qa_core.indexing.service import ingest_documents
from qa_core.retrieval.models import DemoEmbeddings
from qa_core.retrieval.store import retrieve
from qa_core.storage.database import Database
from qa_core.utils import stable_hash


@unittest.skipUnless(os.getenv("MVP_TEST_PG_DSN"), "MVP_TEST_PG_DSN not supplied; production databases are not used")
class PostgreSQLIntegration(unittest.TestCase):
    def test_isolated_schema_build_publish_query_rollback(self):
        class TestVectors:
            # Contract fixture, not exposed by the production CLI.
            dimension = 1024
            signature = "test-only-1024"
            def embed_documents(self, texts):
                return DemoEmbeddings(1024).embed_documents(texts)

        schema = "mvp_test_" + uuid4().hex
        database = Database(pg_dsn=os.environ["MVP_TEST_PG_DSN"], kb_schema=schema)
        # Generated identifier consists of a fixed prefix and hex, not user SQL.
        database.execute("CREATE SCHEMA " + schema).close()
        database.execute("SET search_path TO " + schema + ", public").close()
        try:
            database.initialize()
            settings = Settings()
            provider = TestVectors()
            doc = LegalDocument("测试法规", stable_hash("test"), "fixture", [SourceLine("第一条 测试内容。")])
            ingest_documents([doc], database=database, embeddings=provider, settings=settings, version="v1")
            database.publish("v1")
            self.assertEqual(retrieve(database, provider, "测试")[0]["article_no"], "第一条")
            stats = ingest_documents([doc], database=database, embeddings=provider, settings=settings, version="v2")
            self.assertEqual(stats["chunks_embedded"], 0)
            database.publish("v2")
            database.publish("v1", rollback=True)
            self.assertEqual(database.active_version(), "v1")
        finally:
            database.execute("SET search_path TO public").close()
            database.execute("DROP SCHEMA " + schema + " CASCADE").close()
            database.close()

