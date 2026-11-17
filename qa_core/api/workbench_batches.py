"""工作台持久化批次：自动排队解析，复用现有 SQLite 任务，不创建数据库。"""
import asyncio
from datetime import datetime, timezone
from pathlib import PurePosixPath
import time

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from .common import guarded, page_of
from .workbench_schemas import UploadBatchStatus, UploadBatchPage
from .private_operations import OperationStore, digest
from qa_core.document_parsing.mineru_client import MinerUError


def now():
    return datetime.now(timezone.utc).isoformat()


class BatchStore(OperationStore):
    def __init__(self, root):
        super().__init__(root)
        self.root = self.root.parent / ".file-workbench-batches"

    def create(self, principal, owner, key, name):
        if not owner:
            raise MinerUError("data_owner_required", 403)
        operation_id = self.identifier(principal, "file-batch", key)
        fingerprint = digest([name, owner])
        with self.locked():
            previous = self.replay(operation_id, fingerprint)
            if previous:
                return previous
            value = {"operation_id": operation_id, "fingerprint": fingerprint,
                     "principal_id": principal, "owner_id": owner, "name": name,
                     "created_at": now(), "files": []}
            self.save(value)
            return value

    def read_owned(self, batch_id, principal):
        value = self.read(batch_id)
        if value is None or value["principal_id"] != principal:
            raise MinerUError("batch_not_found", 404)
        return value

    def append(self, batch_id, principal, files):
        # 相对目录仅用于分组，绝不参与原件存储路径的计算。
        for item in files:
            path = item.get("relative_path", "")
            fid = item.get("file_id", "")
            if (len(fid) != 32 or any(c not in "0123456789abcdef" for c in fid)
                    or len(path) > 1024 or "\\" in path or ":" in path or "\x00" in path
                    or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts):
                raise MinerUError("invalid_batch_file", 422)
        with self.locked():
            value = self.read_owned(batch_id, principal)
            known = {item["file_id"] for item in value["files"]}
            by_hash = {(item.get('owner_id') or value['owner_id'],item['sha256']):item['file_id']
                       for item in value['files'] if item.get('sha256') and item['status']!='duplicate'}
            for item in files:
                if item["file_id"] not in known:
                    signature=(item.get('owner_id') or value['owner_id'],item.get('sha256'))
                    duplicate=by_hash.get(signature) if item.get('sha256') else None
                    entry={**item,"status":"duplicate" if duplicate else "queued","attempt":0}
                    if duplicate: entry['duplicate_of']=duplicate
                    elif item.get('sha256'): by_hash[signature]=item['file_id']
                    value["files"].append(entry)
                    known.add(item["file_id"])
            self.save(value)
            return value

    def retry(self, batch_id, principal):
        with self.locked():
            value = self.read_owned(batch_id, principal)
            for item in value["files"]:
                if item["status"] == "failed":
                    item.update(status="queued", attempt=item["attempt"] + 1)
                    item.pop("error_code", None)
                    item.pop("task_id", None)
            self.save(value)
            return value

    def claim(self):
        with self.locked():
            for path in sorted(self.root.glob("*.json")):
                value = self.read(path.stem)
                for item in value["files"]:
                    expired = item["status"] == "dispatching" and time.time() - item.get("claimed_at", 0) > 300
                    if item["status"] == "queued" or expired:
                        item.update(status="dispatching", claimed_at=time.time())
                        self.save(value)
                        return value["operation_id"], value["owner_id"], dict(item)
        return None

    def finish(self, batch_id, file_id, attempt, **changes):
        with self.locked():
            value = self.read(batch_id)
            for item in value["files"]:
                if item["file_id"] == file_id and item["attempt"] == attempt:
                    item.update(**changes)
            self.save(value)

    def reconcile(self, repository):
        # 任务本身的成功/失败以 SQLite 中单文件状态为准，绝不凭提交回执猜测完成。
        with self.locked():
            for path in self.root.glob("*.json"):
                value = self.read(path.stem)
                changed = False
                for item in value["files"]:
                    if item["status"] != "submitted":
                        continue
                    try:
                        task = repository.get(item["task_id"], item.get("owner_id") or value["owner_id"])
                    except MinerUError as exc:
                        if exc.status != 404:
                            raise
                        item.update(status="failed", error_code="task_not_found")
                        changed = True
                        continue
                    file = next((f for f in task["files"] if f.get("source_file_id") == item["file_id"]), None)
                    if file and file["status"] == "completed":
                        item.update(status="parsed", parse_id=file.get("database_parse_id"))
                        changed = True
                    elif file and file["status"] in {"failed", "canceled", "timed_out"}:
                        item.update(status="failed", error_code="parse_failed")
                        changed = True
                if changed:
                    self.save(value)

    async def dispatch(self, service, reader):
        await asyncio.to_thread(self.reconcile, service.repository)
        claimed = await asyncio.to_thread(self.claim)
        if not claimed:
            return
        batch_id, owner, item = claimed
        owner = item.get("owner_id") or owner
        try:
            value, path = await asyncio.to_thread(reader.upload, owner, item["file_id"])
            task, _ = await service.submit(owner, digest([batch_id, item["file_id"], item["attempt"]]),
                                           [(value["file_name"], path, item["file_id"])])
            changes = {"status": "submitted", "task_id": task["id"]}
        except MinerUError as exc:
            changes = {"status": "queued"} if exc.status == 429 else {
                "status": "failed", "error_code": "parser_disabled" if exc.code == "parser_disabled" else "submission_failed"}
        except Exception:
            changes = {"status": "failed", "error_code": "submission_unavailable"}
        await asyncio.to_thread(self.finish, batch_id, item["file_id"], item["attempt"], **changes)


class BatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)


class BatchFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    relative_path: str = Field(default="", max_length=1024)


class BatchAppend(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # 传输分页不限制整批总量，客户端可持续追加。
    files: list[BatchFile] = Field(min_length=1, max_length=100)


def register_workbench_batches(app, principal, reader, config):
    store = BatchStore(config.result_dir)
    app.state.file_batches = store
    router = APIRouter(tags=["file-workbench"])

    def public(value, selected_ids=None, page=1, page_size=100):
        from collections import Counter
        items=[item for item in value['files'] if selected_ids is None or item['file_id'] in selected_ids]
        return {key: value[key] for key in ("operation_id", "name", "created_at")} | {
            "files": [{key: item[key] for key in ("file_id", "file_name", "relative_path", "status", "task_id", "error_code", "parse_id", "duplicate_of")
                       if key in item} for item in items[(page-1)*page_size:page*page_size]],
            "total_files":len(value['files']),"counts":dict(Counter(item['status'] for item in value['files']))}

    @router.post("/api/workbench/batches", status_code=201,response_model=UploadBatchStatus)
    @guarded
    def create(body: BatchCreate, idempotency_key: str = Header(min_length=1, max_length=128),
               identity=Depends(principal)):
        return public(store.create(identity.principal_id, identity.owner_id, idempotency_key, body.name))

    @router.get("/api/workbench/batches",response_model=UploadBatchPage)
    @guarded
    def listing(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                identity=Depends(principal)):
        values = []
        # 只读查询不创建目录，不暴露其他操作者的上传批次。
        for path in store.root.glob("*.json"):
            value = store.read(path.stem)
            if value["principal_id"] == identity.principal_id:
                values.append(public(value,selected_ids=set()))
        values.sort(key=lambda value: value["created_at"], reverse=True)
        return page_of(values, page, page_size, "persistent_file_batches")

    @router.get("/api/workbench/batches/{batch_id}",response_model=UploadBatchStatus)
    @guarded
    def detail(batch_id: str,page:int=Query(1,ge=1),page_size:int=Query(100,ge=1,le=100),identity=Depends(principal)):
        return public(store.read_owned(batch_id, identity.principal_id),page=page,page_size=page_size)

    @router.post("/api/workbench/batches/{batch_id}/files",response_model=UploadBatchStatus)
    @guarded
    def append(batch_id: str, body: BatchAppend, identity=Depends(principal)):
        owned = store.read_owned(batch_id, identity.principal_id)
        # 先核对整页归属，再一次提交；不能用请求体伪造其他用户的文件。
        from .review_rbac import readable_upload
        entries = []
        for item in body.files:
            upload, source_path = readable_upload(reader, identity, item.file_id)
            from .upload_ownership import upload_owner
            target_owner = upload_owner(reader,identity,upload,source_path)
            if not target_owner or not identity.is_admin and target_owner != identity.owner_id:
                raise MinerUError("task_write_forbidden", 403)
            entries.append({**item.model_dump(),"owner_id":target_owner,"sha256":upload["sha256"],"file_name":upload["file_name"]})
        return public(store.append(batch_id,identity.principal_id,entries),selected_ids={item.file_id for item in body.files})

    @router.post("/api/workbench/batches/{batch_id}/retry",response_model=UploadBatchStatus)
    @guarded
    def retry(batch_id: str, identity=Depends(principal)):
        return public(store.retry(batch_id, identity.principal_id))

    app.include_router(router)
