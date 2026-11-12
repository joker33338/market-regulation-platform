"""审核动作适配：权限来自服务端，修订追加保存，不自动重解析或发布。"""
from typing import Literal
from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.storage.mysql_review_ledger import canonical, digest
from .common import guarded
from .schemas import ListResponse


class ReviewAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_result_id: str = Field(min_length=1, max_length=128)
    expected_version: int = Field(ge=0)
    reason: str = Field(default='', max_length=2000)
    page: int | None = Field(default=None, ge=1)
    content: str | None = Field(default=None, min_length=1, max_length=200000)
    span: str | None = Field(default=None, max_length=2000)


class ReviewReceipt(BaseModel):
    event_id: str
    parse_id: str
    base_result_id: str
    action: str
    operator: str
    timestamp: str
    version: int
    revision_id: str | None
    status: str
    before: dict
    write_performed: bool
    original_result_modified: bool
    publish_authorized: bool
    reparse_task_created: bool


class ReviewEvent(ReviewReceipt):
    # 原始审核请求单独保留；正文/理由不是回执顶层字段。
    request: ReviewAction


class ReviewEventsResponse(ListResponse):
    list: list[ReviewEvent]


def register_review_writes(app, owner, reader):
    router = APIRouter(tags=['review'], dependencies=[Depends(owner)])

    def authorize(identity, parse_id):
        # 先复用PG只读owner检查；不存在或跨owner仍404，不泄露对象存在性。
        source = reader.review_store().detail(identity, parse_id)
        ledger = app.state.review_ledger
        if ledger is None:
            raise MinerUError('review_ledger_not_configured', 503)
        if identity not in ledger.writers:
            raise MinerUError('review_write_forbidden', 403)
        ledger.health()
        return ledger, source

    def endpoint(action):
        @guarded
        def write(parse_id: str, body: ReviewAction,
                  idempotency_key: str = Header(min_length=1, max_length=128), identity=Depends(owner)):
            ledger, source = authorize(identity, parse_id)
            if len(parse_id) > 128 or not parse_id.isascii() or body.base_result_id != parse_id:
                raise MinerUError('review_base_result_mismatch', 409)
            if action in ('reject', 'mark-error') and not body.reason.strip():
                raise MinerUError('review_reason_required', 422)
            if action == 'save-revision' and (body.content is None or not body.content.strip() or body.page is None):
                raise MinerUError('review_revision_fields_required', 422)
            if action != 'save-revision' and body.content is not None:
                raise MinerUError('review_content_not_allowed', 422)
            if action == 'mark-error' and body.page is None:
                raise MinerUError('review_page_required', 422)
            if body.page is not None and body.page not in {page.get('page_number') for page in source['original_result'].get('pages', [])}:
                raise MinerUError('review_page_not_found', 422)
            return ledger.apply(identity, parse_id, action, body.model_dump(), idempotency_key,
                                digest(canonical({'document_id': source['document_id'],
                                                  'original_result': source['original_result'],
                                                  'raw_text': source.get('raw_text'), 'markdown_content': source.get('markdown_content')})))
        return write

    for action in ('approve', 'reject', 'mark-error', 'save-revision'):
        router.add_api_route('/api/review/{parse_id}/'+action, endpoint(action), methods=['POST'],
                             response_model=ReviewReceipt, name='review_'+action.replace('-','_'))

    @router.get('/api/review/{parse_id}/events', response_model=ReviewEventsResponse)
    @guarded
    def events(parse_id: str, page: int = Query(1, ge=1), page_size: int = Query(20,ge=1,le=100), identity=Depends(owner)):
        reader.review_store().detail(identity, parse_id)
        ledger = app.state.review_ledger
        if ledger is None:
            raise MinerUError('review_ledger_not_configured', 503)
        return ledger.events(identity, parse_id, page, page_size)

    @router.get('/api/system/audit-logs', response_model=ListResponse)
    @guarded
    def audit_logs(page: int = Query(1, ge=1), page_size: int = Query(20,ge=1,le=100),
                   action: Literal['approve','reject','mark-error','save-revision'] | None = None,
                   identity=Depends(owner)):
        ledger = app.state.review_ledger
        if ledger is None:
            raise MinerUError('review_ledger_not_configured', 503)
        return ledger.audit_logs(identity, page, page_size, action)

    app.include_router(router)
