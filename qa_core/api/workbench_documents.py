"""文件工作台只读聚合：上传、解析、审核和发布分别取真实来源。"""
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, Query

from .common import guarded, page_of
from .workbench_schemas import WorkbenchPage, WorkbenchReviewQueue
from .document_query import select_documents, validate_window
from .principals import owner_selector
from qa_core.storage.mysql_review_ledger import digest as owner_digest


def combine_documents(uploads, parses, reviews, versions):
    rows = []
    for upload in uploads:
        parsed = parses.get(upload["file_id"], {})
        parse_id = parsed.get("parse_id")
        review = (reviews or {}).get(parse_id, {})
        raw_status = upload["status"]
        blocked_reason = None
        if raw_status in {"created", "pending", "running", "uploading"}:
            stage = "processing"
        elif raw_status in {"failed", "partial", "timed_out", "canceled"}:
            stage = "needs_attention"
        elif parse_id:
            if versions.get(parse_id) == "ACTIVE":
                stage = "published"
            elif reviews is None:
                stage = "state_unavailable"
            elif review.get("status") in {"rejected", "error", "marked_error", "flagged"}:
                stage = "needs_attention"
            elif review.get("status") == "approved":
                # 修订是否可导出由候选构建逐版本核验，不把所有整页修订误判成历史不明修订。
                stage = "awaiting_publish" if versions.get(parse_id) == "STAGED" else "ready_to_build"
            else:
                stage = "awaiting_review"
        elif raw_status == "uploaded":
            stage = "uploaded"
        else:
            stage = "state_unavailable"
        rows.append({**upload, "parse_id": parse_id, "stage": stage,
                     "title": parsed.get("title") or upload["file_name"],
                     "category": parsed.get("kind") or "unconfirmed",
                     "number": parsed.get("number"), "review_version": review.get("version",0) if reviews is not None and parse_id else None,
                     "parsing_status":parsed.get("parsing_status"),"imported_at":parsed.get("imported_at"),"body_match":bool(parsed.get("body_match")),"blocked_reason": blocked_reason, "published_doc_version_ids":parsed.get("published_doc_version_ids",[])})
    return rows


