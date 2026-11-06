from __future__ import annotations

import contextlib
import io
import json
import math
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from qa_core.config.settings import Settings
from qa_core.indexing.chunking import bounded_parts
from qa_core.indexing.document_loaders import load_file
from qa_core.indexing.legal_structure import parse_articles
from qa_core.indexing.models import LegalDocument, SourceLine
from qa_core.indexing.ocr_documents import approve_candidate
from qa_core.indexing.ocr_review import read_review, review_path
from qa_core.indexing.service import ingest_documents, prepare_document
from qa_core.indexing.source_adapters import _document, source_sql
from qa_core.retrieval.models import DemoEmbeddings, HTTPEmbeddings, validate_vectors
from qa_core.storage.database import Database
from qa_core.utils import IngestionError, file_sha256, stable_hash
from scripts.ingest_legal_documents import main
from query import ask

SAMPLE = """测试办法
第一章 总则
第一节 范围
第一条 第一自然段。
第二自然段。
第二条 有下列情形之一的：
（一）甲情形；
（二）乙情形。
前款情形应当记录。
第二条之一 补充内容。
"""


def document(text=SAMPLE, law_id=None):
    return LegalDocument("测试办法", stable_hash(text), "test.txt",
                         [SourceLine(line, 1, i) for i, line in enumerate(text.splitlines(), 1)],
                         law_id=law_id)


class CountingEmbeddings(DemoEmbeddings):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def embed_documents(self, texts):
        self.calls += len(texts)
        return super().embed_documents(texts)


