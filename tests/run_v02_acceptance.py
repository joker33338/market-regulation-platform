"""对指定Fix源码执行v0.2.0测试；缺少新策略绑定时明确列出SKIP。"""
import argparse
import faulthandler
import importlib.util
from pathlib import Path
import sys
import unittest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args()
    source=args.source.resolve()
    if not (source/'qa_core/document_parsing/document_router.py').is_file():
        parser.error('需要有效的项目源码')
    sys.path.insert(0,str(source))
    file=Path(__file__).with_name('test_v02_dual_engine.py')
    spec=importlib.util.spec_from_file_location('test_v02_dual_engine',file)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    faulthandler.dump_traceback_later(60,exit=True)
    try:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
    finally:
        faulthandler.cancel_dump_traceback_later()
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
