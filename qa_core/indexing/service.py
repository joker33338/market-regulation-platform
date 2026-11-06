"""Offline orchestration, following KnowForge's service/loader/chunker separation."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict

from qa_core.config.settings import CLEANER_VERSION, SCHEMA_VERSION, Settings
from qa_core.indexing.chunking import split_articles
from qa_core.indexing.legal_cleaner import clean_lines
from qa_core.indexing.legal_structure import parse_articles
from qa_core.indexing.models import LegalDocument
from qa_core.quality.ingestion import validate_chunks
from qa_core.retrieval.models import DemoEmbeddings, validate_vectors
from qa_core.storage.database import Database
from qa_core.utils import IngestionError, stable_hash


def prepare_document(document: LegalDocument, *, model_signature: str, max_chars: int,
                     namespace: str = "market_regulation"):
    if not document.law_name or not document.law_name.strip():
        raise IngestionError("法规名称为空。")
    lines, cleaner = clean_lines(document.lines)
    articles = document.articles if document.articles is not None else parse_articles(lines)
    doc_id = stable_hash(namespace, document.law_id or document.law_name)
    processing = stable_hash(SCHEMA_VERSION, CLEANER_VERSION, model_signature, max_chars)
    revision = stable_hash(doc_id, document.law_name, document.source_hash, processing)
    chunks = split_articles(articles, law_name=document.law_name, doc_version_id=revision,
                            model_signature=model_signature, max_chars=max_chars)
    quality = validate_chunks(chunks, max_chars)
    return doc_id, revision, chunks, {
        **document.metadata, "cleaning": cleaner, "quality": quality, "source_path": document.source_path,
        "law_id": document.law_id, "schema_version": SCHEMA_VERSION, "processing_signature": processing,
    }


def preview_documents(documents: Iterable[LegalDocument], *, max_chars: int = 800,
                      namespace: str = "market_regulation") -> dict:
    entries = []
    for document in documents:
        doc_id, revision, chunks, metadata = prepare_document(
            document, model_signature="PREVIEW-NO-EMBEDDING", max_chars=max_chars, namespace=namespace)
        entries.append({"doc_id": doc_id, "revision": revision, "law_name": document.law_name,
                        "source_path": document.source_path, "metadata": metadata,
                        "chunks": [asdict(chunk) for chunk in chunks]})
    if not entries:
        raise IngestionError("没有读取到可处理的法规。")
    return {"mode": "preview", "documents": entries, "document_count": len(entries),
            "chunk_count": sum(len(entry["chunks"]) for entry in entries)}


def ingest_documents(documents: Iterable[LegalDocument], *, database: Database, embeddings,
                     settings: Settings, version: str, namespace: str = "market_regulation",
                     full_snapshot: bool = False) -> dict:
    if namespace != "market_regulation":
        raise IngestionError("MVP 每个数据库只支持一个 market_regulation 发布域。")
    if database.postgres and (embeddings.dimension != 1024 or isinstance(embeddings, DemoEmbeddings)):
        raise IngestionError("PostgreSQL 入库要求真实 1024 维模型；demo 向量仅允许用于 SQLite 演示。")
    signature = stable_hash(SCHEMA_VERSION, CLEANER_VERSION, embeddings.signature, settings.max_chunk_chars)
    database.create_version(version, signature, embeddings.signature, embeddings.dimension, full_snapshot=full_snapshot)
    stats = {"documents_seen": 0, "documents_reused": 0, "chunks_embedded": 0, "vectors_reused": 0,
             "duplicate_inputs": 0, "full_snapshot": full_snapshot}
    seen = {}
    try:
        for document in documents:
            doc_id, revision, chunks, metadata = prepare_document(
                document, model_signature=embeddings.signature, max_chars=settings.max_chunk_chars,
                namespace=namespace)
            if doc_id in seen:
                if seen[doc_id] != revision:
                    raise IngestionError("同一输入批次包含同一法规身份的不同正文，请明确版本后分批构建。")
                stats["duplicate_inputs"] += 1
                continue
            seen[doc_id] = revision
            stats["documents_seen"] += 1
            if database.revision_exists(revision):
                with database.transaction():
                    database.attach_revision(version, doc_id, revision, document.source_path)
                stats["documents_reused"] += 1
                continue
            pending = []
            for chunk in chunks:
                cached = database.cached_vector(chunk.input_hash)
                if cached is not None:
                    chunk.embedding = validate_vectors([cached], 1, embeddings.dimension)[0]
                    stats["vectors_reused"] += 1
                else:
                    pending.append(chunk)
            for start in range(0, len(pending), settings.batch_size):
                batch = pending[start:start + settings.batch_size]
                values = validate_vectors(embeddings.embed_documents([chunk.embedding_text for chunk in batch]),
                                          len(batch), embeddings.dimension)
                for chunk, vector in zip(batch, values, strict=True):
                    chunk.embedding = vector
                stats["chunks_embedded"] += len(batch)
            database.save_revision(version=version, doc_id=doc_id, doc_version_id=revision,
                                   source_hash=document.source_hash, law_name=document.law_name,
                                   source_path=document.source_path, metadata=metadata, chunks=chunks)
        if not seen:
            raise IngestionError("没有输入法规，禁止生成空候选版本。")
        database.finish_version(version, stats)
        return {"version": version, "status": "STAGED", **stats}
    except BaseException:
        database.fail_version(version)
        raise

