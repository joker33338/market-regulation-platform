"""Hybrid retrieval against the compatible law_chunks current projection."""
from __future__ import annotations

import json
import math
import re

from qa_core.storage.database import Database
from qa_core.utils import IngestionError, json_text

SELECT_FIELDS = """l.law_name,l.chapter,l.article_no,l.seq,l.content,
    c.metadata,c.chunk_id,c.doc_version_id,d.source_path,m.kb_version,v.metadata AS document_metadata"""
JOINS = """FROM law_chunks l JOIN mr_active_chunk_map m
    ON l.law_name=m.law_name AND l.article_no=m.article_no AND l.seq=m.seq
    JOIN mr_chunks c ON c.chunk_id=m.chunk_id
    JOIN mr_kb_documents d ON d.kb_version=m.kb_version AND d.doc_version_id=c.doc_version_id
    JOIN mr_document_versions v ON v.doc_version_id=c.doc_version_id"""


def selection(database, kb_version=None, issuing_authority=None, effective_status=None):
    """仅按实际保存的来源字段筛选，不推断机关或法律效力。"""
    joins=JOINS
    clauses=[];params={}
    if kb_version is not None:
        record=database.version(kb_version)
        if record['status'] not in {'ACTIVE','ARCHIVED'} or database.one(
                'SELECT event_id FROM mr_release_history WHERE to_version=:v LIMIT 1',{'v':kb_version}) is None:
            raise IngestionError('只允许检索已发布的当前或历史版本。')
        joins='''FROM mr_chunks l JOIN mr_kb_documents m ON m.doc_version_id=l.doc_version_id
            JOIN mr_chunks c ON c.chunk_id=l.chunk_id
            JOIN mr_kb_documents d ON d.kb_version=m.kb_version AND d.doc_id=m.doc_id
            JOIN mr_document_versions v ON v.doc_version_id=c.doc_version_id'''
        clauses.append('m.kb_version=:selected_version');params['selected_version']=kb_version
    for key,value in (('issuing_authority',issuing_authority),('effective_status',effective_status)):
        if value is not None:
            expression=(f"COALESCE(CAST(c.metadata AS jsonb)->>'{key}',CAST(v.metadata AS jsonb)->>'{key}')" if database.postgres
                        else f"COALESCE(json_extract(c.metadata,'$.{key}'),json_extract(v.metadata,'$.{key}'))")
            clauses.append(expression+'=:'+key);params[key]=value
    return joins,clauses,params


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise IngestionError("查询向量和库内向量维度不匹配。")
    denominator = math.sqrt(sum(v * v for v in left) * sum(v * v for v in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def vector_search(database: Database, vector: list[float], top_k: int, **filters) -> list[dict]:
    joins,clauses,params=selection(database,**filters)
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    if database.postgres:
        return database.all("SELECT " + SELECT_FIELDS + ",1-(l.embedding <=> CAST(:q AS vector)) AS score " +
                            joins + where + " ORDER BY l.embedding <=> CAST(:q AS vector) LIMIT :k",
                            {**params,"q": json_text(vector), "k": top_k})
    rows = database.all("SELECT " + SELECT_FIELDS + ",l.embedding " + joins+where,params)
    for row in rows:
        row["score"] = cosine(vector, json.loads(row.pop("embedding")))
    return sorted(rows, key=lambda row: (-row["score"], row["chunk_id"]))[:top_k]


def keyword_search(database: Database, question: str, top_k: int, **filters) -> list[dict]:
    # 不依赖 zhparser，参数化匹配保留原有关键词回退能力。
    escape = lambda value: value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    joins,clauses,params=selection(database,**filters)
    clauses.append(r"(l.content LIKE :q ESCAPE '\' OR l.article_no LIKE :q ESCAPE '\')")
    return database.all("SELECT " + SELECT_FIELDS + ",1.0 AS score " + joins+' WHERE '+' AND '.join(clauses)+
                        " ORDER BY l.law_name,l.article_no,l.seq LIMIT :k",
                        {**params,"q": "%" + escape(question) + "%", "k": top_k})


def rrf_merge(vector: list[dict], keyword: list[dict], top_k: int = 8) -> list[dict]:
    fused = {}
    for hits in [vector, keyword]:
        for rank, hit in enumerate(hits, 1):
            entry = fused.setdefault(hit["chunk_id"], {"row": hit, "rrf": 0.0})
            entry["rrf"] += 1 / (60 + rank)
    return [{**entry["row"], "rrf_score": entry["rrf"]}
            for entry in sorted(fused.values(), key=lambda value: -value["rrf"])[:top_k]]


def retrieve(database: Database, embeddings, question: str, top_k: int = 8, **filters) -> list[dict]:
    if not question.strip():
        raise IngestionError("问题不能为空。")
    vector = embeddings.embed_documents([question])[0]
    with database.transaction(read_only=True):
        active = filters.get('kb_version') or database.active_version()
        if active is None:
            raise IngestionError("没有 ACTIVE 版本；请先构建并显式 publish。")
        record = database.version(active)
        if record["model_signature"] != embeddings.signature:
            raise IngestionError("查询模型与当前 ACTIVE 向量空间不一致。")
        hits = rrf_merge(vector_search(database, vector, top_k,**filters), keyword_search(database, question, top_k,**filters), top_k)
    for hit in hits:
        hit["metadata"] = json.loads(hit["metadata"])
    return hits

