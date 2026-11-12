"""高权限单文档软删除HTTP契约。"""
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from .common import guarded
from qa_core.storage.document_lifecycle import delete_document


class DeletionDisposition(BaseModel):
    mode: Literal['soft_delete']
    original_bytes: Literal['retained']
    metadata: Literal['quarantined']
    related_records: Literal['unchanged']


class DocumentDeletion(BaseModel):
    file_id: str
    deleted: Literal[True]
    deleted_at: datetime
    disposition: DeletionDisposition


class MachineError(BaseModel):
    code: str


class DocumentDeletionError(BaseModel):
    error: MachineError


def register_document_delete(app,principal,reader):
    router=APIRouter(tags=['documents'],dependencies=[Depends(principal)])

    def references(owner,file_id,value):
        if reader.review_store().deletion_references(file_id,value['sha256']):
            return True
        database=reader.kb_factory()
        try:
            with database.transaction(read_only=True):
                return database.one('SELECT 1 AS found FROM mr_document_versions WHERE source_hash=:hash LIMIT 1',{'hash':value['sha256']}) is not None
        finally:
            database.close()

    app.state.document_delete_references=references

    errors={status:{'model':DocumentDeletionError,'description':description} for status,description in {
        401:'缺失或失效凭证',403:'未获显式删除授权或跨owner',404:'不存在或已删除',
        409:'任务、证据链、版本引用或生命周期锁冲突',422:'file_id格式非法',503:'存储或引用核查不可用'}.items()}

    @router.delete('/api/documents/{file_id}',response_model=DocumentDeletion,responses=errors,
        description='ADMIN可删除任意owner下未形成解析/审核/入库证据链的上传；其他角色403。重复删除404；不销毁原件或关联记录。')
    @guarded
    def remove(file_id: str = Path(pattern='^[a-f0-9]{32}$'),identity=Depends(principal)):
        return delete_document(reader,identity,file_id,app.state.document_delete_references)

    app.include_router(router)
