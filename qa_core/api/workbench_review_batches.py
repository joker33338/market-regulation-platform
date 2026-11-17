"""显式人工确认的批量审核队列；冻结每项身份和版本，逐项重新授权。"""
from collections import Counter
import time
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from .common import guarded, page_of
from .workbench_schemas import ReviewBatchStatus,ReviewBatchItemPage
from .ingestion import source_fingerprint
from .private_operations import OperationStore, digest
from .review_rbac import require_reviewer, review_source
from .review_writes import ReviewAction
from qa_core.document_parsing.mineru_client import MinerUError


class ReviewTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    parse_id: str = Field(min_length=1, max_length=128)
    expected_review_version: int = Field(ge=0)
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReviewBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["approve", "reject"]
    reason: str = Field(default="", max_length=2000)
    targets: list[ReviewTarget] = Field(default_factory=list, max_length=100)
    selection_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    attested: bool = False


class ReviewBatchAppend(BaseModel):
    model_config = ConfigDict(extra="forbid")
    targets: list[ReviewTarget] = Field(min_length=1, max_length=100)


class ReviewBatches(OperationStore):
    def __init__(self, app, reader, root):
        super().__init__(root)
        self.root=self.root.parent/".file-review-batches"
        self.app,self.reader=app,reader

    def owned(self,batch_id,identity):
        value=self.read(batch_id)
        if not value or value['principal_id']!=identity.principal_id:
            raise MinerUError('review_batch_not_found',404)
        return value

    def add(self,value,targets,identity):
        known={entry['entry_id'] for entry in value['items']}
        ledger=self.app.state.review_ledger
        if ledger is None:raise MinerUError('review_ledger_not_configured',503)
        for target in targets:
            entry_id=digest(target.model_dump())
            if entry_id in known:continue
            item={**target.model_dump(),'entry_id':entry_id,'status':'queued','lease_until':0}
            try:
                row,owner=review_source(self.reader,identity,target.parse_id)
                if not identity.can_review(owner):raise MinerUError('review_write_forbidden',403)
                if row['source_location'].get('source_file_id')!=target.file_id or row['document_id']!=target.expected_sha256:
                    raise MinerUError('review_source_changed',409)
                state=ledger.state(owner,target.parse_id)
                if state['version']!=target.expected_review_version:raise MinerUError('review_version_conflict',409)
                item.update(owner_id=owner,source_digest=source_fingerprint(row),file_name=row['file_name'])
            except MinerUError as error:
                item.update(status='failed',error_code=error.code)
            value['items'].append(item);known.add(entry_id)

    @staticmethod
    def public(value):
        return {'batch_id':value['operation_id'],'action':value['action'],'total':len(value['items']),
                'counts':dict(Counter(item['status'] for item in value['items']))}

    def claim(self):
        with self.locked():
            for path in sorted(self.root.glob('*.json')):
                value=self.read(path.stem)
                for item in value['items']:
                    if item['status']=='queued' or item['status']=='running' and item.get('lease_until',0)<time.time():
                        item.update(status='running',lease_until=time.time()+300);self.save(value)
                        return value,item.copy()
        return None

    def tick(self):
        claimed=self.claim()
        if not claimed:return
        batch,item=claimed
        try:
            identity=self.app.state.workbench_ingestion.identity(batch['principal_id'])
            if identity is None:raise MinerUError('unauthorized',401)
            require_reviewer(identity)
            row,owner=review_source(self.reader,identity,item['parse_id'])
            if not identity.can_review(owner) or owner!=item['owner_id']:raise MinerUError('review_write_forbidden',403)
            if source_fingerprint(row)!=item['source_digest']:raise MinerUError('review_source_changed',409)
            body=ReviewAction(base_result_id=item['parse_id'],expected_version=item['expected_review_version'],
                              reason=batch['reason'])
            receipt=self.app.state.review_hooks[batch['action']](
                parse_id=item['parse_id'],body=body,idempotency_key=digest([batch['operation_id'],item['entry_id']]),identity=identity)
            if not receipt.get('write_performed'):raise MinerUError('review_outcome_unconfirmed',409)
            changes={'status':'completed','event_id':receipt['event_id']}
        except MinerUError as error:changes={'status':'failed','error_code':error.code}
        except Exception:changes={'status':'failed','error_code':'review_service_unavailable'}
        with self.locked():
            current=self.read(batch['operation_id'])
            for target in current['items']:
                if target['entry_id']==item['entry_id']:target.update(**changes)
            self.save(current)


