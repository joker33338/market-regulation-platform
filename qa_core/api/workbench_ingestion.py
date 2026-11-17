"""用户确认业务信息后自动构建候选；后台重新核验身份，发布始终显式执行。"""
from datetime import datetime, timezone
import time
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from .common import guarded, page_of
from .workbench_schemas import KnowledgeJobStatus, KnowledgeJobPage, SourceSuggestions
from .ingestion import IngestionBatchRequest, ReleaseRequest, VersionCheckResponse
from .private_operations import OperationStore, digest
from .review_rbac import readable_upload
from .source_segments import SourceRange, suggest_segments, text_digest
from qa_core.document_parsing.mineru_client import MinerUError


class PrepareFile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=256)
    document_type: Literal["law", "case"]
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_parse_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_range: SourceRange | None = None
    whole_file_confirmed: bool = False


class KnowledgeJobCheck(VersionCheckResponse):
    document: KnowledgeJobStatus


class PublishJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_active_version: str | None = Field(..., max_length=128)


class KnowledgeJobs(OperationStore):
    def __init__(self, app, reader, root):
        super().__init__(root)
        self.root = self.root.parent / ".file-knowledge-jobs"
        self.app, self.reader = app, reader

    def identity(self, principal_id):
        identities = {item.principal_id: item for item in self.app.state.auth_registry.principals()}
        if self.app.state.account_store.filename:
            _, accounts = self.app.state.account_store.load()
            identities.update(accounts)
        return identities.get(principal_id)

    def accessible(self, job_id, identity):
        value = self.read(job_id)
        if value is None or value["owner_id"] not in identity.read_owners:
            raise MinerUError("knowledge_job_not_found", 404)
        return value

    @staticmethod
    def public(value):
        return {key: value.get(key) for key in
                ("job_id", "file_id", "title", "document_type", "status", "created_at",
                 "updated_at", "error_code", "kb_version", "published_version")}

    def source(self, job):
        # 指定 ID 也必须经过数据库 owner、文件 ID、原件哈希的交叉核验。
        parse_id = job.get("source_parse_id")
        history = self.reader.history(job["owner_id"], job["file_id"])
        if history:
            _, latest = history[0]
            if latest["status"] != "completed":
                raise MinerUError("latest_parse_unfinished", 409)
            if parse_id and latest.get("database_parse_id") != parse_id:
                raise MinerUError("review_source_changed", 409)
        if history:
            parse_id = parse_id or history[0][1].get('database_parse_id')
        else:
            latest = self.reader.review_store().latest_parse_id(job['owner_id'], job['file_id'])
            if parse_id and latest != parse_id:
                raise MinerUError('review_source_changed', 409)
            parse_id = parse_id or latest
        if not parse_id:
            raise MinerUError("parse_result_not_ready", 409)
        row = self.reader.review_store().detail(job["owner_id"], parse_id)
        location = row["source_location"]
        if (location.get("source_file_id") != job["file_id"] or
                location.get("owner_id") != job["owner_id"] or row["document_id"] != job["source_sha256"]):
            raise MinerUError("ingestion_source_mismatch", 409)
        return row

    def create(self, identity, file_id, body, key):
        upload, source_path = readable_upload(self.reader, identity, file_id)
        from .upload_ownership import upload_owner
        owner = upload_owner(self.reader,identity,upload,source_path)
        if not owner or owner not in identity.read_owners:
            raise MinerUError("source_not_found", 404)
        if upload["sha256"] != body.expected_sha256:
            raise MinerUError("ingestion_source_mismatch", 409)
        operation_id = self.identifier(identity.principal_id, "prepare-file", key)
        fingerprint = digest([file_id, body.model_dump()])
        with self.locked():
            previous = self.replay(operation_id, fingerprint)
            if previous:
                return previous
            # 保存业务确认快照；不修改上传元数据或原始解析。
            value = {"operation_id": operation_id, "job_id": operation_id, "fingerprint": fingerprint,
                     "operator_id": identity.principal_id, "owner_id": owner, "file_id": file_id,
                     "source_sha256": upload["sha256"], "source_parse_id": body.source_parse_id,
                     "title": body.title, "document_type": body.document_type, "source_range":body.source_range.model_dump() if body.source_range else None, "whole_file_confirmed":body.whole_file_confirmed,"status": "queued",
                     "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": None,
                     "next_check_at": 0, "kb_version": "workbench-" + operation_id[:24]}
            if body.source_parse_id:
                self.source(value)
            superseded = []
            for path in self.root.glob("*.json"):
                older = self.read(path.stem)
                if (older['owner_id'] != owner or older['source_sha256'] != upload['sha256']
                        or older['status'] == 'superseded'):
                    continue
                before, after = older.get('source_range'), value.get('source_range')
                same_range = before == after
                if older['status'] == 'published':
                    if not same_range or older['document_type'] != value['document_type']:
                        raise MinerUError('published_source_change_requires_replacement', 409)
                    continue
                changed_text = (before and after and
                                before['expected_text_sha256'] != after['expected_text_sha256'])
                if (before and after and not same_range and not changed_text
                        and before['start'] < after['end'] and after['start'] < before['end']):
                    raise MinerUError('source_scope_overlap', 409)
                if same_range or changed_text or not before or not after:
                    superseded.append(older)
            # 先完成全部范围校验，再改变候选状态；冲突不影响此前成功条目。
            for older in superseded:
                older['status'] = 'superseded'
                self.save(older)
            self.save(value)
            return value

    def claim(self):
        with self.locked():
            now = time.time()
            eligible = []
            for path in self.root.glob("*.json"):
                value = self.read(path.stem)
                if (value["status"] in {"queued", "awaiting_parse", "awaiting_review", "awaiting_admin", "building"}
                        and value.get("next_check_at", 0) <= now):
                    eligible.append(value)
            if eligible:
                # 按到期时间公平领取，避免前几份待审核资料反复检查而饿死后续文件。
                value = min(eligible, key=lambda row: (row.get("next_check_at", 0), row["created_at"], row["job_id"]))
                value.update(status="building", next_check_at=now + 3600)
                self.save(value)
                return value
        return None

    def update(self, job, **changes):
        with self.locked():
            current = self.read(job["job_id"])
            if current["status"] == "superseded":
                return current
            current.update(changes, updated_at=datetime.now(timezone.utc).isoformat())
            self.save(current)
            return current

    def tick(self):
        job = self.claim()
        if job is None:
            return
        try:
            identity = self.identity(job["operator_id"])
            if identity is None or not identity.is_admin:
                self.update(job, status="awaiting_admin", next_check_at=time.time() + 5)
                return
            source = self.source(job)
            ledger = self.app.state.review_ledger
            if ledger is None:
                raise MinerUError("review_ledger_not_configured", 503)
            state = ledger.state(job["owner_id"], source["parse_id"])
            if state["status"] != "approved":
                self.update(job, status="awaiting_review", next_check_at=time.time() + 3)
                return
            if not job.get('source_range') and not job.get('whole_file_confirmed'):
                from .reviewed_export import export_reviewed_result
                reviewed=export_reviewed_result(source,state,ledger,job['owner_id'])
                if len(suggest_segments(reviewed.raw_text))>1:
                    raise MinerUError('source_scope_confirmation_required',409)
            business_id=digest(["workbench-business-v1", job["owner_id"], job["source_sha256"], job["document_type"], job.get("source_range")])
            body = IngestionBatchRequest(kb_version=job["kb_version"], documents=[{
                "parse_id": source["parse_id"], "law_name": job["title"],
                "law_id": business_id,
                "document_type": job["document_type"], "source_range":job.get("source_range"), "expected_review_version": state["version"]}])
            # 所有审批/来源/质量/模型/幂等门禁继续由既有入库服务检查。
            result = self.app.state.knowledge_hooks["build"](
                body=body, idempotency_key=job["job_id"], identity=identity)
            if result.get("status") != "STAGED" or result.get("outcome_unconfirmed"):
                raise MinerUError("ingestion_outcome_unconfirmed", 409)
            database=self.reader.kb_factory()
            try:
                with database.transaction(read_only=True):
                    rows=database.all('SELECT v.doc_version_id,v.metadata FROM mr_document_versions v JOIN mr_kb_documents k ON k.doc_version_id=v.doc_version_id WHERE k.kb_version=:v',{'v':job['kb_version']})
                import json
                matches=[]
                for row in rows:
                    metadata=json.loads(row['metadata']) if isinstance(row['metadata'],str) else row['metadata']
                    if metadata.get('law_id')==business_id and metadata.get('api_review_reference',{}).get('version')==state['version']:
                        matches.append(row['doc_version_id'])
                if len(matches)!=1:
                    raise MinerUError('knowledge_candidate_identity_mismatch',409)
            finally: database.close()
            self.update(job, status="awaiting_publish", error_code=None,
                        source_parse_id=source["parse_id"], review_version=state["version"],
                        doc_version_id=matches[0],business_id=business_id)
        except MinerUError as error:
            if error.code in {"parse_result_not_ready", "latest_parse_unfinished"}:
                self.update(job, status="awaiting_parse", next_check_at=time.time() + 3)
            elif error.code in {"model_busy", "queue_full"}:
                self.update(job, status="queued", next_check_at=time.time() + 3)
            else:
                self.update(job, status="needs_attention", error_code=error.code)
        except Exception:
            self.update(job, status="needs_attention", error_code="knowledge_service_unavailable")

    def delegate_approved(self, owner, file_id, identity):
        if not identity.is_admin:
            return
        with self.locked():
            for path in self.root.glob("*.json"):
                value = self.read(path.stem)
                if value["owner_id"] == owner and value["file_id"] == file_id and value["status"] in {
                    "queued", "awaiting_review", "awaiting_admin", "awaiting_parse"}:
                    value.update(operator_id=identity.principal_id, next_check_at=0)
                    self.save(value)