def inventory(reader, identity, ledger, keyword=""):
    from qa_core.access import is_all_owners
    scopes = identity.read_owners
    uploads = (reader.documents(scopes) if is_all_owners(scopes) else
               [row for owner in scopes for row in reader.documents(owner)])
    if not uploads:
        return [], {"postgres": True, "review_ledger": ledger is not None}
    parses, versions = {}, {}
    pg_available = False
    if reader.review is not None:
        where, args = reader.review.scope(owner_selector(identity))
        with reader.review.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT ON (source_location->>'source_file_id')
                    parse_id,parsing_status,requires_review,imported_at,
                    strpos(lower(raw_text),lower(NULLIF(%s,'')))>0 AS body_match,
                    source_location->>'source_file_id' AS file_id,
                    source_location->>'owner_id' AS owner_id
                FROM document_review.documents
                WHERE source_location->>'source_file_id'=ANY(%s) AND """ + where + """
                ORDER BY source_location->>'source_file_id',imported_at DESC,parse_id DESC
                """, [keyword, [item["file_id"] for item in uploads], *args])
            parses = {item["file_id"]: dict(item) for item in cursor.fetchall()}
            if parses:
                cursor.execute("""
                    SELECT r.parse_id,r.doc_version_id,r.kind,r.title,r.number,v.status,
                        EXISTS(SELECT 1 FROM public.mr_active a
                            JOIN public.mr_kb_documents k ON k.kb_version=a.kb_version
                            WHERE k.doc_version_id=r.doc_version_id
                            AND EXISTS(SELECT 1 FROM public.mr_release_history h
                                WHERE h.to_version=a.kb_version AND h.action IN ('publish','rollback'))) AS published
                    FROM business_library.records r
                    LEFT JOIN public.mr_kb_documents k USING(doc_version_id)
                    LEFT JOIN public.mr_kb_versions v USING(kb_version)
                    WHERE r.parse_id=ANY(%s)
                    """, [[item["parse_id"] for item in parses.values()]])
                by_parse = {item["parse_id"]: item for item in parses.values()}
                for record in cursor.fetchall():
                    by_parse[record["parse_id"]].update({key: record[key] for key in ("kind", "title", "number")})
                    current = versions.get(record["parse_id"])
                    if record["published"]:
                        by_parse[record["parse_id"]].setdefault('published_doc_version_ids',[]).append(record['doc_version_id'])
                        versions[record["parse_id"]] = "ACTIVE"
                    elif current != "ACTIVE" and record["status"] == "STAGED":
                        versions[record["parse_id"]] = "STAGED"
        pg_available = True
    reviews = None
    if ledger is not None and parses:
        try:
            reviews = {}
            references = list(parses.values())
            with ledger.connection() as connection, connection.cursor() as cursor:
                for offset in range(0, len(references), 100):
                    group = references[offset:offset + 100]
                    predicates = " OR ".join("(owner_key=%s AND parse_id=%s)" for _ in group)
                    args = [value for item in group for value in (owner_digest(item["owner_id"]), item["parse_id"])]
                    cursor.execute("SELECT parse_id,status,version,current_revision FROM review_heads WHERE " + predicates, args)
                    reviews.update({item["parse_id"]: dict(item) for item in cursor.fetchall()})
        except Exception:
            reviews = None
    return combine_documents(uploads, parses, reviews, versions), {
        "postgres": pg_available, "review_ledger": reviews is not None}


def add_batch_metadata(rows, identity, root):
    from .workbench_batches import BatchStore
    by_file={row['file_id']: row for row in rows}
    batches=[]
    store=BatchStore(root)
    for path in store.root.glob('*.json'):
        batch=store.read(path.stem)
        count=0
        for item in batch['files']:
            row=by_file.get(item['file_id'])
            if row is None or (item.get('owner_id') or batch['owner_id']) not in identity.read_owners:
                continue
            count+=1
            row.setdefault('batch_ids',[]).append(batch['operation_id'])
            row['relative_path']=item.get('relative_path','')
            if row['stage']=='uploaded' and item['status'] in {'queued','dispatching','submitted'}:
                row['stage']='processing'
        if count:
            batches.append({'batch_id':batch['operation_id'],'name':batch['name'],'count':count})
    return batches


def add_job_metadata(rows, identity, root):
    from .private_operations import OperationStore
    store=OperationStore(root)
    store.root=store.root.parent/'.file-knowledge-jobs'
    by_file={row['file_id']:row for row in rows}
    latest={}
    for path in store.root.glob('*.json'):
        value=store.read(path.stem)
        if value['status']=='superseded' or value['owner_id'] not in identity.read_owners:
            continue
        scope=value.get('source_range') or {}
        key=(value['file_id'],value['document_type'],scope.get('start'),scope.get('end'))
        previous=latest.get(key)
        if previous is None or previous['created_at']<value['created_at']:
            latest[key]=value
    groups={}
    for value in latest.values():
        groups.setdefault(value['file_id'],[]).append(value)
    for fid,row in by_file.items():
        if fid not in groups and row['stage']=='ready_to_build':
            row['stage']='awaiting_classification'
    for fid,entries in groups.items():
        row=by_file.get(fid)
        if row is None:
            continue
        entries=[value for value in entries if row['sha256']==value['source_sha256']]
        if not entries:
            continue
        row['child_title_search']=' '.join(value['title'] for value in entries)
        kinds={value['document_type'] for value in entries}
        published=set(row.get('published_doc_version_ids',[]))
        row.update(child_document_count=len(entries),
                   published_document_count=sum(value.get('doc_version_id') in published for value in entries),
                   category=next(iter(kinds)) if len(kinds)==1 else 'unconfirmed')
        if len(entries)==1:
            value=entries[0]
            row.update(title=value['title'],knowledge_job_id=value['job_id'],knowledge_job_status=value['status'])
        else:
            row['title']=row['file_name']
        if row['published_document_count']==len(entries):
            row['stage']='published'
        elif any(value['status']=='needs_attention' for value in entries):
            row.update(stage='needs_attention',blocked_reason=next(value.get('error_code') for value in entries if value['status']=='needs_attention'))
        elif any(value['status']=='awaiting_publish' and row.get('parse_id')==value.get('source_parse_id')
                 and row.get('review_version')==value.get('review_version') for value in entries):
            row.update(stage='awaiting_publish',blocked_reason=None)
        elif any(value['status'] in {'queued','building','awaiting_parse'} for value in entries):
            row['stage']='processing'
        elif row['stage']=='published':
            row['stage']='ready_to_build' if row.get('review_version') else 'awaiting_review'


def register_workbench_documents(app, principal, reader):
    from datetime import datetime
    router = APIRouter(tags=["file-workbench"])

    @router.get("/api/workbench/review-queue",response_model=WorkbenchReviewQueue)
    @guarded
    def review_queue(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),identity=Depends(principal)):
        rows,availability=inventory(reader,identity,app.state.review_ledger)
        if any(row.get('parse_id') for row in rows) and not availability['review_ledger']:
            from qa_core.document_parsing.mineru_client import MinerUError
            raise MinerUError('review_ledger_unavailable',503)
        pending=[row for row in rows if row.get('parse_id') and row['stage'] in {'awaiting_review','needs_attention'}]
        pending.sort(key=lambda row:row['stage']!='needs_attention')
        return page_of([{'parse_id':row['parse_id'],'document_id':row['sha256'],'file_name':row['file_name'],
                         'file_type':row['doc_type'],'parsing_status':row.get('parsing_status') or row['status'],
                         'requires_review':True,'imported_at':row.get('imported_at') or row['uploaded_at'],
                         'source_location':{'owner_id':row.get('owner_id'),'source_file_id':row['file_id']},
                         'quality':{}} for row in pending],page,page_size,'workbench_pending_review')

    @router.get("/api/workbench/documents",response_model=WorkbenchPage)
    @guarded
    def listing(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                keyword: str = Query("", max_length=200),
                stage: str = Query("", max_length=40),
                category: Literal["", "law", "case", "unconfirmed"] = "",
                doc_type: Literal["", "pdf", "docx", "image"] = "",
                date_from: datetime | None = None, date_to: datetime | None = None,
                batch_id: str = Query("", max_length=64),
                identity=Depends(principal)):
        validate_window(date_from, date_to)
        rows, availability = inventory(reader, identity, app.state.review_ledger, keyword)
        batches = add_batch_metadata(rows, identity, reader.config.result_dir)
        add_job_metadata(rows, identity, reader.config.result_dir)
        term = keyword.strip().casefold()
        rows = [row for row in rows
                if (not term or any(term in str(row.get(field) or "").casefold()
                                    for field in ("file_name", "title", "number","child_title_search")) or row.get("body_match"))
                and (not category or row["category"] == category)
                and (not doc_type or row["doc_type"] == doc_type)
                and (not batch_id or batch_id in row.get("batch_ids", []))]
        rows = select_documents(rows, date_from, date_to, "uploaded_at", "desc")
        summary = dict(Counter(row["stage"] for row in rows))
        rows = [row for row in rows if not stage or row["stage"] == stage]
        return {**page_of(rows, page, page_size, "uploads+parsing+review_ledger+knowledge_versions"),
                "summary": summary, "availability": availability, "batches": batches}

    app.include_router(router)
