"""Article-first chunking. Paragraph/item metadata survives every fragment."""
from __future__ import annotations

import re

from qa_core.indexing.models import Article, Chunk, LegalUnit
from qa_core.utils import IngestionError, stable_hash


def bounded_parts(text: str, limit: int) -> list[str]:
    if limit < 32:
        raise IngestionError("max-chars 至少为 32。")
    result = []
    rest = text.strip()
    while len(rest) > limit:
        window = rest[:limit]
        cuts = [match.end() for match in re.finditer(r"[。；;！？\n]", window)]
        boundary = cuts[-1] if cuts and cuts[-1] >= limit // 3 else limit
        result.append(rest[:boundary].strip())
        rest = rest[boundary:].lstrip()
    if rest:
        result.append(rest)
    return result


def split_articles(articles: list[Article], *, law_name: str, doc_version_id: str,
                   model_signature: str, max_chars: int = 800) -> list[Chunk]:
    chunks = []
    for article in articles:
        path = " / ".join(item for item in [article.part, article.chapter, article.section] if item)
        prefix = f"《{law_name}》 {path} {article.article_no}\n".strip() + "\n"
        intro = article.units[0].text if article.units and not article.units[0].item_no else ""
        pieces: list[tuple[str, list[LegalUnit], int, int]] = []
        if len(article.text) <= max_chars:
            pieces.append((article.text, article.units, 1, 1))
        else:
            for unit in article.units:
                # Account for the article label in the projected content limit.
                parts = bounded_parts(unit.text, max_chars - len(article.article_no) - 1)
                for index, text in enumerate(parts, 1):
                    pieces.append((article.article_no + " " + text, [unit], index, len(parts)))
        for seq, (content, units, fragment, total) in enumerate(pieces, 1):
            context = intro + "\n" if len(units) == 1 and units[0].item_no and intro else ""
            embedding_text = prefix + context + content
            spans = [span for unit in units for span in unit.spans]
            metadata = {
                "part": article.part, "chapter": article.chapter, "section": article.section,
                "paragraph_nos": sorted({unit.paragraph_no for unit in units}),
                "item_nos": [unit.item_no for unit in units if unit.item_no],
                "source_spans": spans,
                "fragment_index": fragment, "fragment_total": total,
                "parent_article_id": stable_hash(doc_version_id, article.article_no),
                "parent_article_text": article.text,
                "paragraph_status": "inferred_from_source_layout",
            }
            chunks.append(Chunk(
                stable_hash(doc_version_id, article.article_no, seq, content),
                law_name, path, article.article_no, seq, content, embedding_text,
                stable_hash(model_signature, embedding_text), metadata,
            ))
    return chunks

