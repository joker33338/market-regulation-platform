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
from .workbench_schemas import ReviewedText
from .principals import owner_selector, data_owner
from .schemas import (DocumentInfo, DocumentList, HealthResponse, ListResponse, PreviewRequest,
                      PreviewResponse, ReviewDetail, SearchRequest, SearchResponse, StatsResponse, VersionInfo)

def register_review(app, service, config, owner, reader):
    router = APIRouter(tags=["review"], dependencies=[Depends(owner)])
    pagination = Query(default=1, ge=1)
    size = Query(default=20, ge=1, le=100)

    @router.get("/api/review", response_model=ListResponse)
    @guarded
    def reviews(page: int = pagination, page_size: int = size, requires_review: bool = True, identity=Depends(owner)):
        return safe(reader.review_store().listing(owner_selector(identity), page, page_size, requires_review))

    @router.get("/api/review/{parse_id}", response_model=ReviewDetail)
    @guarded
    def review(parse_id: str, identity=Depends(owner)):
        result = reader.review_detail(owner_selector(identity), parse_id)
        target_owner = data_owner(identity, result)
        ledger = app.state.review_ledger
        result['review_ledger'] = {'available': False, 'reason': 'not_configured'}
        if ledger is not None:
            try:
                ledger.health()
                result['review_ledger'] = {'available': True, 'reason': None, **ledger.state(target_owner, parse_id)}
                result['review_write_supported'] = identity.can_review(target_owner)
            except Exception:
                result['review_ledger'] = {'available': False, 'reason': 'ledger_unavailable'}
        return result


    @router.get("/api/review/{parse_id}/reviewed-text",response_model=ReviewedText)
    @guarded
    def reviewed_text(parse_id: str,identity=Depends(owner)):
        source=reader.review_store().detail(owner_selector(identity),parse_id)
        target_owner=data_owner(identity,source)
        ledger=app.state.review_ledger
        if ledger is None:
            from qa_core.document_parsing.mineru_client import MinerUError
            raise MinerUError('review_ledger_not_configured',503)
        state=ledger.state(target_owner,parse_id)
        from .reviewed_export import export_reviewed_result
        result=export_reviewed_result(source,state,ledger,target_owner)
        return {'parse_id':parse_id,'review_version':state['version'],'approved':state['status']=='approved',
                'original_unchanged':True,'pages':[{'page_number':page.page_number,'text':page.raw_text}
                                                  for page in result.pages],
                'revisions':result.quality.get('reviewed_page_revisions',[])}

    app.include_router(router)
