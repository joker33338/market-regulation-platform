"""将用户明确选择的候选合成发布清单；保留原ACTIVE资料，只发布一次。"""
import json
from typing import Literal
from .schemas import ListResponse

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from .common import guarded, page_of
from .ingestion import ReleaseRequest, VersionCheckResponse
from .private_operations import OperationStore, digest
from .workbench_ingestion import PublishJob
from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.utils import IngestionError


class ReleaseItems(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # 单次传输分页，不限制整个发布清单可追加的总数。
    job_ids: list[str] = Field(default_factory=list, max_length=100)
    all_ready: bool = False


class ReleaseDocument(BaseModel):
    job_id: str
    title: str
    document_type: Literal["law", "case"]
    file_id: str


class ReleaseManifest(BaseModel):
    release_id: str
    status: str
    kb_version: str
    documents: list[ReleaseDocument]
    expected_active_version: str | None = None
    document_count: int = 0
    category_counts: dict[str,int] = Field(default_factory=dict)


class ReleaseManifestCheck(VersionCheckResponse):
    manifest: ReleaseManifest


class ReleaseDocumentPage(ListResponse):
    list: list[ReleaseDocument]


def register_workbench_releases(app, principal, reader, config):
    store = OperationStore(config.result_dir)
    store.root = store.root.parent / ".file-knowledge-releases"
    jobs = app.state.workbench_ingestion
    router = APIRouter(tags=["file-workbench"])

    def admin(identity):
        if not identity.is_admin:
            raise MinerUError("knowledge_write_forbidden", 403)

    def read(release_id, identity):
        admin(identity)
        value = store.read(release_id)
        if not value or value["operator_id"] != identity.principal_id:
            raise MinerUError("release_not_found", 404)
        return value

    def snapshot(value, identity):
        rows = []
        for job_id in value["job_ids"]:
            job = jobs.accessible(job_id, identity)
            allowed = {"awaiting_publish", "published"} if value["status"] == "published" else {"awaiting_publish"}
            if job["status"] not in allowed:
                raise MinerUError("knowledge_candidate_not_ready", 409)
            if value["status"]!="published":jobs.source(job)
            rows.append(job)
        return rows

    def remember_documents(value, rows):
        value['documents']=[{key:row[key] for key in ('job_id','title','document_type','file_id')} for row in rows]

    def public(value, identity):
        from collections import Counter
        rows=value.get('documents',[])
        return {"release_id": value["operation_id"], "status": value["status"], "kb_version": value["kb_version"],
                "documents": rows[:20], "document_count":len(rows),
                "category_counts":dict(Counter(row['document_type'] for row in rows)),
                "expected_active_version": value.get("expected_active_version")}

    @router.post("/api/workbench/releases", status_code=201, response_model=ReleaseManifest)
    @guarded
    def create(body: ReleaseItems, idempotency_key: str = Header(min_length=1, max_length=128), identity=Depends(principal)):
        admin(identity)
        operation_id = store.identifier(identity.principal_id, "release-manifest", idempotency_key)
        fingerprint = digest(body.model_dump())
        with store.locked(), jobs.locked():
            value = store.replay(operation_id, fingerprint)
            if value is None:
                if body.all_ready and body.job_ids:
                    raise MinerUError("ambiguous_release_selection", 422)
                selected_ids = list(dict.fromkeys(body.job_ids))
                if body.all_ready:
                    for path in jobs.root.glob("*.json"):
                        job = jobs.read(path.stem)
                        if job["status"] == "awaiting_publish" and job["owner_id"] in identity.read_owners:
                            selected_ids.append(job["job_id"])
                value = {"operation_id": operation_id, "fingerprint": fingerprint, "operator_id": identity.principal_id,
                         "status": "DRAFT", "job_ids": selected_ids,
                         "kb_version": "release-" + operation_id[:24]}
                remember_documents(value, snapshot(value, identity))
                store.save(value)
            return public(value, identity)

    @router.post("/api/workbench/releases/{release_id}/items", response_model=ReleaseManifest)
    @guarded
    def append(release_id: str, body: ReleaseItems, identity=Depends(principal)):
        with store.locked():
            value = read(release_id, identity)
            if value["status"] != "DRAFT":
                raise MinerUError("release_manifest_frozen", 409)
            new_ids=[job_id for job_id in dict.fromkeys(body.job_ids) if job_id not in value['job_ids']]
            additions=snapshot({'status':'DRAFT','job_ids':new_ids},identity)
            value['job_ids'].extend(new_ids)
            value.setdefault('documents',[]).extend({key:row[key] for key in ('job_id','title','document_type','file_id')} for row in additions)
            store.save(value)
            return public(value, identity)

    @router.get("/api/workbench/releases/{release_id}/items",response_model=ReleaseDocumentPage)
    @guarded
    def manifest_items(release_id: str, page: int=Query(1,ge=1),page_size: int=Query(20,ge=1,le=100),identity=Depends(principal)):
        value=read(release_id,identity)
        return page_of(value.get('documents',[]),page,page_size,'fixed_release_manifest')

    def collect(database, selected):
        documents = []
        settings = None
        for offset in range(0, len(selected), 100):
            group = selected[offset:offset + 100]
            params = {f"v{index}": job["kb_version"] for index, job in enumerate(group)}
            slots = ",".join(f":v{index}" for index in range(len(group)))
            versions = database.all("SELECT kb_version,status,processing_signature,model_signature,dimension FROM mr_kb_versions WHERE kb_version IN (" + slots + ")", params)
            if len(versions) != len(group):
                raise MinerUError("knowledge_candidate_not_ready", 409)
            for version in versions:
                current = tuple(version[key] for key in ("processing_signature", "model_signature", "dimension"))
                if version["status"] not in {"STAGED", "ACTIVE", "ARCHIVED"} or settings is not None and current != settings:
                    raise MinerUError("knowledge_processing_mismatch", 409)
                settings = current
            # 只取每份候选对应的目标文档，避免把各自继承的ACTIVE资料重复合并。
            values = []
            wanted_params = {}
            for index, job in enumerate(group):
                values.append(f"(:v{index},:p{index})")
                wanted_params.update({f"v{index}": job["kb_version"], f"p{index}": job["source_parse_id"]})
            expression = "(v.metadata::jsonb->'api_review_reference'->>'parse_id')" if database.postgres else "json_extract(v.metadata,'$.api_review_reference.parse_id')"
            found = database.all("WITH wanted(kb_version,parse_id) AS (VALUES " + ",".join(values) + ") SELECT k.kb_version,k.doc_id,k.doc_version_id,k.source_path,v.metadata FROM wanted w JOIN mr_kb_documents k ON k.kb_version=w.kb_version JOIN mr_document_versions v ON v.doc_version_id=k.doc_version_id WHERE " + expression + "=w.parse_id", wanted_params)
            by_version = {}
            for row in found:
                by_version.setdefault(row["kb_version"], []).append(row)
            for job in group:
                matches = [row for row in by_version.get(job["kb_version"], [])
                           if row['doc_version_id']==job.get('doc_version_id')]
                if len(matches) != 1:
                    raise MinerUError("knowledge_candidate_identity_mismatch", 409)
                row = matches[0]
                metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
                reference = metadata.get("api_review_reference", {})
                if (reference.get("version") != job.get("review_version") or
                        reference.get("owner_id") != job["owner_id"] or
                        metadata.get("document_type", "law") != job["document_type"]):
                    raise MinerUError("knowledge_candidate_identity_mismatch", 409)
                documents.append({**row, "reference": reference})
        seen = {}
        for row in documents:
            if row["doc_id"] in seen:
                raise MinerUError("conflicting_document_versions", 409)
            seen[row["doc_id"]] = row["doc_version_id"]
        return documents, settings

    @router.post("/api/workbench/releases/{release_id}/prepare", response_model=ReleaseManifest)
    @guarded
    def prepare(release_id: str, identity=Depends(principal)):
        with store.locked(), jobs.locked():
            value = read(release_id, identity)
            if value["status"] == "STAGED":
                return public(value, identity)
            if value["status"] != "DRAFT" or not value["job_ids"]:
                raise MinerUError("release_manifest_not_ready", 409)
            selected = snapshot(value, identity)
            database = reader.kb_write_factory()
            created = False
            try:
                with database.transaction(read_only=True):
                    documents, settings = collect(database, selected)
                ledger = app.state.review_ledger
                if ledger is None:
                    raise MinerUError("review_ledger_not_configured", 503)
                with ledger.verified_ingestion_scope([row["reference"] for row in documents]):
                    value["status"] = "PREPARING"
                    store.save(value)
                    database.create_version(value["kb_version"], *settings)
                    created = True
                    with database.transaction():
                        for row in documents:
                            database.attach_revision(value["kb_version"], row["doc_id"], row["doc_version_id"], row["source_path"])
                    database.finish_version(value["kb_version"], {"documents_seen": len(documents), "documents_reused": len(documents),
                                                                  "chunks_embedded": 0, "full_snapshot": False})
                value.update(status="STAGED", expected_active_version=database.version(value["kb_version"])["base_version"])
                store.save(value)
                return public(value, identity)
            except Exception as error:
                if created:
                    database.fail_version(value["kb_version"])
                value["status"] = "FAILED"
                store.save(value)
                if isinstance(error, MinerUError):
                    raise
                raise MinerUError("release_prepare_conflict" if isinstance(error, IngestionError) else "release_prepare_unavailable",
                                  409 if isinstance(error, IngestionError) else 503) from None
            finally:
                database.close()

    @router.get("/api/workbench/releases/{release_id}/check",response_model=ReleaseManifestCheck)
    @guarded
    def check(release_id: str, identity=Depends(principal)):
        value = read(release_id, identity)
        snapshot(value, identity)
        return {**app.state.knowledge_hooks["check"](kb_version=value["kb_version"], identity=identity),
                "manifest": public(value, identity)}

    @router.post("/api/workbench/releases/{release_id}/publish", response_model=ReleaseManifest)
    @guarded
    def publish(release_id: str, body: PublishJob, idempotency_key: str = Header(min_length=1, max_length=128),
                identity=Depends(principal)):
        with store.locked(), jobs.locked():
            value = read(release_id, identity)
            if value["status"] not in {"STAGED", "published"}:
                raise MinerUError("release_manifest_not_ready", 409)
            selected = snapshot(value, identity)
            receipt = app.state.knowledge_hooks["publish"](
                body=ReleaseRequest(kb_version=value["kb_version"], expected_active_version=body.expected_active_version),
                idempotency_key=idempotency_key, identity=identity)
            if receipt.get("status") != "COMPLETED" or receipt.get("outcome_unconfirmed"):
                raise MinerUError("ingestion_outcome_unconfirmed", 409)
            value["status"] = "published"
            store.save(value)
            for job in selected:
                job["status"] = "published"
                job["published_version"] = value["kb_version"]
                jobs.save(job)
            return public(value, identity)

    app.include_router(router)
