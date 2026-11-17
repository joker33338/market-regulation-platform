"""文件工作台批次使用临时状态；不连接数据库或调用解析引擎。"""
import tempfile
import unittest
from pathlib import Path
from qa_core.api.workbench_batches import BatchStore
from qa_core.document_parsing.mineru_client import MinerUError


class WorkbenchBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = BatchStore(Path(self.temp.name))

    def test_create_replay_and_changed_request_conflict(self):
        first = self.store.create("person", "alice", "key", "资料")
        self.assertEqual(first, self.store.create("person", "alice", "key", "资料"))
        with self.assertRaises(MinerUError) as error:
            self.store.create("person", "alice", "key", "其他")
        self.assertEqual(error.exception.status, 409)

    def test_incremental_append_has_no_total_file_limit_and_deduplicates(self):
        batch = self.store.create("person", "alice", "key", "资料")
        for offset in range(0, 45, 9):
            self.store.append(batch["operation_id"], "person", [
                {"file_id": f"{i:032x}", "relative_path": f"地区/{i}.pdf"} for i in range(offset, offset + 9)
            ])
        self.store.append(batch["operation_id"], "person", [{"file_id": f"{0:032x}", "relative_path": "地区/0.pdf"}])
        stored = self.store.read_owned(batch["operation_id"], "person")
        self.assertEqual(len(stored["files"]), 45)
        # 重新建立对象可恢复批次，不依赖页面内存。
        self.assertEqual(BatchStore(Path(self.temp.name)).read_owned(batch["operation_id"], "person"), stored)

    def test_foreign_principal_cannot_read_or_append(self):
        batch = self.store.create("person", "alice", "key", "资料")
        for action in [
            lambda: self.store.read_owned(batch["operation_id"], "other"),
            lambda: self.store.append(batch["operation_id"], "other", [{"file_id": "a" * 32}]),
        ]:
            with self.assertRaises(MinerUError) as error:
                action()
            self.assertEqual(error.exception.status, 404)

    def test_unsafe_relative_path_is_rejected_without_mutation(self):
        batch = self.store.create("person", "alice", "key", "资料")
        for path in ["../escape.pdf", "/tmp/file.pdf", "C:\\private.pdf", "地区/../../escape.pdf"]:
            with self.assertRaises(MinerUError):
                self.store.append(batch["operation_id"], "person", [{"file_id": "a" * 32, "relative_path": path}])
            self.assertEqual(self.store.read_owned(batch["operation_id"], "person")["files"], [])

    def test_retry_preserves_success_and_pending_items(self):
        batch = self.store.create("person", "alice", "key", "资料")
        value = self.store.append(batch["operation_id"], "person", [
            {"file_id": "a" * 32}, {"file_id": "b" * 32}, {"file_id": "c" * 32}
        ])
        value["files"][0].update(status="submitted", task_id="task")
        value["files"][1].update(status="failed", error_code="source_not_found")
        with self.store.locked():
            self.store.save(value)
        result = self.store.retry(batch["operation_id"], "person")
        self.assertEqual([item["status"] for item in result["files"]], ["submitted", "queued", "queued"])
        self.assertEqual(result["files"][0]["task_id"], "task")
        self.assertEqual(result["files"][1]["attempt"], 1)

    def test_invalid_id_and_empty_owner_fail_closed(self):
        with self.assertRaises(MinerUError):
            self.store.create("person", None, "key", "资料")
        with self.assertRaises(MinerUError):
            self.store.read_owned("../private", "person")

    def test_equal_bytes_are_not_queued_twice_within_same_owner(self):
        batch=self.store.create("person","alice","key","资料")
        value=self.store.append(batch["operation_id"],"person",[
            {"file_id":"a"*32,"sha256":"c"*64,"owner_id":"alice"},
            {"file_id":"b"*32,"sha256":"c"*64,"owner_id":"alice"},
            {"file_id":"d"*32,"sha256":"c"*64,"owner_id":"bob"}])
        self.assertEqual([item['status'] for item in value['files']],['queued','duplicate','queued'])
