"""固定全部匹配文件范围，操作时重新核验权限和来源，不把分页当作全部。"""
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from .common import guarded, page_of
from .workbench_schemas import SelectionSnapshot, SelectionFilePage
from .document_query import select_documents, validate_window
from .private_operations import OperationStore, digest
from .review_rbac import readable_upload
from .workbench_documents import inventory, add_batch_metadata, add_job_metadata
from qa_core.document_parsing.mineru_client import MinerUError


class SelectionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyword: str = Field(default="", max_length=200)
    stage: str = Field(default="", max_length=40)
    category: str = Field(default="", max_length=40)
    doc_type: str = Field(default="", max_length=40)
    batch_id: str = Field(default="", max_length=64)
    date_from: datetime | None = None
    date_to: datetime | None = None


def register_workbench_selections(app, principal, reader, config):
    store = OperationStore(config.result_dir)
    store.root = store.root.parent / ".file-workbench-selections"
    router = APIRouter(tags=["file-workbench"])

    @router.post("/api/workbench/selections", status_code=201,response_model=SelectionSnapshot)
    @guarded
    def create(body: SelectionFilter, idempotency_key: str = Header(min_length=1, max_length=128),
               identity=Depends(principal)):
        validate_window(body.date_from, body.date_to)
        operation_id = store.identifier(identity.principal_id, "selection", idempotency_key)
        fingerprint = digest(body.model_dump(mode="json"))
        with store.locked():
            value = store.replay(operation_id, fingerprint)
            if value is None:
                rows, _ = inventory(reader, identity, app.state.review_ledger, body.keyword)
                add_batch_metadata(rows, identity, config.result_dir)
                add_job_metadata(rows, identity, config.result_dir)
                term = body.keyword.strip().casefold()
                rows = [row for row in rows if
                        (not term or any(term in str(row.get(field) or "").casefold() for field in ("file_name", "title", "number","child_title_search")) or row.get("body_match"))
                        and (not body.stage or row["stage"] == body.stage)
                        and (not body.category or row["category"] == body.category)
                        and (not body.doc_type or row["doc_type"] == body.doc_type)
                        and (not body.batch_id or body.batch_id in row.get("batch_ids", []))]
                rows = select_documents(rows, body.date_from, body.date_to, "uploaded_at", "desc")
                value = {"operation_id": operation_id, "principal_id": identity.principal_id,
                         "fingerprint": fingerprint, "expires_at": time.time() + 3600,
                         "files": [{key: row[key] for key in ("file_id", "file_name", "sha256", "parse_id", "review_version")} for row in rows]}
                store.save(value)
            if value["expires_at"] <= time.time():
                raise MinerUError("selection_expired", 409)
            return {"selection_id": operation_id, "count": len(value["files"]), "expires_at": value["expires_at"]}

    @router.get("/api/workbench/selections/{selection_id}/files",response_model=SelectionFilePage)
    @guarded
    def files(selection_id: str, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100),
              identity=Depends(principal)):
        value = store.read(selection_id)
        if not value or value["principal_id"] != identity.principal_id:
            raise MinerUError("selection_not_found", 404)
        if value["expires_at"] <= time.time():
            raise MinerUError("selection_expired", 409)
        selected = page_of(value["files"], page, page_size, "fixed_selection_snapshot")
        for item in selected["list"]:
            current, _ = readable_upload(reader, identity, item["file_id"])
            if current["sha256"] != item["sha256"]:
                raise MinerUError("selection_source_changed", 409)
        return selected

    app.include_router(router)
