"""Read-only package/import and container build-context preflight."""
import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Round01Integrity(unittest.TestCase):
    def test_business_modules_import_without_external_services(self):
        for path in sorted((ROOT/'qa_core').rglob('*.py')):
            name='.'.join(path.relative_to(ROOT).with_suffix('').parts)
            if name.endswith('.__init__'):
                name=name[:-9]
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_DOC_002_docker_copy_sources_exist(self):
        missing=[]
        for line in (ROOT/'Dockerfile').read_text(encoding='utf-8').splitlines():
            if line.startswith('COPY ') and not line.startswith('COPY --from='):
                for source in line.split()[1:-1]:
                    if not (ROOT/source).exists():
                        missing.append(source)
        self.assertEqual(missing, [], 'Docker COPY sources missing from isolated worktree')
