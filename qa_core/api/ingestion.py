"""入库预检、候选构建和显式发布；复用业务服务，不把审核当作发布。"""
from datetime import datetime, timezone
import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.utils import IngestionError
from .common import guarded, page_of
from .private_operations import OperationStore, digest, grant
from .source_segments import SourceRange, slice_result
from .principals import owner_selector


class IngestionDocument(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    parse_id: str=Field(min_length=1,max_length=128)
    law_name: str=Field(min_length=1,max_length=256)
    law_id: str=Field(min_length=1,max_length=128)
    expected_review_version: int=Field(ge=1)
    document_type: Literal["law","case"]="law"
    source_range: SourceRange | None = None


class IngestionBatchRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kb_version: str=Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$')
    documents: list[IngestionDocument]=Field(min_length=1,max_length=20)
    full_snapshot: bool=False


class ReleaseRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kb_version: str=Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$')
    expected_active_version: str | None=Field(...,max_length=128)


class PrecheckItem(BaseModel):
    parse_id: str
    review_version: int
    chunk_count: int
    quality_passed: bool | None=None
    eligible: bool=True
    error_code: str | None=None


class PrecheckResponse(BaseModel):
    eligible: bool
    documents: list[PrecheckItem]
    active_version: str | None
    target_exists: bool
    write_performed: bool=False
    publish_authorized: bool=False


class VersionCheckResponse(BaseModel):
    kb_version: str
    status: str
    base_version: str | None
    active_version: str | None
    is_active: bool
    base_matches_active: bool
    publish_eligible: bool
    rollback_eligible: bool
    write_performed: bool=False
    publish_authorized: bool=False


class KnowledgeOperation(BaseModel):
    operation_id: str
    operator_id: str
    action: str
    kb_version: str
    status: str
    created_at: str
    completed_at: str | None=None
    write_performed: bool | None=False
    publish_authorized: bool=False
    result: dict | None=None
    error_code: str | None=None
    event_id: str | None=None
    execution_live: bool=False
    outcome_unconfirmed: bool=False
    stage_summary: dict[str,dict]=Field(default_factory=dict)


class KnowledgeOperationPage(BaseModel):
    list: list[KnowledgeOperation]
    total: int
    page: int
    page_size: int
    source: str


def source_fingerprint(row):
    from qa_core.storage.mysql_review_ledger import canonical,digest as review_digest
    return review_digest(canonical({'document_id':row['document_id'],'original_result':row['original_result'],
        'raw_text':row.get('raw_text'),'markdown_content':row.get('markdown_content')}))


def register_ingestion(app, principal, reader, config):
    from .document_delete import DocumentDeletionError
    errors={code:{'model':DocumentDeletionError} for code in (401,403,404,409,422,429,503)}
    router=APIRouter(tags=['ingestion'],dependencies=[Depends(principal)],responses=errors)
    operations=OperationStore(config.result_dir)
    app.state.knowledge_operations=operations
    active_builds=set()

    def prepare(body,identity,scopes=None):
        from qa_core.document_parsing.bridge import to_legal_document
        from qa_core.document_parsing.schemas import DocumentResult
        from qa_core.indexing.service import preview_documents
        ledger=app.state.review_ledger
        if ledger is None:
            raise MinerUError('review_ledger_not_configured',503)
        ledger.health()
        documents=[];checks=[];identities=set();parse_ids=set()
        for item in body.documents:
            if item.law_id in identities or item.parse_id in parse_ids:
                raise MinerUError('duplicate_law_identity',422)
            identities.add(item.law_id)
            parse_ids.add(item.parse_id)
            row=reader.review_store().detail(scopes if scopes is not None else owner_selector(identity),item.parse_id)
            target_owner=row.get('source_location',{}).get('owner_id')
            allowed=scopes if scopes is not None else identity.read_owners
            if target_owner not in allowed:
                raise MinerUError('document_not_found',404)
            state=ledger.verify_for_ingestion(target_owner,item.parse_id,source_fingerprint(row),item.expected_review_version)
            # 人工修订尚无经确认的正文导出协议，不能默默把旧OCR正文入库。
            from .reviewed_export import export_reviewed_result
            reviewed_result = export_reviewed_result(row, state, ledger, target_owner)
            full_reviewed_text = reviewed_result.raw_text
            if item.source_range is not None:
                if not state.get('current_revision') and full_reviewed_text!=row.get('raw_text'):
                    raise MinerUError('source_scope_source_mismatch',409)
                reviewed_result = slice_result(reviewed_result, item.source_range)
            source_id=row.get('source_location',{}).get('source_file_id')
            value,path=reader.upload(target_owner,source_id or '')
            from qa_core.utils import file_sha256
            if value['sha256']!=row['document_id'] or row['original_result'].get('document_id')!=row['document_id'] or file_sha256(path)!=value['sha256']:
                raise MinerUError('ingestion_source_mismatch',409)
            events=ledger.events(target_owner,item.parse_id,1,1)['list']
            if not events or events[0]['version']!=state['version'] or events[0]['action']!='approve' or not events[0].get('operator_id'):
                raise MinerUError('review_approval_required',409)
            try:
                if item.document_type == "case":
                    from qa_core.document_parsing.case_bridge import to_case_document
                    document=to_case_document(reviewed_result,
                        reviewer=events[0]['operator_id'],title=item.law_name,business_id=item.law_id)
                else:
                    document=to_legal_document(reviewed_result,
                        reviewer=events[0]['operator_id'],law_name=item.law_name,law_id=item.law_id)
                document.source_path=str(path)
                if state.get('current_revision'):
                    document.metadata['reviewed_text'] = full_reviewed_text
                    document.metadata['reviewed_page_revisions'] = reviewed_result.quality['reviewed_page_revisions']
                if item.source_range is not None:
                    document.metadata['source_range'] = item.source_range.model_dump()
                document.metadata['api_review_reference']={'owner_id':target_owner,'parse_id':item.parse_id,
                    'source_digest':source_fingerprint(row),'version':state['version'], 'revision_id':state.get('current_revision')}
                preview=preview_documents([document])
            except IngestionError:
                raise MinerUError('ingestion_quality_blocked',409) from None
            documents.append(document)
            checks.append({'parse_id':item.parse_id,'review_version':state['version'],
                           'chunk_count':preview['chunk_count'],'quality_passed':True})
        return documents,checks

    @router.post('/api/ingestion/precheck',response_model=PrecheckResponse)
    @guarded
    def precheck(body: IngestionBatchRequest,identity=Depends(principal)):
        if len({item.law_id for item in body.documents})!=len(body.documents) or len({item.parse_id for item in body.documents})!=len(body.documents):
            raise MinerUError('duplicate_law_identity',422)
        checks=[]
        for item in body.documents:
            try:
                _,entries=prepare(body.model_copy(update={'documents':[item]}),identity)
                checks.extend(entries)
            except MinerUError as error:
                if error.status not in {409,422}:
                    raise
                checks.append({'parse_id':item.parse_id,'review_version':item.expected_review_version,'chunk_count':0,
                               'quality_passed':False if error.code=='ingestion_quality_blocked' else None,
                               'eligible':False,'error_code':error.code})
        database=reader.kb_factory()
        try:
            with database.transaction(read_only=True):
                active=database.active_version()
                existing=database.one('SELECT status FROM mr_kb_versions WHERE kb_version=:v',{'v':body.kb_version})
            return {'eligible':existing is None and all(item.get('eligible',True) for item in checks),
                    'documents':checks,'active_version':active,'target_exists':existing is not None}
        finally:
            database.close()

    def public_operation(value):
        live=value['operation_id'] in active_builds and value['status']=='RUNNING'
        return {**{key:item for key,item in value.items() if key!='fingerprint'},
                'execution_live':live,'outcome_unconfirmed':value['status']=='RUNNING' and not live}

    @router.get('/api/ingestion/batches',response_model=KnowledgeOperationPage)
    @guarded
    def batches(page: int=Query(1,ge=1),page_size: int=Query(20,ge=1,le=100),identity=Depends(principal)):
        rows=[]
        for path in operations.root.glob('*.json'):
            value=json.loads(path.read_text(encoding='utf-8'))
            if value['action']=='build' and (identity.is_admin or value['operator_id']==identity.principal_id):
                rows.append(public_operation(value))
        return page_of(sorted(rows,key=lambda row:row['created_at'],reverse=True),page,page_size,'private_knowledge_operation_receipts')

    @router.get('/api/ingestion/batches/{batch_id}',response_model=KnowledgeOperation)
    @guarded
    def batch(batch_id: str,identity=Depends(principal)):
        value=operations.read(batch_id)
        if not value or not identity.is_admin and value['operator_id']!=identity.principal_id or value['action']!='build':
            raise MinerUError('batch_not_found',404)
        return public_operation(value)

    @router.post('/api/ingestion/batches',response_model=KnowledgeOperation,status_code=201)
    @guarded
    def build(body: IngestionBatchRequest,idempotency_key: str=Header(min_length=1,max_length=128),identity=Depends(principal)):
        scopes=grant(identity,'build',body.kb_version)
        operation_id=operations.identifier(identity.principal_id,'build',idempotency_key)
        fingerprint=digest(body.model_dump())
        with operations.locked():
            previous=operations.replay(operation_id,fingerprint)
            if previous:
                if previous['status']=='RUNNING':
                    raise MinerUError('ingestion_outcome_unconfirmed',409)
                if previous['status']=='FAILED':
                    raise MinerUError('ingestion_previous_failed',409)
                return public_operation(previous)
            documents,_=prepare(body,identity,scopes)
            if not reader._search_lock.acquire(blocking=False):
                raise MinerUError('model_busy',429)
            database=None
            try:
                database=reader.kb_write_factory()
                from qa_core.storage.library_projection import ensure_projection_schema,project_library
                ensure_projection_schema(database, reviewed_text=any(doc.metadata.get("reviewed_text") and doc.metadata.get("document_type","law")=="law" for doc in documents))
                with database.transaction(read_only=True):
                    if database.one('SELECT status FROM mr_kb_versions WHERE kb_version=:v',{'v':body.kb_version}):
                        raise MinerUError('knowledge_version_exists',409)
                value={'operation_id':operation_id,'fingerprint':fingerprint,'operator_id':identity.principal_id,
                       'action':'build','kb_version':body.kb_version,'status':'RUNNING',
                       'created_at':datetime.now(timezone.utc).isoformat(),'write_performed':False,'publish_authorized':False,
                       'stage_summary':{'precheck':{'status':'COMPLETED','succeeded':len(documents),'failed':0},
                                        'ingestion':{'status':'RUNNING','succeeded':None,'failed':None}}}
                operations.save(value)
                active_builds.add(operation_id)
                from qa_core.config.settings import Settings
                from qa_core.indexing.service import ingest_documents
                try:
                    reader._embeddings=reader._embeddings or reader.embeddings_factory()
                    result=ingest_documents(documents,database=database,embeddings=reader._embeddings,
                        settings=Settings.from_env(),version=body.kb_version,full_snapshot=body.full_snapshot,
                        before_finish=project_library)
                except Exception as error:
                    value.update(status='FAILED',error_code='ingestion_quality_blocked' if isinstance(error,IngestionError) else 'ingestion_failed',
                                 completed_at=datetime.now(timezone.utc).isoformat(),write_performed=None)
                    value['stage_summary']['ingestion']['status']='FAILED'
                    operations.save(value)
                    raise MinerUError(value['error_code'],409 if isinstance(error,IngestionError) else 503) from None
                value.update(status='STAGED',result=result,write_performed=True,completed_at=datetime.now(timezone.utc).isoformat())
                value['stage_summary']['ingestion']={'status':'COMPLETED','succeeded':result['documents_seen'],'failed':0}
                operations.save(value)
                return public_operation(value)
            finally:
                active_builds.discard(operation_id)
                try:
                    if database is not None:
                        database.close()
                finally:
                    reader._search_lock.release()

    @router.get('/api/ingestion/version-check',response_model=VersionCheckResponse)
    @guarded
    def version_check(kb_version: str=Query(min_length=1,max_length=128),identity=Depends(principal)):
        database=reader.kb_factory()
        try:
            with database.transaction(read_only=True):
                active=database.active_version()
                row=database.one('SELECT kb_version,status,base_version FROM mr_kb_versions WHERE kb_version=:v',{'v':kb_version})
                if row is None:
                    raise MinerUError('version_not_found',404)
                return {**row,'active_version':active,'is_active':active==kb_version,
                        'base_matches_active':row['base_version']==active,
                        'publish_eligible':row['status']=='STAGED' and row['base_version']==active,
                        'rollback_eligible':row['status']=='ARCHIVED','write_performed':False,'publish_authorized':False}
        finally:
            database.close()

    def release_endpoint(action):
        @guarded
        def release(body: ReleaseRequest,idempotency_key: str=Header(min_length=1,max_length=128),identity=Depends(principal)):
            grant(identity,action,body.kb_version)
            operation_id=operations.identifier(identity.principal_id,action,idempotency_key)
            fingerprint=digest(body.model_dump())
            with operations.locked():
                value=operations.replay(operation_id,fingerprint)
                if value and value['status']=='COMPLETED':
                    return public_operation(value)
                database=reader.kb_write_factory()
                try:
                    if value:
                        with database.transaction(read_only=True):
                            history=database.one('SELECT event_id FROM mr_release_history WHERE event_id=:id',{'id':value['event_id']})
                        if history:
                            value.update(status='COMPLETED',write_performed=True,completed_at=datetime.now(timezone.utc).isoformat())
                            operations.save(value)
                            return public_operation(value)
                    else:
                        value={'operation_id':operation_id,'fingerprint':fingerprint,'operator_id':identity.principal_id,
                               'action':action,'kb_version':body.kb_version,'status':'PREPARED','event_id':uuid4().hex,
                               'created_at':datetime.now(timezone.utc).isoformat(),'write_performed':False,'publish_authorized':True}
                        operations.save(value)
                    try:
                        from qa_core.governance.kb_versions import publish,rollback
                        with database.transaction(read_only=True):
                            metadata=database.all('''SELECT v.metadata FROM mr_document_versions v JOIN mr_kb_documents d
                                ON d.doc_version_id=v.doc_version_id WHERE d.kb_version=:v''',{'v':body.kb_version})
                        references=[]
                        for item in metadata:
                            source_metadata=json.loads(item['metadata']) if isinstance(item['metadata'],str) else item['metadata']
                            reference=source_metadata.get('api_review_reference')
                            if not isinstance(reference,dict):
                                raise MinerUError('knowledge_review_provenance_required',409)
                            # 当前解析原文仍须与被审批的摘要一致，不复用过期批准。
                            current=reader.review_store().detail(reference['owner_id'],reference['parse_id'])
                            if source_fingerprint(current)!=reference['source_digest']:
                                raise MinerUError('review_source_changed',409)
                            references.append(reference)
                        if not references:
                            raise MinerUError('knowledge_empty_version',409)
                        ledger=app.state.review_ledger
                        if ledger is None:
                            raise MinerUError('review_ledger_not_configured',503)
                        # 共享锁持续到PG发布事务完成，避免撤回审核与发布并发越过门禁。
                        with ledger.verified_ingestion_scope(references):
                            (rollback if action=='rollback' else publish)(database,body.kb_version,
                                expected_active=body.expected_active_version,event_id=value['event_id'])
                    except IngestionError:
                        raise MinerUError('knowledge_release_conflict',409) from None
                    value.update(status='COMPLETED',write_performed=True,completed_at=datetime.now(timezone.utc).isoformat())
                    operations.save(value)
                    return public_operation(value)
                finally:
                    database.close()
        return release

    router.add_api_route('/api/ingestion/publish',release_endpoint('publish'),methods=['POST'],response_model=KnowledgeOperation)
    router.add_api_route('/api/ingestion/rollback',release_endpoint('rollback'),methods=['POST'],response_model=KnowledgeOperation)
    app.state.knowledge_hooks = {"build": build, "precheck": precheck, "check": version_check, "publish": release_endpoint('publish')}
    app.include_router(router)
