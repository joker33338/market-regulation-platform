"""法规/案例分别切分的只读预览；不审核、向量化、建表或发布版本。"""
from dataclasses import asdict
import re

from qa_core.config.settings import CHUNKER_VERSION
from qa_core.document_parsing.bridge import source_lines
from qa_core.indexing.chunking import pack_units, split_articles
from qa_core.indexing.legal_cleaner import clean_lines
from qa_core.indexing.legal_structure import ARTICLE, parse_articles
from qa_core.indexing.models import LegalUnit
from qa_core.utils import IngestionError, stable_hash

CASE_VERSION = "case-sections-v1"
CASE_HEADING = re.compile(r"^(?:[一二三四五六七八九十]+[、．.]|[（(][一二三四五六七八九十]+[）)])\s*(.{1,60})$")
NAMED_HEADING = re.compile(r"^(?:当事人(?:基本情况)?|调查(?:经过|情况)|违法事实(?:及证据)?|事实(?:及证据)?|证据|处罚依据|法律适用|处罚决定|处罚内容|救济途径|复议诉讼权利)[：:]?$")
CASE_TOPIC = re.compile(r"当事人|案由|调查|事实|证据|违法|法律|依据|处罚|决定|裁量|复议|诉讼|救济|程序|告知|陈述|申辩|听证")


def compact(text):
    return re.sub(r"\s+", "", text)


