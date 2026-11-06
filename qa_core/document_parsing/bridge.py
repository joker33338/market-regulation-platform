"""Explicit output adapter. It does not generate vectors or touch a database."""
from __future__ import annotations

from datetime import datetime, timezone

from qa_core.indexing.models import LegalDocument, SourceLine
from qa_core.utils import IngestionError, stable_hash
from .schemas import DocumentResult, json_safe


def to_legal_document(result: DocumentResult, *, reviewer: str, law_name: str, law_id: str | None = None) -> LegalDocument:
    if result.parsing_status not in {"success", "needs_review"} or not result.pages:
        raise IngestionError("失败或部分失败的解析结果不能交给正式入库。")
    if not reviewer.strip() or not law_name.strip():
        raise IngestionError("需要明确复核人及法规名称；OCR 质量检查不能替代审核。")
    if any(page.tables or any(block.kind == "table" for block in page.layout_blocks) for page in result.pages):
        raise IngestionError("当前法律切分器不消费表格；请保留 tables，另用表格入库适配器，禁止摊平成法条。")
    lines = []
    evidence = []
    for page in result.pages:
        line_number = 0
        for block in page.layout_blocks:
            if block.kind in {"table", "image", "header", "footer", "number", "footnote"}:
                continue
            for index, text in enumerate(block.raw_text.splitlines()):
                line_number += 1
                lines.append(SourceLine(text, page.page_number, line_number, index == 0, block.bbox))
            evidence.append({"page": page.page_number, "block": block.block_id,
                             "location": block.source_location, "raw_text": block.raw_text})
    fingerprint = stable_hash(result.document_id, result.schema_version, evidence)
    return LegalDocument(law_name.strip(), fingerprint, result.source_location.get("file_path", result.file_name),
                         lines, law_id, metadata={
                             "format": result.file_type, "file_sha256": result.document_id,
                             "parsing_schema": result.schema_version, "source_evidence": evidence,
                             "review": {"reviewer": reviewer.strip(), "reviewed_at": datetime.now(timezone.utc).isoformat(),
                                        "reviewed_output_hash": fingerprint},
                             "paragraph_basis": "parser_blocks_requires_legal_review",
                         })

