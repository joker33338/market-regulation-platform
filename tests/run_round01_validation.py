"""Run QA acceptance file against an explicitly selected isolated source tree.

Use the existing Python interpreter and optional API dependencies. No dependency
installation, network access, DDL or production configuration loading occurs here.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


def cases(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from cases(test)
        else:
            yield test


def case_id(test):
    test = getattr(test, 'test_case', test)
    return f'{type(test).__module__.split(".")[-1]}.{type(test).__name__}.{test._testMethodName}'


class RecordingResult(unittest.TextTestResult):
    """记录方法级结果，便于合并Windows与独立数据库的执行证据。"""
    def startTest(self, test):
        if not hasattr(self, 'outcomes'):
            self.outcomes = {}
        self.outcomes[case_id(test)] = 'RUNNING'
        super().startTest(test)

    def addSuccess(self, test):
        self.outcomes[case_id(test)] = 'PASS'
        super().addSuccess(test)

    def addSkip(self, test, reason):
        self.outcomes[case_id(test)] = 'SKIP'
        super().addSkip(test, reason)

    def addFailure(self, test, err):
        self.outcomes[case_id(test)] = 'FAIL'
        super().addFailure(test, err)

    def addError(self, test, err):
        self.outcomes[case_id(test)] = 'ERROR'
        super().addError(test, err)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.outcomes[case_id(test)] = 'FAIL'
        super().addSubTest(test, subtest, err)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--include-source-tests', action='store_true')
    parser.add_argument('--result-json', type=Path)
    parser.add_argument('--database-only', action='store_true')
    parser.add_argument('--source-commit')
    parser.add_argument('--qa-test-commit')
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / 'qa_core/document_parsing/mineru_service.py').is_file():
        parser.error('selected source does not include Fix implementation')
    sys.path.insert(0, str(source))
    suite = unittest.TestSuite()
    qa_suite = unittest.TestSuite()
    filenames = ['test_round01_postgres_acceptance.py'] if args.database_only else [
        'test_round01_fix_acceptance.py', 'test_mineru_contract.py', 'test_round01_postgres_acceptance.py']
    for name in filenames:
        file = Path(__file__).with_name(name)
        spec = importlib.util.spec_from_file_location(file.stem, file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        qa_suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    qa_keys = {case_id(test) for test in cases(qa_suite)}
    if args.include_source_tests:
        supplied = unittest.defaultTestLoader.discover(str(source / 'tests'), top_level_dir=str(source))
        # Fix may have imported QA's tests already. Replace only overlapping QA
        # cases with this committed QA copy, retaining every other source test.
        suite.addTests(test for test in cases(supplied) if case_id(test) not in qa_keys)
    elif args.database_only:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromNames([
            'tests.test_parsing_postgres', 'tests.test_postgres_integration']))
    suite.addTests(qa_suite)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    if args.result_json:
        failures = {getattr(test, 'test_case', test).id()
                    for test, _ in result.failures + result.errors}
        failures.update(test.id() for test in result.unexpectedSuccesses)
        def commit(root, declared):
            if declared:
                if not re.fullmatch('[0-9a-f]{40}', declared):
                    parser.error('commit must be a full SHA')
                return declared
            return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        evidence = {
            'source_commit': commit(source, args.source_commit),
            'qa_test_commit': commit(Path(__file__).resolve().parents[1], args.qa_test_commit),
            'identity_mode': 'host-verified-readonly-mount' if args.source_commit else 'local-git',
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
            'test_outcomes': result.outcomes,
        }
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