def preview_chunks(result, document_type: str, *, max_chars=800):
    if document_type not in {"law", "case"}:
        raise IngestionError("请明确选择法规或处罚案例。")
    if type(max_chars) is not int or not 64 <= max_chars <= 1600:
        raise IngestionError("预览片段上限应在64至1600字之间。")
    if result.parsing_status not in {"success", "needs_review"} or not result.pages:
        raise IngestionError("请先完成全部页面解析，再预览切分。")
    lines, _ = source_lines(result)
    lines, _ = clean_lines(lines)
    tables = [{"page_number": page.page_number, **asdict(table)} for page in result.pages for table in page.tables]
    if document_type == "law" and tables:
        raise IngestionError("法规含表格，须独立处理表格并复核，不能摊平成法条。")
    strategy_version = CHUNKER_VERSION if document_type == "law" else CASE_VERSION
    revision = stable_hash(result.document_id, result.schema_version, document_type, strategy_version, max_chars,
                           [(line.text, line.page, line.line, line.new_paragraph, line.bbox) for line in lines])
    warnings = ["仅供切分复核，尚未写入RAG索引或发布知识库。"]
    if document_type == "law":
        articles = parse_articles(lines)
        chunks = [asdict(chunk) for chunk in split_articles(articles, law_name=result.file_name,
                  doc_version_id=revision, model_signature="PREVIEW-NO-EMBEDDING", max_chars=max_chars)]
        parents = [{"parent_id": stable_hash(revision, article.article_no), "label": article.article_no,
                    "text": article.text} for article in articles]
        expected_body = "".join(unit.text for article in articles for unit in article.units)
        actual_body = "".join(chunk["content"][len(chunk["article_no"]):] for chunk in chunks)
        first_article = next(index for index, line in enumerate(lines)
                             if ARTICLE.match(re.sub(r"^\s*#{1,6}\s*", "", line.text).strip()))
        unassigned = [{"page": line.page, "line": line.line, "text": line.text}
                      for line in lines[:first_article] if line.text]
        warnings.append("法规名称、效力状态和适用时间需确认；预览使用文件标题，不据此认定法律身份。")
    else:
        sections = []
        title, units = "文书前部", []
        paragraph = 0
        for line in lines:
            text = line.text
            if not text:
                continue
            numbered = CASE_HEADING.fullmatch(text)
            heading = line.new_paragraph and bool(NAMED_HEADING.fullmatch(text) or (
                numbered and CASE_TOPIC.search(numbered.group(1)) and not re.search(r"[。；;]", text)))
            # 只在原始新段开始识别标题，正文中的引述法条从不作为法规分支解析。
            if heading and line.new_paragraph:
                if units:
                    sections.append((title, units))
                title, units = text, []
            span = {"page": line.page, "line": line.line}
            if line.bbox:
                span["bbox"] = line.bbox
            if units and not line.new_paragraph and not heading:
                units[-1].text += text
                units[-1].spans.append(span)
            else:
                paragraph += 1
                units.append(LegalUnit(text, paragraph, spans=[span]))
        if units:
            sections.append((title, units))
        if not sections:
            raise IngestionError("没有可切分的正文。")
        expected_body = "".join(line.text for line in lines)
        unassigned = []
        parents, chunks = [], []
        for section_index, (title, units) in enumerate(sections, 1):
            parent_text = "\n".join(unit.text for unit in units)
            parent_id = stable_hash(revision, "case", section_index, parent_text)
            parents.append({"parent_id": parent_id, "label": title, "text": parent_text})
            pieces = pack_units(units, max_chars)
            for index, (content, sources) in enumerate(pieces, 1):
                chunks.append({"chunk_id": stable_hash(parent_id, index, content), "seq": len(chunks)+1,
                    "document_title": result.file_name, "section": title, "content": content,
                    "embedding_text": "案例资料｜"+result.file_name[:128]+"｜"+title[:80]+"\n"+content,
                    "metadata": {"document_type": "case", "evidence_kind": "case_material",
                        "parent_section_id": parent_id, "parent_section_text": parent_text,
                        "fragment_index": index, "fragment_total": len(pieces), "chunker_version": CASE_VERSION,
                        "paragraph_nos": [unit.paragraph_no for unit in sources],
                        "source_spans": [span for unit in sources for span in unit.spans],
                        "source_span_precision": "unit", "section_detection": "heuristic",
                        "requires_review": True}})
        actual_body = "".join(chunk["content"] for chunk in chunks)
        warnings.append("案例原文可能含指控、陈述或机关认定，未自动判定其真实性；案例引用的法条须另检索法规核验。")
    if tables:
        warnings.append("表格以原结构单独保留，未混入文字片段。")
    for chunk in chunks:
        chunk["metadata"].update(document_type=document_type, input_sha256=result.document_id,
                                 requires_review=True, preview_only=True)
    coverage = compact(expected_body) == compact(actual_body)
    located = all(chunk["metadata"]["source_spans"] for chunk in chunks)
    bounded = all(0 < len(chunk["content"]) <= max_chars for chunk in chunks)
    unique = len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
    if not all((coverage, located, bounded, unique)):
        raise IngestionError("切分完整性检查失败，禁止将当前预览用于正式入库。")
    body_pages = {line.page for line in lines if line.text}
    missing_pages = [page.page_number for page in result.pages
                     if page.raw_text.strip() and page.page_number not in body_pages and not page.tables]
    excluded = [{"page": page.page_number, "kind": block.kind, "characters": len(block.raw_text)}
                for page in result.pages for block in page.layout_blocks
                if block.kind in {"image", "header", "footer", "number", "footnote"} and block.raw_text.strip()]
    mismatched_pages = [page.page_number for page in result.pages if not page.tables and
                        compact(page.raw_text) != compact("".join(block.raw_text for block in page.layout_blocks))]
    if missing_pages:
        warnings.append("有页面正文未进入文本切分，请检查版面块与解析正文是否一致。")
    if excluded:
        warnings.append("存在按版面类型排除的页眉、页脚、注释或图片说明，原结果保留，须核对是否含业务内容。")
    if mismatched_pages:
        warnings.append("有页面的解析正文与版面块文字不一致，切分覆盖通过不代表该差异已解决。")
    return {"mode": "preview", "document_type": document_type, "revision": revision,
            "file_name": result.file_name, "input_sha256": result.document_id, "max_chars": max_chars,
            "chunk_count": len(chunks), "parent_count": len(parents), "chunks": chunks,
            "parents": parents, "tables": tables, "warnings": warnings, "requires_review": True,
            "unassigned_preface": unassigned,
            "quality": {"body_roundtrip_equal": coverage, "bounded": bounded, "unique_chunk_ids": unique,
                        "all_chunks_located": located, "body_characters_without_whitespace": len(compact(expected_body)),
                        "pages_with_body": sorted(body_pages), "pages_without_body_chunks": missing_pages,
                        "pages_with_text_layout_mismatch": mismatched_pages,
                        "small_chunks_under_80_chars": sum(len(chunk["content"]) < 80 for chunk in chunks),
                        "unassigned_preface_lines": len(unassigned), "excluded_layout_blocks": excluded,
                        "scope": "仅检查解析正文到切分结果的完整性，不代表OCR与原文件逐字一致或法律结构已复核。"},
            "rag_index_written": False}
