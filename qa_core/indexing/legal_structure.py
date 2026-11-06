"""Stateful chapter/section/article/paragraph/item parsing, without LLM rewriting."""
from __future__ import annotations

import re

from qa_core.indexing.models import Article, LegalUnit, SourceLine
from qa_core.utils import IngestionError

NUM = r"[〇零一二三四五六七八九十百千万两0-9]+"
ARTICLE = re.compile(rf"^(第\s*{NUM}\s*条(?:\s*之\s*{NUM})?)[\s\u3000]*(.*)$")
HEADING = re.compile(rf"^第\s*{NUM}\s*([编章节])(?:\s*.*)?$")
ITEM = re.compile(rf"^([（(]{NUM}[）)]|[0-9]+[、.．])(.*)$")


def parse_articles(lines: list[SourceLine]) -> list[Article]:
    articles = []
    current = None
    part = chapter = section = ""
    paragraph_no = 0
    previous = None
    seen = set()
    for line in lines:
        text = re.sub(r"^\s*#{1,6}\s*", "", line.text).strip()
        if not text:
            previous = None
            continue
        if text in {"目录", "目 录"}:
            raise IngestionError("材料包含目录；MVP 请提供正文，避免目录与正文重复条号。")
        heading = HEADING.fullmatch(text)
        if heading:
            if heading.group(1) == "编":
                part, chapter, section = text, "", ""
            elif heading.group(1) == "章":
                chapter, section = text, ""
            else:
                section = text
            previous = None
            continue
        match = ARTICLE.match(text)
        if match:
            article_no = re.sub(r"\s+", "", match.group(1))
            if article_no in seen:
                raise IngestionError(f"同一文档出现重复条号 {article_no}；请检查目录、合订本或来源数据。")
            seen.add(article_no)
            current = Article(article_no, chapter, section, part)
            articles.append(current)
            paragraph_no = 0
            previous = None
            text = match.group(2)
            if not text:
                continue
        if current is None:
            continue
        span = {"page": line.page, "line": line.line}
        if line.bbox:
            span["bbox"] = line.bbox
        item_match = ITEM.match(text)
        if item_match:
            if paragraph_no == 0:
                paragraph_no = 1
            unit = LegalUnit(text, paragraph_no, item_match.group(1), [span])
            current.units.append(unit)
            previous = unit
        elif previous is not None and not line.new_paragraph:
            previous.text += text
            previous.spans.append(span)
        else:
            paragraph_no += 1
            unit = LegalUnit(text, paragraph_no, None, [span])
            current.units.append(unit)
            previous = unit
    if not articles:
        raise IngestionError("没有识别到“第…条”法条；MVP 不将无结构全文自动当作一条。")
    empty = [article.article_no for article in articles if not article.units]
    if empty:
        raise IngestionError("存在只有条号而无正文的条文，请检查解析结果。")
    return articles

