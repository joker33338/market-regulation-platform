"""Article-first chunking. Paragraph/item metadata survives every fragment."""
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
    """相邻短款项合并；超长单元仍受上限约束，保留其来源范围。"""
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


def split_articles(articles: list[Article], *, law_name: str, doc_version_id: str,
                   model_signature: str, max_chars: int = 800) -> list[Chunk]:
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

