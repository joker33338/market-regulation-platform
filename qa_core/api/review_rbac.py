"""审核读写权限入口；审核员范围不扩展到任务修改或知识库发布。"""
from qa_core.api.principals import owner_selector, data_owner
from qa_core.document_parsing.mineru_client import MinerUError


def review_source(reader, principal, parse_id):
    row = reader.review_store().detail(owner_selector(principal),parse_id)
    return row, data_owner(principal,row)


def require_reviewer(principal):
    if 'REVIEWER' not in principal.roles and not principal.is_admin:
        raise MinerUError('review_write_forbidden',403)


def readable_upload(reader, principal, file_id):
    if principal.is_admin:
        return reader.upload(principal.read_owners,file_id)
    for owner_id in principal.read_owners:
        try:
            return reader.upload(owner_id,file_id)
        except MinerUError as exc:
            if exc.status != 404:
                raise
    raise MinerUError('source_not_found',404)
