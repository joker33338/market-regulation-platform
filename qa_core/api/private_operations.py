"""私密运行授权与追加操作回执；不增加数据库或读取项目环境文件。"""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from filelock import FileLock, Timeout
from contextlib import contextmanager
from qa_core.document_parsing.mineru_client import MinerUError
from .principals import identifier


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def grant(identity, action, version):
    if not identity.is_admin:
        raise MinerUError('knowledge_write_forbidden',403)
    from qa_core.access import ALL_OWNERS
    return ALL_OWNERS


class OperationStore:
    def __init__(self, root):
        self.root=Path(root)/'.knowledge-api-operations'

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True,exist_ok=True)
        try:
            with FileLock(str(self.root/'operations.lock'),timeout=2):
                yield
        except Timeout:
            raise MinerUError('knowledge_operation_busy',409) from None

    def identifier(self, principal, action, key):
        return digest([principal,action,key])

    def read(self, operation_id):
        if len(operation_id)!=64 or any(c not in '0123456789abcdef' for c in operation_id):
            raise MinerUError('operation_not_found',404)
        path=self.root/(operation_id+'.json')
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None

    def save(self, value):
        path=self.root/(value['operation_id']+'.json')
        temporary=self.root/(uuid4().hex+'.tmp')
        with temporary.open('x',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)

    def replay(self, operation_id, fingerprint):
        previous=self.read(operation_id)
        if previous and previous['fingerprint']!=fingerprint:
            raise MinerUError('idempotency_conflict',409)
        return previous
