"""Streaming, read-only adapter for the existing source main/detail tables."""
from __future__ import annotations

import re

from qa_core.indexing.models import Article, LegalDocument, SourceLine
from qa_core.indexing.legal_structure import ARTICLE, HEADING, parse_articles
from qa_core.utils import IngestionError, stable_hash

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def source_sql(main_table: str, detail_table: str) -> str:
    if not IDENTIFIER.fullmatch(main_table) or not IDENTIFIER.fullmatch(detail_table):
        raise IngestionError("源表名必须是简单 SQL 标识符。")
    return f"""SELECT m.id AS source_id,m.title AS law_name,d.auto_id AS detail_id,
        d.art_title AS chapter,d.article_number AS article_no,d.article_text AS content
        FROM {detail_table} d JOIN {main_table} m ON m.id=d.law_record_id
        WHERE d.article_text IS NOT NULL AND btrim(d.article_text)<>''
        AND d.article_number IS NOT NULL AND btrim(d.article_number)<>''
        ORDER BY m.id,d.auto_id"""


def _document(rows: list[dict], source_system: str) -> LegalDocument:
    articles = []
    seen = set()
    part = chapter = section = ""
    non_article_records = []
    for index, row in enumerate(rows, 1):
        number = re.sub(r"\s+", "", row["article_no"])
        heading = HEADING.fullmatch(number)
        if number in {"前言", "序言"} or heading:
            # These are genuine source records, but are not numbered articles.
            # Keep their text and IDs for review and use explicit headings as hierarchy.
            content = row["content"].strip()
            non_article_records.append({"source_record_id": str(row["detail_id"]),
                                        "label": number, "content": content})
            if heading:
                title = number + (" " + content if content else "")
                if heading.group(1) == "编":
                    part, chapter, section = title, "", ""
                elif heading.group(1) == "章":
                    chapter, section = title, ""
                else:
                    section = title
            continue
        match = ARTICLE.match(number)
        if not match or match.group(2):
            raise IngestionError("源表条号格式不受支持，请先核对 article_number。")
        if number in seen:
            raise IngestionError("同一法规源表存在重复条号。")
        seen.add(number)
        content = row["content"].strip()
        content_match = ARTICLE.match(content)
        if content_match:
            if re.sub(r"\s+", "", content_match.group(1)) != number:
                raise IngestionError("源表条号与正文条号不一致。")
            content = content_match.group(2)
        body_lines = [SourceLine(number + " " + content, 1, index)] if "\n" not in content else [
            SourceLine((number + " " if i == 1 else "") + value, 1, index * 100000 + i)
            for i, value in enumerate(content.splitlines(), 1)]
        article = parse_articles(body_lines)[0]
        article.part = part
        article.chapter = chapter or row["chapter"] or ""
        article.section = section
        for unit in article.units:
            for span in unit.spans:
                span["source_record_id"] = str(row["detail_id"])
        articles.append(article)
    if not articles:
        raise IngestionError("源法规只有前言或标题，没有可处理的编号条文。")
    first = rows[0]
    return LegalDocument(
        law_name=first["law_name"], law_id=source_system + ":" + str(first["source_id"]),
        source_hash=stable_hash(rows), source_path="postgres-source:" + source_system + ":" + str(first["source_id"]),
        lines=[], articles=articles,
        metadata={"source_system": source_system, "source_record_id": str(first["source_id"]),
                  "paragraph_basis": "database_text",
                  "chapter_semantics": "explicit_heading_or_source_art_title_unverified",
                  "non_article_records": non_article_records},
    )


def load_pg_documents(dsn: str, *, main_table: str = "national_laws_regulations",
                      detail_table: str = "national_laws_regulations_detail", limit_laws: int = 0):
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:
        raise IngestionError("读取 PostgreSQL 源数据需要 psycopg2-binary。") from exc
    sql = source_sql(main_table, detail_table)
    connection = psycopg2.connect(dsn, connect_timeout=5, application_name="market_regulation_source_readonly")
    try:
        connection.set_session(readonly=True)
        with connection.cursor(name="legal_source", cursor_factory=RealDictCursor) as cursor:
            cursor.itersize = 500
            cursor.execute(sql)
            group = []
            completed = 0
            for row in cursor:
                if group and row["source_id"] != group[0]["source_id"]:
                    yield _document(group, main_table)
                    completed += 1
                    if limit_laws and completed >= limit_laws:
                        return
                    group = []
                group.append(dict(row))
            if group:
                yield _document(group, main_table)
    finally:
        connection.rollback()
        connection.close()

