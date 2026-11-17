"""向前端提供明确能力口径，配置存在不代表数据库健康或单次操作获准。"""
from fastapi import Depends
import os
from pydantic import BaseModel
from .contracts import CONTRACT_VERSION
from .principals import PrincipalInfo
from .principals import principal_info


class PasswordCapability(BaseModel):
    implemented: bool
    configured: bool
    registration: str


class ReviewCapability(BaseModel):
    implemented: bool
    ledger_configured: bool
    per_object_gate: bool


class IngestionCapability(BaseModel):
    document_types: list[str]
    review_required: bool
    quality_required: bool
    manual_revision_export: bool
    auto_publish: bool
    admin_required: bool
    write_configured: bool


class TaskLogCapability(BaseModel):
    historical_backfill: bool
    source: str


class OperationalLogCapability(BaseModel):
    request_bodies: bool
    credentials: bool
    historical_backfill: bool


class CapabilitiesResponse(BaseModel):
    contract_version: str
    admin_policy: str
    identity: PrincipalInfo
    password_login: PasswordCapability
    review: ReviewCapability
    document_filters: list[str]
    search_filters: list[str]
    search_version_scope: str
    ingestion: IngestionCapability
    task_logs: TaskLogCapability
    operational_logs: OperationalLogCapability


def register_capabilities(app,principal):
    from .document_delete import DocumentDeletionError
    @app.get('/api/system/capabilities',tags=['monitoring'],response_model=CapabilitiesResponse,
             responses={code:{'model':DocumentDeletionError} for code in (401,403,503)})
    def capabilities(identity=Depends(principal)):
        return {'contract_version':CONTRACT_VERSION,'admin_policy':'all_permissions',
                'identity':principal_info(identity),
                'password_login':{'implemented':True,'configured':bool(app.state.account_store.filename),'registration':'admin_only'},
                'review':{'implemented':True,'ledger_configured':app.state.review_ledger is not None,'per_object_gate':True},
                'document_filters':['date_from','date_to','sort_by','order'],
                'search_filters':['kb_version','issuing_authority','effective_status','document_type'],
                'search_version_scope':'published_active_or_archived',
                'ingestion':{'document_types':['law','case'],'review_required':True,'quality_required':True,
                             'manual_revision_export':True,'auto_publish':False,'admin_required':True,
                             'write_configured':bool(os.getenv('KNOWLEDGE_WRITE_PG_DSN'))},
                'task_logs':{'historical_backfill':False,'source':'persisted_state_transitions'},
                'operational_logs':{'request_bodies':False,'credentials':False,'historical_backfill':False}}
