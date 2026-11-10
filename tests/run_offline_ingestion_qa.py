"""冻结 Git 内容到 QA 私有目录，并独立绑定专项测试，禁止修改 Fix。"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import types
import unittest


QA = Path(__file__).resolve().parents[1]


def git(*args, binary=False):
    return subprocess.check_output(['git', '-C', str(QA), *args],
                                   **({} if binary else {'text': True, 'encoding': 'utf-8'}))


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def verify(source, sha):
    manifest = json.loads((source / 'snapshot-identity.json').read_text('utf-8'))
    if manifest['source_commit'] != sha:
        raise RuntimeError('快照提交不匹配')
    for record in manifest['files']:
        if blob((source / record['path']).read_bytes()) != record['blob']:
            raise RuntimeError('快照内容变化：' + record['path'])
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--api-packages', type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.is_relative_to(QA / 'local'):
        parser.error('快照只允许放在 QA 忽略目录')
    actual = git('rev-parse', '--verify', args.source_sha + '^{commit}').strip()
    if len(args.source_sha) != 40 or actual != args.source_sha:
        parser.error('需要完整、存在的冻结提交')
    if args.export:
        if source.exists():
            parser.error('不覆盖已有快照，请使用新的证据目录')
        source.mkdir(parents=True)
        payload = git('-c', 'core.autocrlf=false', 'archive', args.source_sha, binary=True)
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
            archive.extractall(source, filter='data')
        records = []
        for row in git('ls-tree', '-rz', args.source_sha, binary=True).decode('utf-8').split('\0'):
            if not row:
                continue
            identity, path = row.split('\t', 1)
            mode, kind, digest = identity.split()
            if kind != 'blob' or mode == '120000':
                raise RuntimeError('快照包含不支持的对象')
            records.append(dict(path=path, blob=digest))
        (source / 'snapshot-identity.json').write_text(json.dumps(dict(
            source_commit=args.source_sha, exported_at=datetime.now(timezone.utc).isoformat(), files=records),
            ensure_ascii=False, indent=2), encoding='utf-8')
        verify(source, args.source_sha)
        print(json.dumps(dict(source_commit=args.source_sha, verified_files=len(records))))
        return 0
    if args.output is None:
        parser.error('需要输出目录')
    output = args.output.resolve()
    if not output.is_relative_to(QA / 'local'):
        parser.error('测试证据只允许放在 QA 忽略目录')
    output.mkdir(parents=True, exist_ok=True)
    verify(source, args.source_sha)
    sys.dont_write_bytecode = True
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      OFFLINE_QA_SOURCE=str(source), OFFLINE_QA_OUTPUT=str(output),
                      TEMP=str(output), TMP=str(output))
    for key in ('MVP_TEST_PG_DSN', 'PARSING_TEST_PG_DSN', 'PARSING_RESULT_PG_DSN', 'QA_ISOLATED_PG_DSN'):
        os.environ[key] = ''
    sys.path[:] = [str(source)] + ([str(args.api_packages)] if args.api_packages else []) + [
        p for p in sys.path if p and Path(p).resolve() not in (QA, QA / 'tests')]
    package = types.ModuleType('tests')
    package.__path__ = [str(QA / 'tests'), str(source / 'tests')]
    sys.modules['tests'] = package
    from tests.run_round01_validation import RecordingResult
    path = QA / 'tests/test_offline_ingestion_optimization.py'
    spec = importlib.util.spec_from_file_location('tests.test_offline_ingestion_optimization', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    bindings = {name: str(Path(m.__file__).resolve()) for name, m in sys.modules.copy().items()
                if (name == 'qa_core' or name.startswith('qa_core.')) and getattr(m, '__file__', None)}
    if not all(Path(p).is_relative_to(source) for p in bindings.values()):
        raise RuntimeError('源码导入路径发生漂移')
    verify(source, args.source_sha)
    evidence = dict(source_commit=args.source_sha, qa_commit=git('rev-parse', 'HEAD').strip(),
                    checked_at=datetime.now(timezone.utc).isoformat(), source_path=str(source),
                    executable=sys.executable, python=sys.version, test_file=str(path),
                    test_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bindings=bindings,
                    total=result.testsRun, outcomes=result.outcomes,
                    skips=[dict(test=t.id(), reason=r) for t, r in result.skipped],
                    failures=[t.id() for t, _ in result.failures], errors=[t.id() for t, _ in result.errors])
    (output / 'special-result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
