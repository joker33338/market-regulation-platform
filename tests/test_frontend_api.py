"""前端查询契约的合成请求测试；仅使用临时目录、SQLite 及模拟 PostgreSQL 游标。"""
import asyncio
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from qa_core.api.common import FrontendReader
from qa_core.api.read_store import ReviewReader
from qa_core.document_parsing.mineru_api import create_app
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.schemas import DocumentResult, LayoutBlock, PageResult
from qa_core.storage.database import Database


class FrontendAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = MinerUConfig(enabled=True, result_dir=self.root, poll_interval=0, max_polls=3)
        self.app = create_app(self.config, tokens={"a" * 32: "alice", "b" * 32: "bob"})
        # 不启动后台 worker，测试明确驱动模拟任务，不存在真实云端请求或模型加载。
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.service = self.app.state.service
        self.addCleanup(lambda: asyncio.run(self.service.client.close()))
        self.reader = self.app.state.frontend_reader
        self.auth = {"Authorization": "Bearer " + "a" * 32}
        self.other = {"Authorization": "Bearer " + "b" * 32}
        self.data = b"%PDF-1.7 synthetic original bytes"


    def get(self, path, **kwargs):
        return self.client.get(path, headers=self.auth, **kwargs)


    def upload_task(self, key="synthetic-request"):
        upload = self.client.post("/api/parse/files", params={"file_name": "合成样本.pdf"},
                                  content=self.data, headers=self.auth)
        self.assertEqual(upload.status_code, 201, upload.text)
        fid = upload.json()["file_id"]
        task = self.client.post("/api/parse/tasks", json={"file_ids": [fid]},
                                headers={**self.auth, "Idempotency-Key": key})
        self.assertEqual(task.status_code, 202, task.text)
        return fid, task.json()


    def test_upload_history_task_mapping_and_idempotency(self):
        fid, task = self.upload_task()
        tid = task["task_id"]
        rows = self.get("/api/documents").json()
        self.assertEqual(rows["total"], 1)
        self.assertEqual(rows["list"][0]["latest_task_id"], tid)
        self.assertEqual(rows["list"][0]["sha256"], hashlib.sha256(self.data).hexdigest())
        history = self.get(f"/api/documents/{fid}/parse-history").json()["list"][0]
        self.assertEqual(history["source_file_id"], fid)
        self.assertNotEqual(history["file_id"], fid)
        repeat = self.client.post("/api/parse/tasks", json={"file_ids": [fid]},
                                  headers={**self.auth, "Idempotency-Key": "synthetic-request"})
        self.assertEqual(repeat.json()["task_id"], tid)
        self.assertEqual(self.get("/api/parse/tasks").json()["total"], 1)
        self.assertEqual(self.get("/api/parse/tasks?status=completed").json()["total"], 0)
        asyncio.run(self.service.run(tid))
        self.assertEqual(self.get("/api/parse/tasks?status=completed").json()["total"], 1)
        self.assertEqual(self.get(f"/api/parse/tasks/{tid}/results").status_code, 200)
        result = self.get(f"/api/documents/{fid}").json()
        self.assertIn(result["status"], {"completed", "pending_review"})


    def test_original_bytes_range_head_and_owner_isolation(self):
        fid, task = self.upload_task()
        path = f"/api/parse/files/{fid}/source"
        original = self.get(path)
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.content, self.data)
        self.assertEqual(original.headers["x-sha256"], hashlib.sha256(self.data).hexdigest())
        part = self.client.get(path, headers={**self.auth, "Range": "bytes=2-7"})
        self.assertEqual(part.status_code, 206)
        self.assertEqual(part.content, self.data[2:8])
        self.assertEqual(part.headers["content-range"], f"bytes 2-7/{len(self.data)}")
        self.assertEqual(self.client.head(path, headers=self.auth).content, b"")
        for target in (path, f"/api/documents/{fid}", f"/api/documents/{fid}/parse-history"):
            self.assertEqual(self.client.get(target, headers=self.other).status_code, 404)
            self.assertEqual(self.client.get(target).status_code, 401)
        self.assertEqual(self.client.get("/api/documents", headers=self.other).json()["total"], 0)
        self.assertEqual(self.client.get("/api/parse/tasks", headers=self.other).json()["total"], 0)


    def test_source_integrity_and_tampered_metadata_are_rejected(self):
        fid, _ = self.upload_task()
        metadata = self.reader.root("alice") / (fid + ".json")
        value = json.loads(metadata.read_text())
        Path(value["path"]).write_bytes(b"different")
        self.assertEqual(self.get(f"/api/parse/files/{fid}/source").status_code, 409)
        value["path"] = str(self.root / "not-an-upload.pdf")
        metadata.write_text(json.dumps(value))
        self.assertEqual(self.get(f"/api/parse/files/{fid}/source").status_code, 404)


    def test_paging_validation_empty_and_auth_contract(self):
        self.assertEqual(self.get("/api/documents").json()["list"], [])
        self.assertEqual(self.get("/api/parse/tasks?page=100").json()["list"], [])
        for query in ("page=0", "page_size=101", "page=bad"):
            self.assertEqual(self.get("/api/documents?" + query).status_code, 422)
        for target in ("/api/documents", "/api/parse/tasks",
                       "/api/review", "/api/knowledge/versions", "/api/openapi.json"):
            self.assertEqual(self.client.get(target).status_code, 401, target)

    def test_preview_reuses_structure_without_writes(self):
        fid, task = self.upload_task()
        tid, file_id = task["task_id"], task["files"][0]["file_id"]
        stored = self.service.repository.get(tid)
        directory = self.root / tid / file_id
        directory.mkdir(parents=True)
        result = DocumentResult("synthetic-document", "合成法规.pdf", "pdf", {}, pages=[
            PageResult(1, "native_pdf", raw_text="第一条 合成规范。", layout_blocks=[
                LayoutBlock("block-1", "text", "第一条 合成规范。")])])
        (directory / "normalized.json").write_text(result.to_json(), encoding="utf-8")
        stored["files"][0]["result_path"] = str(directory)
        self.service.repository.save(stored)
        url = f"/api/parse/tasks/{tid}/files/{file_id}/preview"
        before = self.service.repository.get(tid)
        response = self.client.post(url, headers=self.auth, json={"document_type": "law"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["write_performed"])
        self.assertTrue(response.json()["preview"]["chunks"])
        self.assertEqual(self.service.repository.get(tid), before)
        self.assertEqual(self.client.post(url, headers=self.other, json={"document_type": "law"}).status_code, 404)


    def test_review_reader_ownership_no_finding_view_and_no_write_api(self):
        review = MagicMock()
        review.listing.return_value = {"list": [{"parse_id": "p", "requires_review": True}],
                                       "total": 1, "page": 1, "page_size": 20,
                                       "source": "document_review.documents"}
        review.detail.return_value = dict(parse_id="p", document_id="different-document-id", file_name="合成.pdf",
             parsing_status="needs_review", requires_review=True, source_location={"owner_id": "alice"},
             quality={}, raw_text="合成文本", markdown_content="合成文本", original_result={"pages": []})
        self.reader.review = review
        self.assertEqual(self.get("/api/review").json()["total"], 1)
        review.listing.assert_called_once_with("alice", 1, 20, True)
        detail = self.get("/api/review/p")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertFalse(detail.json()["review_write_supported"])
        self.assertFalse(detail.json()["local_candidate_available"])
        self.assertEqual(self.client.post("/api/review/p/approve", headers=self.auth).status_code, 404)
        connection, cursor = MagicMock(), MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.return_value = {"total": 0}
        cursor.fetchall.return_value = []
        with patch("psycopg2.connect", return_value=connection):
            ReviewReader("never-connected").listing("alice", 1, 20, True)
        connection.set_session.assert_called_once_with(readonly=True, isolation_level="REPEATABLE READ")
        queries = [(call.args[0], call.args[1] if len(call.args) > 1 else None)
                   for call in cursor.execute.call_args_list]
        self.assertTrue(all("owner_id" in sql and "alice" in args for sql, args in queries[1:]))
        self.assertNotIn("v_review_queue", str(queries))
        connection.close.assert_called_once()


    def test_empty_kb_does_not_load_embeddings_and_is_read_only(self):
        kb = self.root / "isolated.sqlite3"
        with nullcontext(Database(sqlite_path=kb)) as database:
            database.initialize()
            database.close()
        self.reader.kb_factory = lambda: Database(sqlite_path=kb)
        before = kb.read_bytes()
        self.assertEqual(self.get("/api/knowledge/versions").json()["total"], 0)
        self.assertEqual(self.get("/api/knowledge/versions/none").status_code, 404)
        self.assertEqual(kb.read_bytes(), before)
