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

    @router.delete('/api/documents/{file_id}',response_model=DocumentDeletion,
        description='显式ADMIN与本人owner删除范围授权；仅未形成解析/审核/入库证据链的上传可软删除。重复删除404；不销毁原件或关联记录。')
    @guarded
    def remove(file_id: str = Path(pattern='^[a-f0-9]{32}$'),identity=Depends(principal)):
        return delete_document(reader,identity,file_id,app.state.document_delete_references)

    app.include_router(router)
