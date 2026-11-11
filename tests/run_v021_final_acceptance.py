"""独立绑定冻结 Fix 源码，运行既有 unittest；证据仅写入显式目录。"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from datetime import datetime, timezone


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True, encoding='utf-8').strip()


def valid_png_fixture_override(name, original, updated):
    """仅允许两处无效PNG夹具改为真PNG，逐字符约束其余代码及断言不变。"""
    if name == 'test_round01_repair_edges.py':
        old = '        self.a.write_bytes(b"%PDF-1.7 synthetic a")\n        self.b.write_bytes(b"%PDF-1.7 synthetic b")'
        new = '        for path in (self.a, self.b):\n            with fitz.open() as pdf:\n                pdf.new_page().insert_text((30, 30), "synthetic")\n                pdf.save(path)'
        return original.count(old) == 1 and updated == original.replace('import unittest\n', 'import unittest\nimport fitz\n', 1).replace(old, new, 1)
    payloads = {
        'test_v021_diagnostic_edges.py': "source.write_bytes(b'synthetic-only')",
        'test_v021_engine_diagnostics.py': "source.write_bytes(b'synthetic non-confidential fixture')",
    }
    old = payloads.get(name)
    if not old or original.count(old) != 1 or original.count('import unittest\n') != 1:
        return False
    expected = original.replace('import unittest\n', 'import unittest\nfrom PIL import Image\n', 1)
    expected = expected.replace(old, "Image.new('RGB', (10, 10), 'white').save(source)", 1)
    return updated == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--api-packages', type=Path)
    parser.add_argument('--qa-fixture-overrides', nargs='*', default=[],
                        choices=['test_v021_diagnostic_edges.py', 'test_v021_engine_diagnostics.py', 'test_round01_repair_edges.py'])
    args = parser.parse_args()
    source = args.source.resolve()
    qa = Path(__file__).resolve().parents[1]
    if source == qa or git(source, 'rev-parse', 'HEAD') != args.source_sha:
        parser.error('必须独立指定且匹配冻结 Fix SHA')
    if git(source, 'status', '--porcelain'):
        parser.error('Fix 工作区存在修改，拒绝混合版本测试')
    output = args.output.resolve()
    if not output.is_relative_to(qa / 'local'):
        parser.error('原始证据只能写入 QA local 目录')
    output.mkdir(parents=True, exist_ok=True)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1',
                      TRANSFORMERS_OFFLINE='1', PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True')
    for key in ('MVP_TEST_PG_DSN', 'PARSING_TEST_PG_DSN', 'PARSING_RESULT_PG_DSN', 'QA_ISOLATED_PG_DSN'):
        os.environ[key] = ''  # 数据库写入必须独立审批和独立执行。
    os.environ['MARKET_REGULATION_DUAL_ENGINE_TEST_ADAPTER'] = 'tests.dual_engine_adapter:run_scenario'
    os.environ['TEMP'] = os.environ['TMP'] = str(output)
    os.environ['OCR_ASCII_CACHE_ROOT'] = str(Path(os.environ['LOCALAPPDATA']) / 'Temp' / 'qa-v021-final-ascii')
    sys.dont_write_bytecode = True
    # 去掉 QA 工程根目录，业务模块只从 Fix 导入；测试辅助包单独绑定。
    sys.path[:] = [str(source)] + ([str(args.api_packages.resolve())] if args.api_packages else []) + [
        p for p in sys.path if p and Path(p).resolve() not in (qa, qa / 'tests', source)]
    os.environ['PYTHONPATH'] = os.pathsep.join([str(source)] + ([str(args.api_packages.resolve())] if args.api_packages else []))
    package = types.ModuleType('tests')
    package.__path__ = [str(source / 'tests'), str(qa / 'tests')]
    sys.modules['tests'] = package
    os.chdir(output)  # 相对写入不能落到 Fix 或 QA 源码目录。
    from tests.run_round01_validation import RecordingResult
    bindings = {}
    for name in ('qa_core', 'query', 'qa_core.document_parsing.document_router',
                 'qa_core.document_parsing.runtime', 'qa_core.document_parsing.mineru_api',
                 'qa_core.document_parsing.mineru_service', 'qa_core.document_parsing.quality'):
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(source):
            raise RuntimeError('业务模块来源错误：' + name)
        bindings[name] = str(path)
    files = {p.name: p for p in (source / 'tests').glob('test_*.py')}
    identical_tests = {}
    fixture_overrides = {}
    for file in (qa / 'tests').glob('test_*.py'):
        if file.name in files:
            original = files[file.name].read_text(encoding='utf-8')
            updated = file.read_text(encoding='utf-8')
            if original != updated:
                if file.name not in args.qa_fixture_overrides or not valid_png_fixture_override(file.name, original, updated):
                    raise RuntimeError('同名测试存在不同断言，需单独审阅：' + file.name)
                fixture_overrides[file.name] = dict(
                    reason='无效图片/PDF占位字节改为合法合成文件；其余代码及断言逐字符保持',
                    source_raw_sha256=hashlib.sha256(files[file.name].read_bytes()).hexdigest(),
                    qa_raw_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
                files[file.name] = file
                continue
            identical_tests[file.name] = dict(
                normalization='CRLF/CR -> LF only',
                normalized_sha256=hashlib.sha256(file.read_text(encoding='utf-8').encode()).hexdigest(),
                qa_raw_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                fix_raw_sha256=hashlib.sha256(files[file.name].read_bytes()).hexdigest())
        else:
            files[file.name] = file
    suite = unittest.TestSuite()
    test_paths = {}
    for name, file in sorted(files.items()):
        module_name = 'tests.' + file.stem
        if name in fixture_overrides:
            spec = importlib.util.spec_from_file_location(module_name, file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        else:
            module = importlib.import_module(module_name)
        test_paths[module_name] = str(Path(module.__file__).resolve())
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    origins = {}
    for name, module in list(sys.modules.items()):
        if name == 'query' or name == 'qa_core' or name.startswith('qa_core.'):
            if getattr(module, '__file__', None):
                path = Path(module.__file__).resolve()
                if not path.is_relative_to(source):
                    raise RuntimeError('测试期间发生业务模块来源漂移：' + name)
                origins[name] = str(path)
    final_sha = git(source, 'rev-parse', 'HEAD')
    clean = not git(source, 'status', '--porcelain')
    evidence = dict(checked_at=datetime.now(timezone.utc).isoformat(),
                    source_commit=args.source_sha, qa_commit=git(qa, 'rev-parse', 'HEAD'),
                    source_path=str(source), qa_path=str(qa), python=sys.version,
                    executable=sys.executable, initial_bindings=bindings, imported_business_modules=origins,
                    test_paths=test_paths, qa_identical_test_hashes=identical_tests,
                    fixture_overrides=fixture_overrides,
                    total=result.testsRun, outcomes=result.outcomes,
                    failures=[t.id() for t, _ in result.failures], errors=[t.id() for t, _ in result.errors],
                    skips=[dict(test=t.id(), reason=r) for t, r in result.skipped],
                    final_sha=final_sha, source_clean=clean,
                    successful=result.wasSuccessful() and final_sha == args.source_sha and clean)
    (output / 'suite-result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if evidence['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
