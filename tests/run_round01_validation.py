"""Run QA acceptance file against an explicitly selected isolated source tree.

Use the existing Python interpreter and optional API dependencies. No dependency
installation, network access, DDL or production configuration loading occurs here.
"""
import argparse
import importlib.util
from pathlib import Path
import sys
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--include-source-tests', action='store_true')
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
    if args.include_source_tests:
        suite.addTests(unittest.defaultTestLoader.discover(str(source / 'tests'), top_level_dir=str(source)))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
