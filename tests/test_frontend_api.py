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


    def test_source_integrity_and_tampered_metadata_are_rejected(self):
        fid, _ = self.upload_task()
        metadata = self.reader.root("alice") / (fid + ".json")
        value = json.loads(metadata.read_text())
        Path(value["path"]).write_bytes(b"different")
        self.assertEqual(self.get(f"/api/parse/files/{fid}/source").status_code, 409)
        value["path"] = str(self.root / "not-an-upload.pdf")
        metadata.write_text(json.dumps(value))
        self.assertEqual(self.get(f"/api/parse/files/{fid}/source").status_code, 404)


    def test_document_list_detail_and_existing_task_association(self):
        fid, task = self.upload_task()
        response = self.get("/api/documents?doc_type=pdf&keyword=合成")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["list"][0]["file_id"], fid)
        self.assertEqual(self.get(f"/api/documents/{fid}").json()["latest_task_id"], task["task_id"])
        self.assertEqual(self.get(f"/api/documents/{fid}/parse-history").json()["total"], 1)
        self.assertEqual(self.get("/api/documents?page=0").status_code, 422)
