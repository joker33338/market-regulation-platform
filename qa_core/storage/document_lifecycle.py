"""上传生命周期锁及软删除；原始字节不销毁，活动元数据移动是提交点。"""
from contextlib import contextmanager, asynccontextmanager
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4
from filelock import FileLock, Timeout
from qa_core.document_parsing.mineru_client import MinerUError


def lock(root):
    return FileLock(str(Path(root)/'.document-lifecycle.lock'),timeout=5,thread_local=False)


@contextmanager
def lifecycle(root):
    try:
        with lock(root):
            yield
    except Timeout:
        raise MinerUError('document_busy',409) from None


@asynccontextmanager
async def async_lifecycle(root):
    guard=lock(root)
    acquire=asyncio.create_task(asyncio.to_thread(guard.acquire))
    try:
        await asyncio.shield(acquire)
    except Timeout:
        raise MinerUError('document_busy',409) from None
    except asyncio.CancelledError:
        try:
            await acquire
        finally:
            guard.release()
        raise
    try:
        yield
    finally:
        guard.release()


def retained_upload(path):
    """支持的入库入口也检查活动元数据，拒绝重新引用已隔离上传。"""
    path=Path(path)
    if path.parent.parent.name=='sources' and re.fullmatch('[a-f0-9]{64}',path.parent.name) and re.fullmatch('[a-f0-9]{32}',path.stem):
        return path.parent.parent.parent
    return None


def assert_active(path):
    path=Path(path)
    if retained_upload(path) is not None and not path.with_suffix('.json').is_file():
        raise MinerUError('source_not_found',404)


def delete_document(reader,principal,file_id,references):
    if not re.fullmatch('[a-f0-9]{32}',file_id):
        raise MinerUError('invalid_file_id',422)
    owner=principal.owner_id
    if owner is None or not principal.can_delete(owner):
        raise MinerUError('document_delete_forbidden',403)
    with lifecycle(reader.config.result_dir):
        root=reader.root(owner)
        if root.is_symlink() or root.resolve().parent != (reader.config.result_dir/'sources').resolve():
            raise MinerUError('source_storage_unavailable',503)
        active=root/(file_id+'.json')
        if not active.is_file():
            # 只有DELETE采用任务指定的跨owner403语义，不回显他人属性。
            base=reader.config.result_dir/'sources'
            for directory in base.iterdir() if base.is_dir() else ():
                if directory.is_symlink() or not re.fullmatch('[a-f0-9]{64}',directory.name):
                    continue
                if directory != root and ((directory/(file_id+'.json')).is_file() or (directory/'.deleted'/(file_id+'.json')).is_file()):
                    raise MinerUError('document_delete_forbidden',403)
            raise MinerUError('document_not_found',404)
        value,source=reader.upload(owner,file_id)
        history=reader.history(owner,file_id)
        if history:
            active_states={'created','uploading','pending','running','waiting-file'}
            code='document_active_task' if any(task['status'] in active_states for task,_ in history) else 'document_evidence_protected'
            raise MinerUError(code,409)
        if references(owner,file_id,value):
            raise MinerUError('document_referenced',409)
        if not source.is_file():
            raise MinerUError('source_storage_unavailable',503)
        archive=root/'.deleted'
        if archive.is_symlink():
            raise MinerUError('source_storage_unavailable',503)
        archive.mkdir(exist_ok=True)
        if archive.resolve().parent != root.resolve():
            raise MinerUError('source_storage_unavailable',503)
        archived=archive/(file_id+'.json')
        if archived.exists():
            raise MinerUError('document_archive_conflict',409)
        deleted_at=datetime.now(timezone.utc).isoformat()
        receipt={'file_id':file_id,'deleted':True,'deleted_at':deleted_at,
                 'disposition':{'mode':'soft_delete','original_bytes':'retained','metadata':'quarantined','related_records':'unchanged'}}
        audit={'file_id':file_id,'deleted_at':deleted_at,'record_type':'prepared_deletion',
               'commit_condition':'archived_metadata_exists_and_active_metadata_absent',
               'operator_id':principal.principal_id,'owner_id':owner,'deletion_id':uuid4().hex,
               'metadata_sha256':hashlib.sha256(active.read_bytes()).hexdigest()}
        # 先准备审计，只有活动元数据确已移动才算删除；准备失败不影响原文件可见性。
        prepared=archive/(file_id+'.deletion.json')
        temporary=archive/(uuid4().hex+'.tmp')
        with temporary.open('x',encoding='utf-8') as stream:
            json.dump(audit,stream,ensure_ascii=False)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,prepared)
        os.replace(active,archived)
        # 提交点之后不再做可能导致返回503的存储操作。
        return receipt