def register_workbench_ingestion(app, principal, reader, config):
    jobs = KnowledgeJobs(app, reader, config.result_dir)
    app.state.workbench_ingestion = jobs
    router = APIRouter(tags=["file-workbench"])

    @router.get("/api/workbench/documents/{file_id}/suggestions",response_model=SourceSuggestions)
    @guarded
    def suggestions(file_id: str,start:int=Query(0,ge=0),length:int=Query(20000,ge=1000,le=50000),identity=Depends(principal)):
        upload,source_path=readable_upload(reader,identity,file_id)
        from .upload_ownership import upload_owner
        owner=upload_owner(reader,identity,upload,source_path)
        source=jobs.source({'owner_id':owner,'file_id':file_id,'source_sha256':upload['sha256']})
        ledger=app.state.review_ledger
        state=ledger.state(owner,source['parse_id']) if ledger is not None else {'current_revision':None}
        from .reviewed_export import export_reviewed_result
        result=export_reviewed_result(source,state,ledger,owner)
        text=result.raw_text
        first='\n'.join(text.splitlines()[:12])
        suggested_type='case' if '行政处罚决定书' in first else None
        if suggested_type is None:
            import re
            suggested_type='law' if re.search(r'(条例|办法|规定|细则|法)[》\s]*$',first,re.M) else None
        return {'file_id':file_id,'source_parse_id':source['parse_id'],'expected_sha256':upload['sha256'],
                'suggested_type':suggested_type,'requires_confirmation':True,
                'text_sha256':text_digest(text),'segments':suggest_segments(text),'source_text':text[start:start+length],
                'text_start':start,'total_characters':len(text),'page_offset':text.count('\f',0,start),
                'warning':'标题和边界仅为拆分建议，请对照原件核对；目录页、引文和重复标题可能产生误识别。'}

    @router.post("/api/workbench/documents/{file_id}/prepare", status_code=202,response_model=KnowledgeJobStatus)
    @guarded
    def prepare(file_id: str, body: PrepareFile, idempotency_key: str = Header(min_length=1, max_length=128),
                identity=Depends(principal)):
        return jobs.public(jobs.create(identity, file_id, body, idempotency_key))

    @router.get("/api/workbench/jobs",response_model=KnowledgeJobPage)
    @guarded
    def listing(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                file_id: str = Query('',max_length=32),identity=Depends(principal)):
        rows = []
        for path in jobs.root.glob("*.json"):
            value = jobs.read(path.stem)
            if value["owner_id"] in identity.read_owners and value["status"] != "superseded" and (not file_id or value["file_id"]==file_id):
                rows.append(jobs.public(value))
        rows.sort(key=lambda value: value["created_at"], reverse=True)
        return page_of(rows, page, page_size, "persisted_knowledge_jobs")

    @router.get("/api/workbench/jobs/{job_id}",response_model=KnowledgeJobStatus)
    @guarded
    def detail(job_id: str, identity=Depends(principal)):
        return jobs.public(jobs.accessible(job_id, identity))

    @router.get("/api/workbench/jobs/{job_id}/check",response_model=KnowledgeJobCheck)
    @guarded
    def check(job_id: str, identity=Depends(principal)):
        value = jobs.accessible(job_id, identity)
        result = app.state.knowledge_hooks["check"](kb_version=value["kb_version"], identity=identity)
        return {**result, "document": jobs.public(value)}

    @router.post("/api/workbench/jobs/{job_id}/publish",response_model=KnowledgeJobStatus)
    @guarded
    def publish(job_id: str, body: PublishJob, idempotency_key: str = Header(min_length=1, max_length=128),
                identity=Depends(principal)):
        if not identity.is_admin:
            raise MinerUError("knowledge_write_forbidden", 403)
        value = jobs.accessible(job_id, identity)
        if value["status"] not in {"awaiting_publish", "published"}:
            raise MinerUError("knowledge_candidate_not_ready", 409)
        if value["status"]!="published":jobs.source(value)
        result = app.state.knowledge_hooks["publish"](
            body=ReleaseRequest(kb_version=value["kb_version"], expected_active_version=body.expected_active_version),
            idempotency_key=idempotency_key, identity=identity)
        if result.get("status") != "COMPLETED" or result.get("outcome_unconfirmed"):
            raise MinerUError("ingestion_outcome_unconfirmed", 409)
        return jobs.public(jobs.update(value, status="published", published_version=value["kb_version"]))

    app.include_router(router)
