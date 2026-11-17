"""将页级解析结果转换为法规处理输入。

复用页号、文本块及来源证据生成 SourceLine 和 LegalDocument；不生成向量或
写入数据库。含表格的结果由现有门禁拒绝转换，避免结构被摊平成法律条文。
调用方仍须负责验证审核身份与权限，本模块不提供认证或发布授权。"""
from __future__ import annotations

from datetime import datetime, timezone

from qa_core.indexing.models import LegalDocument, SourceLine
from qa_core.utils import IngestionError, stable_hash
from .schemas import DocumentResult, json_safe


def source_lines(result: DocumentResult):
    """从正文块生成来源行，并返回用于计算内容指纹的块级证据。

    参数 result 为已持久化的统一解析结果。跳过表格、图片、页眉页脚、页码和
    脚注块；每页重新计行号，每块首行标记为段落起点，保留该块 bbox。
    返回 (lines, evidence)，不写入审核记录，也不推断页内字符级坐标。"""
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
    return lines, evidence


# 解析结果必须经过明确复核后才进入法规处理，识别完成不代表法律审核通过。
def to_legal_document(result: DocumentResult, *, reviewer: str, law_name: str, law_id: str | None = None) -> LegalDocument:
    """将可接受的完整解析结果转换为法规处理对象。

    reviewer 和 law_name 必须为非空字符串，law_id 可由调用方指定。
    拒绝失败、部分失败、无页结果及任何含表格的结果；本适配器尚不能将表格
    安全转换为法条，不能靠忽略表格让数据进入正式入库。
    来源指纹覆盖文档身份、协议版本及块证据；返回对象携带复核说明与来源，
    但本函数不验证登录身份、不生成向量，也不修改数据库或发布知识库。"""
    if result.parsing_status not in {"success", "needs_review"} or not result.pages:
        raise IngestionError("失败或部分失败的解析结果不能交给正式入库。")
    if not reviewer.strip() or not law_name.strip():
        raise IngestionError("需要明确复核人及法规名称；OCR 质量检查不能替代审核。")
    if any(page.tables or any(block.kind == "table" for block in page.layout_blocks) for page in result.pages):
        raise IngestionError("当前法律切分器不消费表格；请保留 tables，另用表格入库适配器，禁止摊平成法条。")
    lines, evidence = source_lines(result)
    fingerprint = stable_hash(result.document_id, result.schema_version, evidence)
    return LegalDocument(law_name.strip(), fingerprint, result.source_location.get("file_path", result.file_name),
                         lines, law_id, metadata={
                             "format": result.file_type, "file_sha256": result.document_id,
                             "parsing_schema": result.schema_version, "source_evidence": evidence,
                             "review": {"reviewer": reviewer.strip(), "reviewed_at": datetime.now(timezone.utc).isoformat(),
                                        "reviewed_output_hash": fingerprint},
                             "paragraph_basis": "parser_blocks_requires_legal_review",
                         })

