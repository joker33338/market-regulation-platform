"""真实云探针的无联网准备与防止误传控制。"""
import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("cloud_probe", Path(__file__).resolve().parents[1]/"scripts/verify_mineru_cloud.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class CloudProbePreparationTests(unittest.TestCase):
    def test_generated_content_and_hash_are_stable_for_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            first, sha = probe.prepare(Path(folder))
            payload = first.read_bytes()
            second, repeated_sha = probe.prepare(Path(folder))
            self.assertEqual(sha, repeated_sha)
            self.assertEqual(payload, second.read_bytes())
            import fitz
            with fitz.open(first) as document:
                self.assertEqual(len(document), 1)
                self.assertIn("SYNTHETIC-MINERU-V021", document[0].get_text())

    def test_existing_arbitrary_content_is_not_overwritten_or_authorized(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"synthetic-mineru-smoke.pdf"
            path.write_bytes(b"arbitrary input must not be uploaded")
            with self.assertRaises(ValueError):
                probe.prepare(Path(folder))
            self.assertEqual(path.read_bytes(), b"arbitrary input must not be uploaded")