class ParserTests(unittest.TestCase):
    def test_hierarchy_paragraph_items_and_article_suffix(self):
        articles = parse_articles(document().lines)
        self.assertEqual([item.article_no for item in articles], ["第一条", "第二条", "第二条之一"])
        self.assertEqual(articles[0].chapter, "第一章 总则")
        self.assertEqual(articles[0].section, "第一节 范围")
        self.assertEqual([unit.paragraph_no for unit in articles[1].units], [1, 1, 1, 2])
        self.assertEqual([unit.item_no for unit in articles[1].units], [None, "（一）", "（二）", None])

    def test_pdf_continuation_spans_pages(self):
        articles = parse_articles([SourceLine("第一条 跨页", 1, 1), SourceLine("续文。", 2, 1, False)])
        self.assertEqual(articles[0].units[0].text, "跨页续文。")
        self.assertEqual([span["page"] for span in articles[0].units[0].spans], [1, 2])

    def test_duplicate_article_and_table_of_contents_blocked(self):
        for text in ["第一条 正文\n第一条 重复", "目录\n第一条 示例"]:
            with self.subTest(text=text), self.assertRaises(IngestionError):
                parse_articles(document(text).lines)

    def test_long_single_sentence_is_bounded(self):
        text = "第一条 " + "甲" * 500
        _, _, chunks, _ = prepare_document(document(text), model_signature="test", max_chars=64)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.content) <= 64 for chunk in chunks))
        self.assertEqual("".join(chunk.content.split(" ", 1)[1] for chunk in chunks), "甲" * 500)
        self.assertEqual(len({chunk.metadata["parent_article_id"] for chunk in chunks}), 1)

    def test_same_text_in_different_articles_keeps_distinct_ids(self):
        _, _, chunks, _ = prepare_document(document("第一条 相同。\n第二条 相同。"),
                                           model_signature="test", max_chars=800)
        self.assertEqual(len({chunk.chunk_id for chunk in chunks}), 2)

    def test_chunking_never_crosses_articles(self):
        _, _, chunks, _ = prepare_document(document(), model_signature="test", max_chars=64)
        self.assertTrue(all(len({span["page"] for span in chunk.metadata["source_spans"]}) == 1 for chunk in chunks))
        self.assertTrue(all(chunk.content.startswith(chunk.article_no) for chunk in chunks))

    def test_small_limit_is_rejected(self):
        with self.assertRaises(IngestionError):
            bounded_parts("abc", 12)

    def test_database_source_preserves_ids_and_chapter(self):
        doc = _document([{"source_id": 10, "law_name": "测试办法", "detail_id": 20,
                          "chapter": "原始标题", "article_no": "第一条",
                          "content": "第一条 正文。\n（一）事项。"}], "source")
        self.assertEqual(doc.law_id, "source:10")
        self.assertEqual(doc.articles[0].chapter, "原始标题")
        self.assertEqual(doc.articles[0].units[0].spans[0]["source_record_id"], "20")

    def test_source_table_identifier_injection_rejected(self):
        with self.assertRaises(IngestionError):
            source_sql("laws;DELETE", "details")

    def test_database_source_preserves_preface_and_uses_explicit_hierarchy(self):
        rows = [{"source_id": 10, "law_name": "测试办法", "detail_id": index,
                 "chapter": "测试办法", "article_no": number, "content": content}
                for index, (number, content) in enumerate([
                    ("前言", "修订记录。"), ("第一编", "总编"), ("第一章", "总则"),
                    ("第一节", "适用范围"), ("第一条", "正文。"),
                    ("第二章", "管理"), ("第二条", "管理正文。")], 1)]
        doc = _document(rows, "source")
        self.assertEqual([article.article_no for article in doc.articles], ["第一条", "第二条"])
        self.assertEqual(doc.articles[0].part, "第一编 总编")
        self.assertEqual(doc.articles[0].chapter, "第一章 总则")
        self.assertEqual(doc.articles[0].section, "第一节 适用范围")
        self.assertEqual(doc.articles[1].chapter, "第二章 管理")
        self.assertEqual(doc.articles[1].section, "")
        self.assertEqual(doc.articles[0].units[0].spans[0]["source_record_id"], "5")
        self.assertEqual(doc.metadata["non_article_records"][0]["content"], "修订记录。")

    def test_database_source_rejects_unrecognized_number_and_heading_only_law(self):
        for number in ["未知记录", "第一章"]:
            with self.subTest(number=number), self.assertRaises(IngestionError):
                _document([{"source_id": 10, "law_name": "测试办法", "detail_id": 1,
                            "chapter": "", "article_no": number, "content": "内容。"}], "source")


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_file_hash_not_stat_and_move_keeps_revision(self):
        first = self.path / "first.txt"
        first.write_text(SAMPLE, encoding="utf-8-sig")
        initial = load_file(first)
        second = self.path / "renamed.txt"
        second.write_bytes(first.read_bytes())
        _, rev1, _, _ = prepare_document(initial, model_signature="test", max_chars=800)
        _, rev2, _, _ = prepare_document(load_file(second), model_signature="test", max_chars=800)
        self.assertEqual(rev1, rev2)
        old = first.stat()
        first.write_bytes(first.read_bytes().replace("甲".encode(), "丙".encode()))
        os.utime(first, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertNotEqual(initial.source_hash, file_sha256(first))

    def test_docx_paragraph_order_without_dependency(self):
        path = self.path / "document.docx"
        xml = """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body><w:p><w:r><w:t>测试办法</w:t></w:r></w:p>
        <w:p><w:r><w:t>第一条 正文。</w:t></w:r></w:p></w:body></w:document>"""
        with ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", xml)
        self.assertEqual(load_file(path).lines[1].text, "第一条 正文。")

    def test_ocr_approval_bound_to_actual_text(self):
        candidate = self.path / "test_ocr.md"
        candidate.write_text(SAMPLE, encoding="utf-8")
        with self.assertRaises(IngestionError):
            read_review(candidate)
        review_path(candidate).write_text(json.dumps({"status": "pending", "source_sha256": "abc",
                                                      "pages": [{"page": 1}]}), encoding="utf-8")
        approve_candidate(candidate, "tester")
        self.assertEqual(read_review(candidate)["status"], "approved")
        candidate.write_text(SAMPLE + "\n改变", encoding="utf-8")
        with self.assertRaises(IngestionError):
            read_review(candidate)

    def test_default_preview_never_opens_database(self):
        path = self.path / "document.txt"
        path.write_text(SAMPLE, encoding="utf-8")
        with patch("scripts.ingest_legal_documents.open_database") as open_db:
            with contextlib.redirect_stdout(io.StringIO()):
                status = main(["ingest", "--input", str(path)])
            self.assertEqual(status, 0)
            open_db.assert_not_called()


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(sqlite_path=Path(self.temp.name) / "test.sqlite3")
        self.db.initialize()
        self.settings = Settings(embedding_backend="demo", embedding_dimension=32, max_chunk_chars=64)
        self.embed = CountingEmbeddings()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def build(self, version, docs=None, **kwargs):
        return ingest_documents([document()] if docs is None else docs, database=self.db,
                                embeddings=self.embed, settings=self.settings, version=version, **kwargs)

    def test_staged_is_invisible_and_unchanged_skips_embedding(self):
        self.build("v1")
        self.assertIsNone(self.db.active_version())
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM law_chunks")["n"], 0)
        self.db.publish("v1")
        calls = self.embed.calls
        stats = self.build("v2")
        self.assertEqual(self.embed.calls, calls)
        self.assertEqual(stats["chunks_embedded"], 0)
        self.assertEqual(stats["documents_reused"], 1)

    def test_update_removes_tail_fragments_and_rollback_restores(self):
        long_doc = document("第一条 " + "甲" * 300)
        self.build("v1", [long_doc])
        self.db.publish("v1")
        old_count = self.db.one("SELECT COUNT(*) AS n FROM law_chunks")["n"]
        self.assertGreater(old_count, 1)
        self.build("v2", [document("第一条 短正文。")])
        self.db.publish("v2")
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM law_chunks")["n"], 1)
        self.db.publish("v1", rollback=True)
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM law_chunks")["n"], old_count)

    def test_publication_failure_rolls_back_projection_and_pointer(self):
        self.build("v1")
        self.db.publish("v1")
        before = self.db.all("SELECT * FROM law_chunks")
        self.build("v2", [document("第一条 拒绝发布测试。")])
        self.db.execute("""CREATE TRIGGER reject_projection BEFORE INSERT ON law_chunks
            WHEN NEW.content LIKE '%拒绝发布%' BEGIN SELECT RAISE(ABORT, 'test failure'); END""").close()
        with self.assertRaises(Exception):
            self.db.publish("v2")
        self.assertEqual(self.db.active_version(), "v1")
        self.assertEqual(self.db.all("SELECT * FROM law_chunks"), before)

    def test_concurrent_staged_base_cannot_overwrite_new_active(self):
        self.build("v1")
        self.db.publish("v1")
        self.build("v2")
        self.build("v3")
        self.db.publish("v2")
        with self.assertRaises(IngestionError):
            self.db.publish("v3")
        self.assertEqual(self.db.active_version(), "v2")

    def test_partial_inherits_and_full_snapshot_removes_missing_documents(self):
        extra = document("第一条 另一部法律。", law_id="other")
        extra.law_name = "另一部办法"
        self.build("v1", [document(), extra])
        self.db.publish("v1")
        self.build("v2")
        self.db.publish("v2")
        self.assertEqual(self.db.one("SELECT COUNT(DISTINCT law_name) AS n FROM law_chunks")["n"], 2)
        self.build("v3", full_snapshot=True)
        self.db.publish("v3")
        self.assertEqual(self.db.one("SELECT COUNT(DISTINCT law_name) AS n FROM law_chunks")["n"], 1)

    def test_failed_embedding_never_changes_active(self):
        self.build("v1")
        self.db.publish("v1")
        with patch.object(self.embed, "embed_documents", return_value=[]):
            with self.assertRaises(IngestionError):
                self.build("v2", [document("第一条 新正文。")])
        self.assertEqual(self.db.version("v2")["status"], "FAILED")
        self.assertEqual(self.db.active_version(), "v1")

    def test_model_change_requires_full_rebuild(self):
        self.build("v1")
        self.db.publish("v1")
        self.embed.signature = "changed"
        with self.assertRaises(IngestionError):
            self.build("v2")
        self.build("v3", full_snapshot=True)

    def test_title_collision_and_conflicting_input_identity_blocked(self):
        with self.assertRaises(IngestionError):
            self.build("conflict", [document(law_id="a"), document(law_id="b")])
        with self.assertRaises(IngestionError):
            self.build("conflict2", [document(), document(SAMPLE.replace("甲", "丙"))])

    def test_duplicate_copy_deduplicates(self):
        stats = self.build("v1", [document(), document()])
        self.assertEqual(stats["duplicate_inputs"], 1)
        self.assertEqual(stats["documents_seen"], 1)

    def test_unmanaged_legacy_data_is_never_overwritten(self):
        self.db.execute("""INSERT INTO law_chunks(law_name,article_no,seq,content,embedding,updated_at)
            VALUES('旧法','第一条',1,'旧数据','[1]','now')""").close()
        self.build("v1")
        with self.assertRaises(IngestionError):
            self.db.publish("v1")
        self.assertEqual(self.db.one("SELECT content FROM law_chunks")["content"], "旧数据")

    def test_query_citations_and_model_check(self):
        self.build("v1")
        self.db.publish("v1")
        answer = ask("甲情形", stream=False, database=self.db, embeddings=self.embed)
        self.assertIn("article", answer["citations"][0])
        self.assertIn("source_spans", answer["citations"][0])
        self.assertEqual(answer["citations"][0]["source"], "test.txt")
        self.assertEqual(answer["citations"][0]["kb_version"], "v1")
        self.embed.signature = "other-space"
        with self.assertRaises(IngestionError):
            ask("甲情形", stream=False, database=self.db, embeddings=self.embed)

    def test_chapter_only_change_updates_online_metadata(self):
        self.build("v1")
        self.db.publish("v1")
        self.build("v2", [document(SAMPLE.replace("第一章 总则", "第一章 新标题"))])
        self.db.publish("v2")
        self.assertIn("新标题", self.db.one("SELECT chapter FROM law_chunks LIMIT 1")["chapter"])


class EmbeddingContractTests(unittest.TestCase):
    def test_reject_bad_count_dimension_nan_and_zero(self):
        for values, count, dimension in [([], 1, 2), ([[1]], 1, 2),
                                         ([[float("nan"), 1]], 1, 2), ([[0, 0]], 1, 2)]:
            with self.subTest(values=values), self.assertRaises(IngestionError):
                validate_vectors(values, count, dimension)

    def test_http_reorders_valid_indexes_and_rejects_duplicate(self):
        provider = HTTPEmbeddings(base_url="http://localhost/v1", api_key="test", model="test", dimension=2)
        for data, error in [
            ({"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]}, False),
            ({"data": [{"index": 0, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]}, True),
        ]:
            with patch("urllib.request.urlopen", return_value=io.StringIO(json.dumps(data))):
                if error:
                    with self.assertRaises(IngestionError):
                        provider.embed_documents(["a", "b"])
                else:
                    self.assertEqual(provider.embed_documents(["a", "b"]), [[1, 0], [0, 1]])


if __name__ == "__main__":
    unittest.main()

