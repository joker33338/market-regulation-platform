"""Small mandatory checks before any candidate can be published."""
from __future__ import annotations

from qa_core.indexing.models import Chunk
from qa_core.utils import IngestionError


def validate_chunks(chunks: list[Chunk], max_chars: int) -> dict:
    if not chunks:
        raise IngestionError("没有有效法条片段。")
    keys = set()
    for chunk in chunks:
        key = (chunk.law_name, chunk.article_no, chunk.seq)
        if key in keys:
            raise IngestionError("片段的兼容键重复。")
        keys.add(key)
        if not chunk.content.strip() or len(chunk.content) > max_chars:
            raise IngestionError("片段为空或超过字符上限。")
        if not chunk.metadata["source_spans"]:
            raise IngestionError("片段缺少来源定位。")
    return {"chunks": len(chunks), "max_chars": max(len(chunk.content) for chunk in chunks),
            "articles": len({chunk.article_no for chunk in chunks}), "passed": True}

