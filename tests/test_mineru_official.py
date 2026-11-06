"""Public v4 API fixtures, kept separate from self-hosted Tasks fixtures."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import httpx
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_official import OfficialMinerUClient
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService


def official_bundle():
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("full.md", "第一条 合成内容。")
        archive.writestr("synthetic_content_list.json", json.dumps([
            {"type": "text", "text": "第一条 合成内容。", "page_idx": 0, "bbox": [1, 2, 3, 4]}]))
        archive.writestr("layout.json", '{"_version_name":"fixture-worker"}')
    return out.getvalue()


class OfficialClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = MinerUConfig(enabled=True, mode="remote", provider="official", api_url="https://mineru.net/api",
                                   api_key="synthetic-key", result_dir=self.root, poll_interval=0, max_polls=3)

    async def test_public_v4_create_upload_query_download_and_source_association(self):
        calls, manifest = [], []
        uploaded = False
        def handle(request):
            nonlocal uploaded
            calls.append(request.url.path)
            if request.method == "POST":
                self.assertEqual(request.url.path, "/api/v4/file-urls/batch")
                body = json.loads(request.content)
                self.assertEqual(body["model_version"], "vlm")
                self.assertNotIn("tier", body)
                manifest.extend(body["files"])
                return httpx.Response(200, json={"code": 0, "data": {"batch_id": "b", "file_urls": [
                    "https://mineru.oss-cn-shanghai.aliyuncs.com/input"]}})
            if request.method == "PUT":
                self.assertNotIn("Authorization", request.headers)
                uploaded = True
                return httpx.Response(200)
            if request.url.host == "cdn-mineru.openxlab.org.cn":
                self.assertNotIn("Authorization", request.headers)
                return httpx.Response(200, content=official_bundle())
            self.assertEqual(request.headers["Authorization"], "Bearer synthetic-key")
            return httpx.Response(200, json={"code": 0, "data": {"batch_id": "b", "extract_result": [
                {"data_id": manifest[0]["data_id"], "file_name": "a.pdf", "state": "done" if uploaded else "waiting-file",
                 "full_zip_url": "https://cdn-mineru.openxlab.org.cn/result.zip"}]}})
        client = OfficialMinerUClient(self.config, transport=httpx.MockTransport(handle))
        self.addAsyncCleanup(client.close)
        service = MinerUService(self.config, TaskRepository(self.root / "tasks.sqlite3"), client)
        path = self.root / "a.pdf"
        path.write_bytes(b"%PDF-1.7 fixture")
        task = (await service.submit("alice", "request", [("a.pdf", path)]))[0]
        await service.run(task["id"])
        result = service.repository.get(task["id"])
        self.assertEqual(result["status"], "completed", result.get("error"))
        file = result["files"][0]
        self.assertEqual(file["remote_id"], manifest[0]["data_id"])
        value = json.loads((Path(file["result_path"]) / "normalized.json").read_text(encoding="utf-8"))
        self.assertEqual(value["source_location"]["parser_name"], "mineru-official")
        self.assertEqual(value["source_location"]["parser_version"], "fixture-worker")
        self.assertIsNone(value["source_location"]["parsing_tier"])
        self.assertEqual(value["source_location"]["model_version"], "vlm")
        self.assertFalse(any("/v1/tasks" in path for path in calls))

    async def test_http_success_with_api_failure_is_not_success_or_retried(self):
        from qa_core.document_parsing.mineru_client import MinerUError
        calls = []
        def handle(request):
            calls.append(request.method)
            return httpx.Response(200, json={"code": -10001, "msg": "sensitive fixture"})
        client = OfficialMinerUClient(self.config, transport=httpx.MockTransport(handle))
        self.addAsyncCleanup(client.close)
        with self.assertRaisesRegex(MinerUError, "official_api_-10001"):
            await client.create([{"file_name": "a.pdf", "bytes": 1}])
        self.assertEqual(calls, ["POST"])
