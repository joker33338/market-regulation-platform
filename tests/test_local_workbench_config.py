"""本地部署配置不得继承云端上传或批次授权，也不能悄悄改绑远程数据库。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from psycopg2.extensions import parse_dsn


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location("workbench_" + name, ROOT / "deploy/local" / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class LocalWorkbenchConfigTests(unittest.TestCase):
    def test_database_rebinding_preserves_credentials_and_drops_old_authorization(self):
        runtime = module("prepare").runtime_values({
            "PARSING_RESULT_PG_DSN": "host=127.0.0.1 port=15432 dbname=synthetic user=synthetic password='synthetic :/@ value'",
            "PARSING_API_TOKENS_JSON": json.dumps({"s" * 32: "synthetic"}),
            "MINERU_API_KEY": "synthetic-token", "DUAL_OCR_CLOUD_ENABLED": "1", "MINERU_MODE": "remote"})
        dsn = parse_dsn(runtime["PARSING_RESULT_PG_DSN"])
        self.assertEqual((dsn["host"], dsn["port"]), ("db", "5432"))
        self.assertEqual(dsn["password"], "synthetic :/@ value")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "runtime.json"
            path.write_text(json.dumps(runtime), encoding="utf-8")
            configured = module("entrypoint").configuration(path)
        self.assertEqual(configured["MINERU_MODE"], "local")
        self.assertEqual(configured["DUAL_OCR_CLOUD_ENABLED"], "0")
        self.assertEqual(configured["DUAL_OCR_AUTHORIZATION_MODE"], "FILE_SHA")

    def test_remote_database_and_untrusted_runtime_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            module("prepare").runtime_values({"PARSING_RESULT_PG_DSN": "host=remote.invalid dbname=synthetic"})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "runtime.json"
            path.write_text(json.dumps({"PARSING_API_TOKENS_JSON": "{}", "PARSING_RESULT_PG_DSN": "synthetic",
                                        "DUAL_OCR_CLOUD_ENABLED": "1"}), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                module("entrypoint").configuration(path)