def register_workbench_review_batches(app,principal,reader,config):
    store=ReviewBatches(app,reader,config.result_dir)
    app.state.review_batches=store
    router=APIRouter(tags=['file-workbench'])

    @router.post('/api/workbench/review-batches',status_code=202,response_model=ReviewBatchStatus)
    @guarded
    def create(body:ReviewBatchRequest,idempotency_key:str=Header(min_length=1,max_length=128),identity=Depends(principal)):
        require_reviewer(identity)
        if not body.attested:raise MinerUError('review_attestation_required',422)
        if body.action=='reject' and not body.reason.strip():raise MinerUError('review_reason_required',422)
        if body.selection_id and body.targets:raise MinerUError('ambiguous_review_selection',422)
        operation_id=store.identifier(identity.principal_id,'review-batch',idempotency_key)
        fingerprint=digest(body.model_dump())
        with store.locked():
            value=store.replay(operation_id,fingerprint)
            if value:return store.public(value)
            targets=body.targets
            if body.selection_id:
                selections=OperationStore(config.result_dir)
                selections.root=selections.root.parent/'.file-workbench-selections'
                snapshot=selections.read(body.selection_id)
                if not snapshot or snapshot['principal_id']!=identity.principal_id:raise MinerUError('selection_not_found',404)
                if snapshot['expires_at']<=time.time():raise MinerUError('selection_expired',409)
                if any(not row.get('parse_id') or row.get('review_version') is None for row in snapshot['files']):
                    raise MinerUError('selection_not_reviewable',409)
                targets=[ReviewTarget(file_id=row['file_id'],parse_id=row['parse_id'],
                    expected_review_version=row['review_version'],expected_sha256=row['sha256']) for row in snapshot['files']]
            if not targets:raise MinerUError('review_selection_empty',422)
            value={'operation_id':operation_id,'fingerprint':fingerprint,'principal_id':identity.principal_id,
                   'action':body.action,'reason':body.reason or '操作者确认已核对本批所选文档的原件与识别正文。','items':[]}
            store.add(value,targets,identity);store.save(value)
            return store.public(value)

    @router.get('/api/workbench/review-batches/{batch_id}',response_model=ReviewBatchStatus)
    @guarded
    def detail(batch_id:str,identity=Depends(principal)):
        return store.public(store.owned(batch_id,identity))

    @router.get('/api/workbench/review-batches/{batch_id}/items',response_model=ReviewBatchItemPage)
    @guarded
    def results(batch_id:str,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),identity=Depends(principal)):
        value=store.owned(batch_id,identity)
        result=page_of(value['items'],page,page_size,'frozen_review_batch_items')
        from .review_rbac import readable_upload
        rows=[]
        for item in result['list']:
            public={'file_id':item['file_id'],'status':item['status'],'error_code':item.get('error_code')}
            try:
                readable_upload(reader,identity,item['file_id'])
                public['file_name']=item.get('file_name') or '未取得名称的文件'
            except MinerUError:
                public.update(status='failed',error_code='source_not_found')
            rows.append(public)
        return {**result,'list':rows}

    @router.post('/api/workbench/review-batches/{batch_id}/items',response_model=ReviewBatchStatus)
    @guarded
    def append(batch_id:str,body:ReviewBatchAppend,identity=Depends(principal)):
        require_reviewer(identity)
        with store.locked():
            value=store.owned(batch_id,identity);store.add(value,body.targets,identity);store.save(value)
            return store.public(value)

    app.include_router(router)
