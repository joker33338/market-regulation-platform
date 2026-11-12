"""候选pytest插件：逐文件核对冻结源码，禁止用宿主业务挂载冒充镜像。"""
import hashlib
import json
import os
from pathlib import Path


def pytest_sessionstart(session):
    manifest=json.loads(Path(os.environ['CANDIDATE_SOURCE_HASHES']).read_text())
    for filename,expected in manifest['files'].items():
        # Windows的Git归档可能输出CRLF；按Git文本对象的LF核对，不忽略其他字节差异。
        actual=hashlib.sha256(Path(filename).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if actual!=expected:
            raise RuntimeError('候选业务文件与冻结Git源码不一致')
    import qa_core
    if not qa_core.__file__.startswith('/app/qa_core/'):
        raise RuntimeError('业务模块未从镜像加载')
    print('frozen_source_files_verified='+str(len(manifest['files']))+';comparison=git_blob_canonical_lf')
