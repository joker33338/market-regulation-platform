"""Hybrid retrieval against the compatible law_chunks current projection."""
from __future__ import annotations

import json
import math
import re

from qa_core.storage.database import Database
from qa_core.utils import IngestionError, json_text

SELECT_FIELDS = """l.law_name,l.chapter,l.article_no,l.seq,l.content,
    c.metadata,c.chunk_id,c.doc_version_id,d.source_path,m.kb_version"""
JOINS = """FROM law_chunks l JOIN mr_active_chunk_map m
    ON l.law_name=m.law_name AND l.article_no=m.article_no AND l.seq=m.seq
    JOIN mr_chunks c ON c.chunk_id=m.chunk_id
    JOIN mr_kb_documents d ON d.kb_version=m.kb_version AND d.doc_version_id=c.doc_version_id"""


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise IngestionError("查询向量和库内向量维度不匹配。")
    denominator = math.sqrt(sum(v * v for v in left) * sum(v * v for v in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def vector_search(database: Database, vector: list[float], top_k: int) -> list[dict]:
    if database.postgres:
        return database.all("SELECT " + SELECT_FIELDS + ",1-(l.embedding <=> CAST(:q AS vector)) AS score " +
                            JOINS + " ORDER BY l.embedding <=> CAST(:q AS vector) LIMIT :k",
                            {"q": json_text(vector), "k": top_k})
    rows = database.all("SELECT " + SELECT_FIELDS + ",l.embedding " + JOINS)
    for row in rows:
        row["score"] = cosine(vector, json.loads(row.pop("embedding")))
    return sorted(rows, key=lambda row: (-row["score"], row["chunk_id"]))[:top_k]


def keyword_search(database: Database, question: str, top_k: int) -> list[dict]:
    # No zhparser dependency; parameterized matching preserves the legacy fallback.
    escape = lambda value: value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return database.all("SELECT " + SELECT_FIELDS + ",1.0 AS score " + JOINS +
                        r" WHERE l.content LIKE :q ESCAPE '\' OR l.article_no LIKE :q ESCAPE '\'"
                        " ORDER BY l.law_name,l.article_no,l.seq LIMIT :k",
                        {"q": "%" + escape(question) + "%", "k": top_k})


def rrf_merge(vector: list[dict], keyword: list[dict], top_k: int = 8) -> list[dict]:
    fused = {}
    for hits in [vector, keyword]:
        for rank, hit in enumerate(hits, 1):
            entry = fused.setdefault(hit["chunk_id"], {"row": hit, "rrf": 0.0})
            entry["rrf"] += 1 / (60 + rank)
    return [{**entry["row"], "rrf_score": entry["rrf"]}
            for entry in sorted(fused.values(), key=lambda value: -value["rrf"])[:top_k]]


def retrieve(database: Database, embeddings, question: str, top_k: int = 8) -> list[dict]:
    if not question.strip():
        raise IngestionError("问题不能为空。")
    vector = embeddings.embed_documents([question])[0]
    with database.transaction(read_only=True):
        active = database.active_version()
        if active is None:
            raise IngestionError("没有 ACTIVE 版本；请先构建并显式 publish。")
        record = database.version(active)
        if record["model_signature"] != embeddings.signature:
            raise IngestionError("查询模型与当前 ACTIVE 向量空间不一致。")
        hits = rrf_merge(vector_search(database, vector, top_k), keyword_search(database, question, top_k), top_k)
    for hit in hits:
        hit["metadata"] = json.loads(hit["metadata"])
    return hits

