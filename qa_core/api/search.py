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

def register_search(app, service, config, owner, reader):
    router = APIRouter(tags=["search"], dependencies=[Depends(owner)])
    pagination = Query(default=1, ge=1)
    size = Query(default=20, ge=1, le=100)

    @router.post("/api/knowledge/search", response_model=SearchResponse)
    @guarded
    def search(body: SearchRequest):
        return reader.search(body)


    app.include_router(router)
