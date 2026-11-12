"""document_review 的租户范围只读查询，不依赖不完整的 v_review_queue。"""
from contextlib import contextmanager

from qa_core.document_parsing.mineru_client import MinerUError


class ReviewReader:
    def __init__(self, dsn):
        self.dsn = dsn

    @contextmanager
    def cursor(self):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        connection = psycopg2.connect(self.dsn, connect_timeout=5,
                                      application_name="frontend_review_read")
        try:
            connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
            with connection:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '5s'")
                    yield cursor
        finally:
            connection.close()

    def listing(self, owner, page, page_size, requires_review=None):
        where = "source_location->>'owner_id'=%s"
        args = [owner]
        if requires_review is not None:
            where += " AND requires_review=%s"
            args.append(requires_review)
        with self.cursor() as cursor:
            cursor.execute("SELECT count(*) AS total FROM document_review.documents WHERE " + where, args)
            total = cursor.fetchone()["total"]
            cursor.execute("""SELECT parse_id,document_id,file_name,file_type,parsing_status,
                requires_review,source_location,quality,imported_at FROM document_review.documents WHERE """ +
                where + " ORDER BY imported_at DESC,parse_id LIMIT %s OFFSET %s",
                [*args, page_size, (page - 1) * page_size])
            return {"list": [dict(row) for row in cursor.fetchall()], "total": total,
                    "page": page, "page_size": page_size, "source": "document_review.documents"}

    def detail(self, owner, parse_id):
        with self.cursor() as cursor:
            cursor.execute("""SELECT parse_id,document_id,file_name,file_type,parsing_status,
                requires_review,source_location,quality,raw_text,markdown_content,original_result,imported_at
                FROM document_review.documents WHERE parse_id=%s AND source_location->>'owner_id'=%s""",
                (parse_id, owner))
            row = cursor.fetchone()
        if row is None:
            raise MinerUError("document_not_found", 404)
        return dict(row)

    def stats(self, owner):
        with self.cursor() as cursor:
            cursor.execute("""SELECT count(*) AS total,
                count(*) FILTER (WHERE requires_review) AS requires_review
                FROM document_review.documents WHERE source_location->>'owner_id'=%s""", (owner,))
            return dict(cursor.fetchone())

    def health(self):
        with self.cursor() as cursor:
            cursor.execute("SELECT 1 FROM document_review.documents LIMIT 0")
        return True
