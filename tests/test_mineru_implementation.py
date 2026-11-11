"""Production-client acceptance with synthetic HTTP fixtures, never real endpoints."""
import asyncio
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import httpx
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_client import MinerUClient, MinerUError
from qa_core.document_parsing.mineru_artifacts import unpack, normalize_artifacts, reviewed_legal_document
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService
from qa_core.document_parsing.mineru_mock import mock_transport


def bundle(extra=None, text="第一条 合成法规用于测试。", table=False):
    content = {"pages": [{"page_idx": 2, "blocks": [{"type": "text", "content": text}]}]}
    if table:
        content["pages"][0]["blocks"].append({"type": "table", "content": "<table><tr><td>金额</td></tr></table>"})
    values = {"markdown.md": text, "middle_json.json": '{"schema":"docvortex.middle","schema_version":"2.0"}',
              "structured_content.json": json.dumps(content), **(extra or {})}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, value in values.items():
            member = zipfile.ZipInfo(name)
            # Windows 构造 ZipInfo 时会规范化分隔符；保留
            # 恶意原始名称，确保实际覆盖生产校验器。
            member.filename = name
            archive.writestr(member, value)
    return out.getvalue()


class ProductionClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = MinerUConfig(enabled=True, api_url="https://api.invalid/proxy", poll_interval=0,
                                   max_polls=3, result_dir=self.root, allowed_origins=("https://store.invalid",))

    def client(self, handler, config=None):
        client = MinerUClient(config or self.config, transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(client.close)
        return client

    async def test_create_manifest_and_no_retry_on_every_error(self):
        for status in (400, 401, 429, 500):
            calls = []
            def handle(request):
                calls.append(request)
                body = json.loads(request.content)
                self.assertEqual(body["tier"], "standard")
                self.assertNotIn("file_id", body["files"][0])
                return httpx.Response(status, json={"error": {"message": "secret", "code": "test"}})
            with self.assertRaises(MinerUError) as caught:
                await self.client(handle).create([{"file_name": "a.pdf", "bytes": 3}])
            self.assertEqual(len(calls), 1)
            self.assertNotIn("secret", str(caught.exception))

    async def test_uncertain_post_timeout_does_not_retry(self):
        calls = []
        def handle(request):
            calls.append(request)
            raise httpx.ReadTimeout("synthetic", request=request)
        with self.assertRaises(httpx.ReadTimeout):
            await self.client(handle).create([{"file_name": "a.pdf", "bytes": 1}])
        self.assertEqual(len(calls), 1)

    async def test_cache_and_waiting_without_upload_skip_put(self):
        client = self.client(lambda r: self.fail("Unexpected traffic"))
        for status in ("pending", "running", "completed", "waiting-file"):
            self.assertFalse(await client.upload({"status": status}, self.root / "absent"))

    async def test_origin_and_redirect_auth_and_proxy_encoded_id(self):
        calls = []
        def handle(request):
            calls.append(request)
            if request.url.host == "api.invalid":
                self.assertEqual(request.headers["Authorization"], "Bearer synthetic-key")
                return httpx.Response(302, headers={"location": "https://store.invalid/result"})
            self.assertNotIn("authorization", request.headers)
            return httpx.Response(200, content=bundle())
        client = self.client(handle, replace(self.config, api_key="synthetic-key"))
        self.assertTrue(await client.download({"result_url": "https://api.invalid/result"}))
        self.assertEqual(len(calls), 2)
        with self.assertRaises(MinerUError):
            await client.download({"result_url": "https://untrusted.invalid/result"})
        paths = []
        client2 = self.client(lambda r: (paths.append(r.url.raw_path) or httpx.Response(200, json={})))
        await client2.detail("a/b")
        await client2.health()
        await client2.tiers()
        self.assertEqual(paths, [b"/proxy/v1/tasks/a%2Fb", b"/proxy/v1/health", b"/proxy/v1/tiers"])

    async def test_bounded_download_and_upload_expiry(self):
        client = self.client(lambda r: httpx.Response(200, content=b"x" * 100), replace(self.config, max_result_bytes=20))
        with self.assertRaisesRegex(MinerUError, "response_too_large"):
            await client.download({"result_url": "https://store.invalid/result"})
        with self.assertRaisesRegex(MinerUError, "upload_expired"):
            await client.upload({"status": "waiting-file", "upload": {"expires_at": 1}}, self.root / "absent")

    async def test_config_and_manifest_reject_unsafe_inputs(self):
        with self.assertRaises(ValueError):
            MinerUConfig(mode="remote")
        with self.assertRaises(MinerUError):
            MinerUClient(self.config)
        client = self.client(lambda r: self.fail("Bad manifests must not reach network"))
        for name, size in [("../x.pdf", 1), ("C:x.pdf", 1), ("a.pdf", 0), ("a.pdf", True), ("a.pdf", 10**15)]:
            with self.assertRaises(MinerUError):
                await client.create([{"file_name": name, "bytes": size}])

    async def test_archive_security_complete_artifacts_and_resource_bounds(self):
        for name in ("../escape.md", "/escape.md", "C:/escape.md", "images\\x.png", "images/CON.png"):
            with self.subTest(name=name), self.assertRaises(MinerUError):
                unpack(bundle({name: "synthetic"}), self.config)
        for payload in (b"notzip", bundle({"markdown.md": "x"})[:-5]):
            with self.assertRaises(MinerUError):
                unpack(payload, self.config)
        with self.assertRaises(MinerUError):
            unpack(bundle(), replace(self.config, max_expanded_bytes=10))
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("result.md", "x")
        with self.assertRaisesRegex(MinerUError, "incomplete_artifacts"):
            unpack(out.getvalue(), self.config)

    def service(self, handler=None, config=None):
        config = config or self.config
        client = self.client(handler) if handler else MinerUClient(replace(config, api_url=""), transport=mock_transport())
        if not handler:
            config = replace(config, api_url="")
            self.addAsyncCleanup(client.close)
        return MinerUService(config, TaskRepository(self.root / "tasks.sqlite3"), client)

    async def input(self, service, key="request", name="a.pdf"):
        path = self.root / name
        path.write_bytes(b"%PDF-1.7 synthetic")
        return (await service.submit("alice", key, [(name, path)]))[0]

    async def test_mock_full_lifecycle_idempotency_persistence_and_result_identity(self):
        service = self.service()
        task = await self.input(service)
        repeated = await self.input(service)
        self.assertEqual(task["id"], repeated["id"])
        await service.run(task["id"])
        result = TaskRepository(self.root / "tasks.sqlite3").get(task["id"], "alice")
        self.assertEqual(result["status"], "completed")
        file = result["files"][0]
        self.assertTrue(file["remote_id"])
        normalized = json.loads((Path(file["result_path"]) / "normalized.json").read_text(encoding="utf-8"))
        self.assertEqual(normalized["document_id"], file["sha256"])
        self.assertEqual(normalized["source_location"]["parser_name"], "mineru-mock")
        from qa_core.document_parsing.schemas import DocumentResult
        with self.assertRaisesRegex(MinerUError, "mock_result"):
            reviewed_legal_document(DocumentResult.from_dict(normalized), reviewer="test", law_name="synthetic")
        with self.assertRaisesRegex(MinerUError, "task_not_found"):
            service.repository.get(task["id"], "bob")
        with self.assertRaisesRegex(MinerUError, "idempotency_conflict"):
            await self.input(service, name="different.pdf")

    async def test_uncertain_submission_persisted_and_never_recreated(self):
        calls = []
        def handle(request):
            calls.append(request.method)
            raise httpx.ReadTimeout("synthetic", request=request)
        service = self.service(handle)
        task = await self.input(service)
        await service.run(task["id"])
        result = service.repository.get(task["id"])
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["submission_started"])
        await service.run(task["id"])
        self.assertEqual(calls, ["POST"])

    async def test_restart_recovers_existing_remote_task_without_post(self):
        calls = []
        def handle(request):
            calls.append(request.method)
            return httpx.Response(200, json={"task_id": "persisted", "status": "failed", "files": [
                {"file_id": "f", "file_name": "a.pdf", "status": "failed", "error": {"code": "parse_failed"}}]})
        service = self.service(handle)
        task = await self.input(service)
        task.update(remote_id="persisted", submission_started=True, status="running")
        task["files"][0]["remote_id"] = "f"
        service.repository.save(task)
        restarted = MinerUService(service.config, TaskRepository(self.root / "tasks.sqlite3"), service.client)
        await restarted.run(task["id"])
        self.assertEqual(restarted.repository.get(task["id"])["status"], "failed")
        self.assertEqual(calls, ["GET"])

    async def test_running_cancel_is_durable_and_preserves_completed_files(self):
        ready = asyncio.Event()
        canceled = False
        def handle(request):
            nonlocal canceled
            if request.url.path.endswith("/cancel"):
                canceled = True
            if request.method == "GET":
                ready.set()
            return httpx.Response(202 if request.method == "POST" and not canceled else 200,
                json={"task_id": "t", "status": "canceled" if canceled else "running", "files": [
                    {"file_id": "f", "file_name": "a.pdf", "status": "canceled" if canceled else "running"}]})
        service = self.service(handle)
        task = await self.input(service)
        job = asyncio.create_task(service.run(task["id"]))
        await asyncio.wait_for(ready.wait(), 2)
        await service.cancel(task["id"], "alice")
        await job
        result = service.repository.get(task["id"])
        self.assertTrue(result["cancel_requested"])
        self.assertEqual(result["status"], "canceled")

    async def test_atomic_queue_limit_allows_same_request_but_rejects_new_one(self):
        service = self.service()
        service.config = replace(service.config, queue_size=1)
        first = await self.input(service)
        self.assertEqual((await self.input(service))["id"], first["id"])
        with self.assertRaisesRegex(MinerUError, "queue_full"):
            await self.input(service, key="another")

    async def test_source_mutation_is_rejected_before_remote_create(self):
        service = self.service(lambda r: self.fail("Changed sources must not create tasks"))
        task = await self.input(service)
        Path(task["files"][0]["source_path"]).write_bytes(b"changed")
        await service.run(task["id"])
        self.assertEqual(service.repository.get(task["id"])["error"]["code"], "source_integrity_mismatch")

    async def test_poll_limit_resume_get_only_no_duplicate_create(self):
        calls, finish = [], False
        def handle(request):
            calls.append(request.method)
            file = {"file_id": "f", "file_name": "a.pdf", "status": "failed" if finish else "running"}
            return httpx.Response(202 if request.method == "POST" else 200,
                                  json={"task_id": "t", "status": "failed" if finish else "running", "files": [file]})
        service = self.service(handle)
        task = await self.input(service)
        await service.run(task["id"])
        self.assertEqual(service.repository.get(task["id"])["status"], "timed_out")
        finish = True
        await service.resume(task["id"], "alice")
        await service.run(task["id"])
        self.assertEqual(service.repository.get(task["id"])["status"], "failed")
        self.assertEqual(calls.count("POST"), 1)

    async def test_interrupted_upload_queries_before_retry_and_partial_results_survive(self):
        calls, uploaded = [], False
        def snapshot():
            return {"task_id": "t", "status": "partial" if uploaded else "waiting-file", "files": [
                {"file_id": "f1", "file_name": "a.pdf", "status": "completed" if uploaded else "waiting-file",
                 **({"result_url": "https://store.invalid/result"} if uploaded else {"upload": {
                     "url": "https://store.invalid/input", "headers": {"X-Signed": "test"}, "expires_at": 4102444800}})},
                {"file_id": "f2", "file_name": "b.pdf", "status": "failed", "error": {"code": "parse_failed"}}]}
        def handle(request):
            nonlocal uploaded
            calls.append(request.method)
            if request.method == "PUT":
                uploaded = True
                self.assertNotIn("Authorization", request.headers)
                raise httpx.WriteError("synthetic", request=request)
            if request.url.host == "store.invalid":
                return httpx.Response(200, content=bundle())
            return httpx.Response(202 if request.method == "POST" else 200, json=snapshot())
        service = self.service(handle)
        a, b = self.root / "a.pdf", self.root / "b.pdf"
        a.write_bytes(b"%PDF-1"); b.write_bytes(b"%PDF-2")
        task = (await service.submit("alice", "partial", [("a.pdf", a), ("b.pdf", b)]))[0]
        await service.run(task["id"])
        result = service.repository.get(task["id"])
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["files"][0]["result_path"])
        self.assertEqual(calls.count("PUT"), 1)
        self.assertEqual(calls[calls.index("PUT") + 1], "GET")

    async def test_real_normalizer_review_to_existing_sqlite_knowledge_pipeline(self):
        from qa_core.storage.database import Database
        from qa_core.config.settings import Settings
        from qa_core.indexing.service import ingest_documents
        from qa_core.retrieval.models import DemoEmbeddings
        from query import ask
        service = self.service()
        task = await self.input(service)
        file = task["files"][0]
        file.update(remote_id="f", result_path="synthetic-location", parse={"tier": "standard", "parser_version": "4.1.7"})
        task["remote_id"] = "t"
        result = normalize_artifacts(task, file, unpack(bundle(), self.config))
        self.assertEqual(result.pages[0].page_number, 3)
        document = reviewed_legal_document(result, reviewer="test", law_name="synthetic")
        db = Database(sqlite_path=self.root / "kb.sqlite3")
        self.addCleanup(db.close)
        db.initialize()
        embeddings = DemoEmbeddings()
        stats = ingest_documents([document], database=db, embeddings=embeddings,
                                 settings=Settings(embedding_backend="demo", embedding_dimension=32), version="v1")
        db.publish("v1")
        self.assertEqual(stats["documents_seen"], 1)
        self.assertTrue(ask("测试", database=db, embeddings=embeddings, stream=False)["hits"])
        table_result = normalize_artifacts(task, file, unpack(bundle(table=True), self.config))
        with self.assertRaises(ValueError):
            reviewed_legal_document(table_result, reviewer="test", law_name="synthetic")
