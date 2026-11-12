"""现有业务服务的权限隔离 HTTP 查询适配。"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
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

def register_knowledge(app, service, config, owner, reader):
    router = APIRouter(tags=["knowledge"], dependencies=[Depends(owner)])
    pagination = Query(default=1, ge=1)
    size = Query(default=20, ge=1, le=100)

    @router.post("/api/review/{parse_id}/preview", response_model=PreviewResponse)
    @guarded
    def review_preview(parse_id: str, body: PreviewRequest, identity=Depends(owner)):
        row = reader.review_store().detail(identity, parse_id)
        return preview(row["original_result"], body)

    def preview(value, body):
        from qa_core.document_parsing.schemas import DocumentResult
        from qa_core.indexing.preview import preview_chunks
        try:
            result = preview_chunks(DocumentResult.from_dict(value), body.document_type, max_chars=body.max_chars)
        except IngestionError:
            raise MinerUError("chunk_preview_blocked", 409) from None
        return {"preview": safe(result), "write_performed": False}

    @router.post("/api/parse/tasks/{task_id}/files/{file_id}/preview", response_model=PreviewResponse)
    @guarded
    def task_preview(task_id: str, file_id: str, body: PreviewRequest, identity=Depends(owner)):
        task, file = reader.task_file(identity, task_id, file_id)
        value = reader.candidate(task, file)
        if value is None:
            raise MinerUError("result_not_found", 404)
        return preview(value, body)

    @router.get("/api/knowledge/versions", response_model=ListResponse)
    @guarded
    def versions(page: int = pagination, page_size: int = size):
        database = reader.kb_factory()
        try:
            with database.transaction(read_only=True):
                active = database.active_version()
                rows = [version_value(row, active) for row in reversed(database.list_versions())]
            return page_of(rows, page, page_size, "public.mr_kb_versions")
        finally:
            database.close()

    def version_value(row, active):
        row = dict(row)
        stats = row["stats"]
        row["stats"] = safe(json.loads(stats) if isinstance(stats, str) else stats)
        return {key: row[key] for key in ("kb_version", "status", "dimension", "created_at", "stats")} | {
            "active": row["kb_version"] == active}

    @router.get("/api/knowledge/versions/{version}", response_model=VersionInfo)
    @guarded
    def version(version: str):
        database = reader.kb_factory()
        try:
            with database.transaction(read_only=True):
                active = database.active_version()
                # 使用显式查询区分不存在与服务故障，不吞掉 Schema 安全错误。
                row = database.one("SELECT * FROM mr_kb_versions WHERE kb_version=:v", {"v": version})
                if row is None:
                    raise MinerUError("version_not_found", 404)
                return version_value(row, active)
        finally:
            database.close()


    app.include_router(router)
