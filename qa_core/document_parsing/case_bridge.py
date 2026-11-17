"""已审核案例适配；复用案例预览切分，保留来源和原始解析。"""
from datetime import datetime, timezone

from qa_core.indexing.models import LegalDocument, Chunk, LegalUnit
from qa_core.indexing.chunking import pack_units
from qa_core.indexing.preview import preview_chunks, CASE_VERSION
from qa_core.quality.ingestion import validate_chunks
from qa_core.utils import IngestionError, stable_hash
from .bridge import source_lines


def to_case_document(result, *, reviewer, title, business_id):
    if not reviewer.strip() or not title.strip():
        raise IngestionError("需要明确审核人员和案例标题。")
    if any(page.tables or any(block.kind == "table" for block in page.layout_blocks) for page in result.pages):
        raise IngestionError("案例包含表格，必须完成表格内容的独立承接，禁止遗漏后发布。")
    preview = preview_chunks(result, "case")
    quality = preview["quality"]
    if any(quality.get(key) for key in (
        "pages_without_body_chunks", "pages_with_text_layout_mismatch", "pages_with_unstructured_tables"
    )):
        raise IngestionError("案例正文与版面存在未解决的完整性问题。")
    lines, evidence = source_lines(result)
    source_hash = stable_hash(result.document_id, result.schema_version, evidence)
    return LegalDocument(title.strip(), source_hash,
        result.source_location.get("file_path", result.file_name), lines, business_id, metadata={
            "document_type": "case", "file_sha256": result.document_id,
            "parsing_schema": result.schema_version, "source_evidence": evidence,
            "case_source_chunks": preview["chunks"],
            "review": {"reviewer": reviewer.strip(), "reviewed_at": datetime.now(timezone.utc).isoformat(),
                       "reviewed_output_hash": source_hash},
        })


def prepare_case_document(document, *, model_signature, max_chars, namespace):
    doc_id = stable_hash(namespace, document.law_id or document.law_name)
    processing = stable_hash("reviewed-case-v1", CASE_VERSION, model_signature, max_chars)
    revision = stable_hash(doc_id, document.law_name, document.source_hash, processing)
    if document.metadata.get("api_review_reference"):
        revision = stable_hash(revision, document.metadata["api_review_reference"])
    groups = {}
    for source in document.metadata["case_source_chunks"]:
        parent = source["metadata"]["parent_section_id"]
        group = groups.setdefault(parent, {"title": source["section"], "units": []})
        group["units"].append(LegalUnit(source["content"], len(group["units"]) + 1,
                                      spans=source["metadata"]["source_spans"]))
    chunks = []
    for ordinal, (parent, section) in enumerate(groups.items(), 1):
        pieces = pack_units(section["units"], max_chars)
        parent_text = "\n".join(unit.text for unit in section["units"])
        for index, (content, units) in enumerate(pieces, 1):
            metadata = {"document_type": "case", "evidence_kind": "case_material",
                        "source_spans": [span for unit in units for span in unit.spans],
                        "source_span_precision": "unit", "chunker_version": CASE_VERSION,
                        "paragraph_nos": [unit.paragraph_no for unit in units],
                        "parent_section_id": stable_hash(revision, parent), "parent_section_text": parent_text,
                        "section": section["title"], "section_detection": "heuristic",
                        "fragment_index": index, "fragment_total": len(pieces)}
            embedding_text = "案例资料｜" + document.law_name[:128] + "｜" + section["title"][:80] + "\n" + content
            chunks.append(Chunk(stable_hash(revision, parent, index, content), document.law_name,
                section["title"], "案例分节" + str(ordinal), index, content, embedding_text,
                stable_hash(model_signature, embedding_text), metadata))
    if document.metadata.get("source_range"):
        for chunk in chunks: chunk.metadata["source_scope"]=document.metadata["source_range"]
    quality = validate_chunks(chunks, max_chars)
    return doc_id, revision, chunks, {
        **{key: value for key, value in document.metadata.items() if key != "case_source_chunks"},
        "quality": quality, "law_id": document.law_id, "schema_version": "reviewed-case-v1",
        "chunker_version": CASE_VERSION, "processing_signature": processing,
        "source_path": document.source_path}
