"""现有业务服务的权限隔离 HTTP 查询适配。"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.document_parsing.mineru_api import public
from qa_core.utils import IngestionError
from .common import guarded, page_of, safe
from .schemas import (DocumentInfo, DocumentList, HealthResponse, ListResponse, PreviewRequest,
                      PreviewResponse, ReviewDetail, SearchRequest, SearchResponse, StatsResponse, VersionInfo)

def register_documents(app, service, config, owner, reader):
    router = APIRouter(tags=["documents"], dependencies=[Depends(owner)])
    pagination = Query(default=1, ge=1)
    size = Query(default=20, ge=1, le=100)

    @router.get("/api/documents", response_model=DocumentList)
    @guarded
    def documents(page: int = pagination, page_size: int = size,
                  keyword: str = Query("", max_length=200), status: str | None = Query(None, max_length=40),
                  doc_type: Literal["pdf", "docx", "image"] | None = None, identity=Depends(owner)):
        rows = [row for row in reader.documents(identity) if keyword.casefold() in row["file_name"].casefold()
                and (not status or row["status"] == status) and (not doc_type or row["doc_type"] == doc_type)]
        return page_of(rows, page, page_size, "owner_upload_metadata+sqlite.parse_tasks")

    @router.get("/api/documents/{file_id}", response_model=DocumentInfo)
    @guarded
    def document(file_id: str, identity=Depends(owner)):
        reader.upload(identity, file_id)
        return next(row for row in reader.documents(identity) if row["file_id"] == file_id)

    @router.get("/api/documents/{file_id}/parse-history", response_model=ListResponse)
    @guarded
    def history(file_id: str, page: int = pagination, page_size: int = size, identity=Depends(owner)):
        reader.upload(identity, file_id)
        rows = [{"task": safe(public(task)), "file_id": file["id"], "source_file_id": file_id,
                 "database_parse_id": file.get("database_parse_id"), "elapsed_seconds": task.get("elapsed_seconds")}
                for task, file in reader.history(identity, file_id)]
        return page_of(rows, page, page_size, "sqlite.parse_tasks")

    @router.get("/api/parse/files/{file_id}/source", response_class=FileResponse)
    @router.head("/api/parse/files/{file_id}/source", include_in_schema=False)
    @guarded
    def source(file_id: str, identity=Depends(owner)):
        value, path = reader.upload(identity, file_id)
        if not path.is_file():
            raise MinerUError("source_not_found", 404)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != value["sha256"] or path.stat().st_size != value["bytes"]:
            raise MinerUError("source_integrity_mismatch", 409)
        media = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[path.suffix]
        return FileResponse(path, media_type=media, filename=value["file_name"],
                            content_disposition_type="attachment" if path.suffix == ".docx" else "inline",
                            headers={"X-SHA256": value["sha256"], "X-Content-Type-Options": "nosniff",
                                     "Content-Security-Policy": "sandbox", "Cache-Control": "private, no-store"})


    app.include_router(router)
