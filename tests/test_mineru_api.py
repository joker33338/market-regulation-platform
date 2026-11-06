"""Authenticated real FastAPI endpoints, with an injected synthetic transport."""
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "Install optional requirements-api.txt in an isolated environment")
class MinerUAPITests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from qa_core.document_parsing.mineru_api import create_app
        from qa_core.document_parsing.mineru_config import MinerUConfig
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        config = MinerUConfig(enabled=True, result_dir=Path(self.temp.name), poll_interval=0, max_polls=3)
        self.headers = {"Authorization": "Bearer " + "a" * 32}
        self.other = {"Authorization": "Bearer " + "b" * 32}
        self.app = create_app(config, tokens={"a" * 32: "alice", "b" * 32: "bob"})
        self.client = self.enterContext(TestClient(self.app))

    def upload(self, headers=None, content=b"%PDF-1.7 synthetic", name="example.pdf"):
        return self.client.post("/api/parse/files", params={"file_name": name}, content=content,
                                headers=headers or self.headers)

    def task(self, file_id, key="stable-request"):
        return self.client.post("/api/parse/tasks", json={"file_ids": [file_id]},
                                headers={**self.headers, "Idempotency-Key": key})

    def test_upload_submit_poll_results_and_duplicate_identity(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        fid = response.json()["file_id"]
        created = self.task(fid)
        self.assertEqual(created.status_code, 202, created.text)
        tid = created.json()["task_id"]
        self.assertEqual(self.task(fid).json()["task_id"], tid)
        result = None
        for _ in range(50):
            result = self.client.get(f"/api/parse/tasks/{tid}", headers=self.headers).json()
            if result["status"] in {"completed", "failed"}:
                break
            time.sleep(0.02)
        self.assertEqual(result["status"], "completed", result)
        output = self.client.get(f"/api/parse/tasks/{tid}/results", headers=self.headers)
        self.assertEqual(output.status_code, 200)
        payload = output.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertTrue(payload["results"][0]["document"]["quality"]["mock"])
        for private in ("source_path", "file_path", "result_path", "upload", "synthetic-key"):
            self.assertNotIn('"' + private + '"', output.text)

    def test_auth_and_cross_owner_isolation_for_all_routes(self):
        denied = self.client.post("/api/parse/files", params={"file_name": "example.pdf"}, content=b"%PDF-1")
        self.assertEqual(denied.status_code, 401)
        fid = self.upload().json()["file_id"]
        response = self.client.post("/api/parse/tasks", json={"file_ids": [fid]},
                                    headers={**self.other, "Idempotency-Key": "other"})
        self.assertEqual(response.status_code, 400)
        tid = self.task(fid).json()["task_id"]
        for route in ("", "/results", "/errors", "/resume", "/cancel"):
            method = self.client.post if route in {"/resume", "/cancel"} else self.client.get
            self.assertEqual(method(f"/api/parse/tasks/{tid}{route}", headers=self.other).status_code, 404)

    def test_input_validation_and_idempotency_conflict(self):
        self.assertEqual(self.upload(content=b"", name="a.pdf").status_code, 400)
        self.assertEqual(self.upload(content=b"not pdf").status_code, 415)
        self.assertEqual(self.upload(name="../escape.pdf").status_code, 400)
        self.assertEqual(self.upload(name="a.exe").status_code, 415)
        fid = self.upload().json()["file_id"]
        self.assertEqual(self.task(fid).status_code, 202)
        other = self.upload(content=b"%PDF-1.7 different").json()["file_id"]
        self.assertEqual(self.task(other).status_code, 409)
        invalid = self.client.post("/api/parse/tasks", content=b"invalid", headers=self.headers)
        self.assertEqual(invalid.status_code, 400)

    def test_no_auth_configuration_refuses_app_creation(self):
        from qa_core.document_parsing.mineru_api import create_app
        from qa_core.document_parsing.mineru_client import MinerUError
        with self.assertRaises(MinerUError):
            create_app(tokens={})

    def test_upload_page_is_served_and_has_no_embedded_credentials(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("上传并解析入库", response.text)
        self.assertNotIn("Bearer " + "a" * 32, response.text)
        self.assertNotIn("MINERU_API_KEY", response.text)
