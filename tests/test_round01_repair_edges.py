"""Focused R01-004/005 boundaries: immutable artifacts and durable local progress."""
import asyncio
from collections import Counter
from pathlib import Path
import tempfile
import unittest
import fitz
from unittest.mock import patch

from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing.mineru_artifacts import store_artifacts
from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService
from qa_core.document_parsing.schemas import DocumentResult, PageResult
from tests.test_mineru_implementation import bundle


class ArtifactRepairEdges(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = MinerUConfig(result_dir=self.root)

    def test_reserved_case_variants_rejected_before_writing_existing_outputs(self):
        directory = self.root / "output"
        directory.mkdir()
        original = directory / "artifact.bin"
        original.write_bytes(b"previous original download")
        for name in ("ARTIFACT.BIN", "Artifact.Bin", "NORMALIZED.JSON", "./Normalized.Json",
                     "ARTIFACT.BIN/member.txt", "normalized.json/member.txt"):
            with self.subTest(name=name), self.assertRaises(MinerUError):
                store_artifacts(bundle({name: b"replacement"}), directory, self.config)
            self.assertEqual(original.read_bytes(), b"previous original download")
            self.assertEqual(list(directory.iterdir()), [original])

    def test_zip_members_cannot_collide_with_generated_temporary_names(self):
        payload = bundle({"markdown.md.part": b"member bytes"})
        directory = self.root / "output"
        expected = store_artifacts(payload, directory, self.config)
        self.assertEqual((directory / "artifact.bin").read_bytes(), payload)
        for name, data in expected.items():
            self.assertEqual((directory / name).read_bytes(), data)
        self.assertFalse(list(directory.glob(".mineru-*")))


class LocalBatchRepairEdges(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = MinerUConfig(enabled=True, mode="local", result_dir=self.root)
        self.repository = TaskRepository(self.root / "tasks.sqlite3")
        self.a, self.b = self.root / "a.pdf", self.root / "b.pdf"
        # Parsing is injected below; no OCR, network or model is needed.
        for path in (self.a, self.b):
            with fitz.open() as pdf:
                pdf.new_page().insert_text((30, 30), "synthetic")
                pdf.save(path)

    def result(self, path):
        from qa_core.utils import file_sha256
        return DocumentResult(file_sha256(path), Path(path).name, ".pdf", {}, pages=[PageResult(1, "native_pdf", raw_text="synthetic")])

    async def submit(self, service, key):
        return (await service.submit("synthetic-owner", key, [("a.pdf", self.a), ("b.pdf", self.b)]))[0]

    async def test_database_retry_reuses_exact_result_and_skips_successful_sibling(self):
        calls, records, sink_calls = [], {}, Counter()
        repository = self.repository

        class FlakySink:
            def save(sink, task, file, result):
                name = file["file_name"]
                sink_calls[name] += 1
                text = result.to_json()
                if name in records:
                    self.assertEqual(records[name], text, "retry must reuse the exact parsed result")
                records[name] = text
                if name == "b.pdf" and sink_calls[name] == 1:
                    stored = repository.get(task["id"])
                    self.assertEqual(stored["files"][0]["status"], "completed")
                    raise RuntimeError("synthetic failure text must not leak")
                return "synthetic-db-" + name

        service = MinerUService(self.config, self.repository, result_sink=FlakySink())
        task = await self.submit(service, "retry")
        def parse(parser, path):
            calls.append(Path(path).name)
            return self.result(path)
        with patch.object(DocumentParser, "parse", autospec=True, side_effect=parse):
            await service.run(task["id"])
            failed = self.repository.get(task["id"])
            self.assertEqual(failed["status"], "partial")
            self.assertEqual(failed["files"][1]["error"], {"code": "RuntimeError"})
            await service.resume(task["id"], "synthetic-owner")
            await service.run(task["id"])
        result = self.repository.get(task["id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(calls, ["a.pdf", "b.pdf"])
        self.assertEqual(sink_calls, {"a.pdf": 1, "b.pdf": 2})
        self.assertEqual(result["files"][0]["database_parse_id"], failed["files"][0]["database_parse_id"])
        self.assertNotIn("error", result["files"][1])

    async def test_worker_interruption_preserves_completed_sibling_for_restart(self):
        calls = Counter()
        service = MinerUService(self.config, self.repository)
        task = await self.submit(service, "interruption")
        def parse(parser, path):
            name = Path(path).name
            calls[name] += 1
            if name == "b.pdf" and calls[name] == 1:
                raise asyncio.CancelledError()
            return self.result(path)
        with patch.object(DocumentParser, "parse", autospec=True, side_effect=parse):
            with self.assertRaises(asyncio.CancelledError):
                await service.run(task["id"])
            self.assertEqual(self.repository.get(task["id"])["files"][0]["status"], "completed")
            restarted = MinerUService(self.config, TaskRepository(self.root / "tasks.sqlite3"))
            await restarted.run(task["id"])
        self.assertEqual(self.repository.get(task["id"])["status"], "completed")
        self.assertEqual(calls, {"a.pdf": 1, "b.pdf": 2})

    async def test_changed_source_and_failed_parse_result_are_isolated(self):
        service = MinerUService(self.config, self.repository)
        task = await self.submit(service, "integrity")
        self.a.write_bytes(b"modified synthetic source")
        with patch.object(DocumentParser, "parse", autospec=True, side_effect=lambda parser, path: self.result(path)):
            await service.run(task["id"])
        stored = self.repository.get(task["id"])
        self.assertEqual(stored["status"], "partial")
        self.assertEqual(stored["files"][0]["error"], {"code": "source_integrity_mismatch"})
        self.assertEqual(stored["files"][1]["status"], "completed")

        task2 = await self.submit(service, "failed-result")
        def parse(parser, path):
            result = self.result(path)
            if Path(path).name == "a.pdf":
                result.parsing_status = "failed"
            return result
        with patch.object(DocumentParser, "parse", autospec=True, side_effect=parse):
            await service.run(task2["id"])
        stored2 = self.repository.get(task2["id"])
        self.assertEqual(stored2["status"], "partial")
        self.assertEqual(stored2["files"][0]["error"], {"code": "local_parse_failed"})
        self.assertEqual(stored2["files"][1]["status"], "completed")
