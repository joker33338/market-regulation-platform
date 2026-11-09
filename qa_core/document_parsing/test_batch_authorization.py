"""受信服务端测试批次授权；清单与账本路径均不得来自HTTP请求。"""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

from qa_core.utils import file_sha256
from .mineru_client import MinerUError


def unique_object(pairs):
    """重复JSON字段视为无效，不能依赖后值覆盖前值解释授权。"""
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('重复JSON字段')
        value[key] = item
    return value


@contextmanager
def locked(path):
    """操作系统锁覆盖整个读改写；锁文件不删除，异常退出自动释放锁。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def atomic_json(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.batch-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class TrustedTestBatch:
    def __init__(self, manifest_path, *, owner, batch_id, usage_path=None, max_calls=32, max_files=3):
        if not isinstance(owner, str) or not owner or not isinstance(batch_id, str) or not batch_id:
            raise ValueError('测试批次必须具有固定服务端owner与batch_id')
        if type(max_calls) is not int or not 1 <= max_calls <= 32 or type(max_files) is not int or not 1 <= max_files <= 3:
            raise ValueError('测试批次预算不得扩大')
        self.path = Path(manifest_path).resolve()
        self.owner, self.batch_id = owner, batch_id
        self.usage_path = Path(usage_path).resolve() if usage_path else self.path.with_name(self.path.name + '.usage.json')
        if self.usage_path == self.path:
            raise ValueError('账本不能覆盖授权清单')
        self.max_calls, self.max_files = max_calls, max_files

    def bind_task(self, task):
        context = dict(mode='TEST_BATCH', owner=self.owner, batch_id=self.batch_id)
        if task.get('owner') != self.owner:
            raise ValueError('测试批次owner不匹配')
        if 'authorization_context' in task and task['authorization_context'] != context:
            raise ValueError('恢复任务不得重新绑定测试批次')
        task['authorization_context'] = context

    def authorize(self, task, file):
        try:
            expected = dict(mode='TEST_BATCH', owner=self.owner, batch_id=self.batch_id)
            if task.get('owner') != self.owner or task.get('authorization_context') != expected:
                return False, 'test_batch_binding_required'
            if task.get('parse_options', {}).get('sensitive', False) is not False:
                return False, 'test_batch_sensitive_denied'
            if self.path.stat().st_size > 1024 * 1024:
                return False, 'test_batch_manifest_invalid'
            manifest = json.loads(self.path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_object)
            expiry = manifest.get('expires_at')
            if (type(manifest.get('version')) is not int or manifest['version'] != 1 or
                    manifest.get('owner') != self.owner or manifest.get('batch_id') != self.batch_id or
                    manifest.get('revoked') is not False or type(expiry) not in (int, float) or
                    not math.isfinite(expiry) or expiry <= time.time()):
                return False, 'test_batch_expired_revoked_or_mismatched'
            entries = manifest.get('entries')
            if not isinstance(entries, list) or not entries:
                return False, 'test_batch_manifest_invalid'
            members = {}
            for entry in entries:
                sha = entry.get('sha256')
                if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha) or sha in members:
                    return False, 'test_batch_manifest_invalid'
                members[sha] = entry
            sha = file.get('sha256')
            entry = members.get(sha)
            if not entry or file_sha256(Path(file['source_path'])) != sha:
                return False, 'test_batch_source_not_approved'
            if (any(entry.get(key) is not True for key in ('source_qualified', 'sensitivity_confirmed',
                    'third_party_transfer_rights_confirmed')) or entry.get('sensitive') is not False or
                    not isinstance(entry.get('source_evidence'), str) or not entry['source_evidence'].strip()):
                return False, 'test_batch_qualification_required'
            return True, 'TEST_BATCH:' + self.batch_id
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return False, 'test_batch_manifest_unreadable_or_invalid'

    def reserve_request(self, task, file, method):
        allowed, _ = self.authorize(task, file)
        if not allowed:
            raise MinerUError('test_batch_authorization_revoked', 403)
        try:
            with locked(self.usage_path.with_name(self.usage_path.name + '.lock')):
                identity = dict(owner=self.owner, batch_id=self.batch_id)
                ledger = json.loads(self.usage_path.read_text('utf-8'), object_pairs_hook=unique_object) if self.usage_path.exists() else {
                    **identity, 'calls': 0, 'files': [], 'methods': {}}
                if any(ledger.get(key) != value for key, value in identity.items()):
                    raise MinerUError('test_batch_ledger_identity_mismatch', 409)
                if (type(ledger.get('calls')) is not int or ledger['calls'] < 0 or
                        not isinstance(ledger.get('files'), list) or not isinstance(ledger.get('methods'), dict)):
                    raise MinerUError('test_batch_ledger_invalid', 409)
                files = set(ledger['files']) | {file['sha256']}
                if ledger['calls'] >= self.max_calls or len(files) > self.max_files:
                    raise MinerUError('test_batch_budget_exhausted', 429)
                if not self.authorize(task, file)[0]:
                    raise MinerUError('test_batch_authorization_revoked', 403)
                if method == 'POST':
                    # 创建结果不确定也保留占位；新task或新输出目录不能盲目重复同一模式上传。
                    submissions = ledger.setdefault('submissions', {})
                    key = file['sha256'] + ':' + task.get('parse_options', {}).get('strategy', 'auto')
                    if key in submissions:
                        raise MinerUError('test_batch_submission_already_started', 409)
                    submissions[key] = True
                ledger['calls'] += 1
                ledger['files'] = sorted(files)
                ledger['methods'][method] = ledger['methods'].get(method, 0) + 1
                atomic_json(self.usage_path, ledger)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise MinerUError('test_batch_ledger_unavailable', 409) from exc

    @staticmethod
    def remote_name(file):
        suffix = Path(file['source_path']).suffix.lower()
        if suffix not in {'.pdf', '.png', '.jpg', '.jpeg', '.docx'}:
            raise MinerUError('unsupported_file', 415)
        return 'sample-' + file['sha256'][:16] + suffix
