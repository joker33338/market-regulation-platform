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

def register_review(app, service, config, owner, reader):
    router = APIRouter(tags=["review"], dependencies=[Depends(owner)])
    pagination = Query(default=1, ge=1)
    size = Query(default=20, ge=1, le=100)

    @router.get("/api/review", response_model=ListResponse)
    @guarded
    def reviews(page: int = pagination, page_size: int = size, requires_review: bool = True, identity=Depends(owner)):
        return safe(reader.review_store().listing(identity, page, page_size, requires_review))

    @router.get("/api/review/{parse_id}", response_model=ReviewDetail)
    @guarded
    def review(parse_id: str, identity=Depends(owner)):
        return reader.review_detail(identity, parse_id)


    app.include_router(router)
