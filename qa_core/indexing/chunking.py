"""按法条优先切分检索片段，并保留款、项和原文位置。

短条文整体保留，长条文按法律单元组合或继续拆分；日期、金额、文号等受保护
字段不得从中截断。向量输入增加标题上下文，但展示正文与来源范围单独保存。"""
from __future__ import annotations

import re

from qa_core.config.settings import CHUNKER_VERSION
from qa_core.indexing.models import Article, Chunk, LegalUnit
from qa_core.utils import IngestionError, stable_hash

PROTECTED_VALUE = re.compile(
    r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|"
    r"[〔［【（(\[]\d{4}[〕］】）)\]](?:第)?\d+(?:号)?|"
    r"\d+(?:[.,，．:/\-]\d+)*(?:\s*(?:[%％‰]|[万亿]?元))?"
)


def bounded_parts(text: str, limit: int) -> list[str]:
    """按字符预算切分正文，同时保护可识别的日期、数值和文号核心。

    limit 至少为 32；优先选择预算窗口后部的句末或换行，必要时退回到受保护
    字段之前。单个受保护字段本身超过预算时抛出 IngestionError，交由调用方
    增大预算并复核。返回由非空片段组成的列表；空文本返回空列表。仅移除片段边界空白，
    不改写内部正文。"""
    if limit < 32:
        raise IngestionError("max-chars 至少为 32。")
    result = []
    rest = text.strip()
    while len(rest) > limit:
        window = rest[:limit]
        cuts = [match.end() for match in re.finditer(r"[。；;！？\n]", window)]
        boundary = cuts[-1] if cuts and cuts[-1] >= limit // 3 else limit
        # 优先退到可识别数值、日期或文号核心之前，不改写原字符串。
        for match in PROTECTED_VALUE.finditer(rest, 0, min(len(rest), limit + 128)):
            if match.start() >= boundary:
                break
            if match.start() < boundary < match.end():
                if match.start():
                    boundary = match.start()
                elif match.end() <= limit:
                    boundary = match.end()
                else:
                    raise IngestionError("单个数值、日期或文号核心超过片段上限，请增加上限后复核；未截断该字段。")
                break
        result.append(rest[:boundary].strip())
        rest = rest[boundary:].lstrip()
    if rest:
        result.append(rest)
    return result


def pack_units(units: list[LegalUnit], limit: int) -> list[tuple[str, list[LegalUnit]]]:
    """按原顺序把相邻法律单元组合成预算内片段，同时返回各片段的来源单元。

    超长单元先交给 bounded_parts 拆分；组合时计入插入的换行。一个单元可对应
    多个片段，每个片段内按对象身份去重来源单元，从而保留款项和位置依据。"""
    pieces = []
    text, sources = "", []
    for unit in units:
        for part in bounded_parts(unit.text, limit):
            candidate = text + ("\n" if text else "") + part
            if text and len(candidate) > limit:
                pieces.append((text, sources))
                text, sources = "", []
            text += ("\n" if text else "") + part
            if not any(source is unit for source in sources):
                sources.append(unit)
    if text:
        pieces.append((text, sources))
    return pieces


# 以法条层级作为父块，按预算拆子块并保留原始来源，不能用截断掩盖超长条文。
def split_articles(articles: list[Article], *, law_name: str, doc_version_id: str,
                   model_signature: str, max_chars: int = 800) -> list[Chunk]:
    """将条文转换为带来源、父条文身份和模型签名的检索片段。

    短条文完整保留，长条文先按款项单元组合。标题和必要的引导语只加入
    embedding_text；正文 content 与来源 spans 另外保留，便于展示和引用核对。
    max_chars 主要约束正文切分；标题及引导语另有预算，因此向量输入总长度
    不能直接等同 max_chars。本函数不调用向量模型，也不执行入库或发布。"""
    chunks = []
    for article in articles:
        path = " / ".join(item for item in [article.part, article.chapter, article.section] if item)
        heading = f"《{law_name}》 {path} {article.article_no}".strip()
        heading_limit = max(64, min(256, max_chars // 2))
        prefix = heading[:heading_limit] + "\n"
        intro = article.units[0].text if article.units and not article.units[0].item_no else ""
        pieces: list[tuple[str, list[LegalUnit]]] = []
        if len(article.text) <= max_chars:
            pieces.append((article.text, article.units))
        else:
            pieces = [(article.article_no + " " + text, units) for text, units in
                      pack_units(article.units, max_chars - len(article.article_no) - 1)]
        for seq, (content, units) in enumerate(pieces, 1):
            context_limit = min(200, max_chars // 3)
            needs_context = bool(intro and any(unit.item_no for unit in units) and intro not in content)
            context = intro[:context_limit] + "\n" if needs_context else ""
            embedding_text = prefix + context + content
            spans = [span for unit in units for span in unit.spans]
            metadata = {
                "part": article.part, "chapter": article.chapter, "section": article.section,
                "paragraph_nos": sorted({unit.paragraph_no for unit in units}),
                "item_nos": [unit.item_no for unit in units if unit.item_no],
                "source_spans": spans,
                "fragment_index": seq, "fragment_total": len(pieces),
                "parent_article_id": stable_hash(doc_version_id, article.article_no),
                "parent_article_text": article.text,
                "paragraph_status": "inferred_from_source_layout",
                "document_type": "law", "evidence_kind": "normative_text",
                "chunker_version": CHUNKER_VERSION, "source_span_precision": "unit",
                "embedding_context_truncated": needs_context and len(intro) > context_limit,
                "embedding_heading_truncated": len(heading) > heading_limit,
            }
            chunks.append(Chunk(
                stable_hash(doc_version_id, article.article_no, seq, content),
                law_name, path, article.article_no, seq, content, embedding_text,
                stable_hash(model_signature, embedding_text), metadata,
            ))
    return chunks

