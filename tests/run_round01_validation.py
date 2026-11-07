"""Run QA acceptance file against an explicitly selected isolated source tree.

Use the existing Python interpreter and optional API dependencies. No dependency
installation, network access, DDL or production configuration loading occurs here.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


def cases(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from cases(test)
        else:
            yield test


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--include-source-tests', action='store_true')
    parser.add_argument('--result-json', type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / 'qa_core/document_parsing/mineru_service.py').is_file():
        parser.error('selected source does not include Fix implementation')
    sys.path.insert(0, str(source))
    file = Path(__file__).with_name('test_round01_fix_acceptance.py')
    spec = importlib.util.spec_from_file_location('round01_fix_acceptance', file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.TestSuite()
    qa_suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    qa_keys = {(type(test).__name__, test._testMethodName) for test in cases(qa_suite)}
    if args.include_source_tests:
        supplied = unittest.defaultTestLoader.discover(str(source / 'tests'), top_level_dir=str(source))
        # Fix may have imported QA's tests already. Replace only overlapping QA
        # cases with this committed QA copy, retaining every other source test.
        suite.addTests(test for test in cases(supplied)
                       if not (type(test).__module__.endswith('test_round01_fix_acceptance')
                               and (type(test).__name__, test._testMethodName) in qa_keys))
    suite.addTests(qa_suite)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if args.result_json:
        failures = {getattr(test, 'test_case', test).id()
                    for test, _ in result.failures + result.errors}
        failures.update(test.id() for test in result.unexpectedSuccesses)
        def commit(root):
            return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        evidence = {
            'source_commit': commit(source),
            'qa_test_commit': commit(Path(__file__).resolve().parents[1]),
            'checked_at': datetime.now(timezone.utc).isoformat(),
            'total_tests': result.testsRun,
            'passed_tests': result.testsRun - len(failures) - len(result.skipped) - len(result.expectedFailures),
            'failed_tests': len(failures),
            'failure_records': len(result.failures) + len(result.errors),
            'skipped_tests': len(result.skipped),
            'expected_failures': len(result.expectedFailures),
            'skips': [{'test': test.id(), 'reason': reason} for test, reason in result.skipped],
            'failed_test_ids': sorted(failures),
            'successful': result.wasSuccessful(),
        }
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
