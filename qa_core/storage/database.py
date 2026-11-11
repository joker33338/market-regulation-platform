"""PostgreSQL storage and a dependency-free SQLite demo using the same lifecycle."""
from __future__ import annotations

import contextlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from qa_core.indexing.models import Chunk
from qa_core.utils import IngestionError, json_text

VERSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS mr_kb_versions (
    kb_version TEXT PRIMARY KEY, base_version TEXT,
    status TEXT NOT NULL, processing_signature TEXT NOT NULL,
    model_signature TEXT NOT NULL, dimension INTEGER NOT NULL,
    created_at TEXT NOT NULL, stats TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS mr_document_versions (
    doc_version_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, source_hash TEXT NOT NULL,
    law_name TEXT NOT NULL, metadata TEXT NOT NULL, chunk_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS mr_chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_version_id TEXT NOT NULL REFERENCES mr_document_versions(doc_version_id),
    law_name TEXT NOT NULL, chapter TEXT NOT NULL, article_no TEXT NOT NULL, seq INTEGER NOT NULL,
    content TEXT NOT NULL, embedding_text TEXT NOT NULL, input_hash TEXT NOT NULL,
    metadata TEXT NOT NULL, embedding VECTOR_TYPE NOT NULL
);
CREATE INDEX IF NOT EXISTS mr_chunks_input_hash_idx ON mr_chunks(input_hash);
CREATE INDEX IF NOT EXISTS mr_chunks_document_idx ON mr_chunks(doc_version_id);
CREATE TABLE IF NOT EXISTS mr_kb_documents (
    kb_version TEXT NOT NULL REFERENCES mr_kb_versions(kb_version),
    doc_id TEXT NOT NULL, doc_version_id TEXT NOT NULL REFERENCES mr_document_versions(doc_version_id),
    source_path TEXT NOT NULL,
    PRIMARY KEY(kb_version, doc_id)
);
CREATE TABLE IF NOT EXISTS mr_active (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1), kb_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mr_active_chunk_map (
    law_name TEXT NOT NULL, article_no TEXT NOT NULL, seq INTEGER NOT NULL,
    chunk_id TEXT NOT NULL REFERENCES mr_chunks(chunk_id), kb_version TEXT NOT NULL,
    PRIMARY KEY(law_name, article_no, seq)
);
CREATE TABLE IF NOT EXISTS mr_release_history (
    event_id TEXT PRIMARY KEY, from_version TEXT, to_version TEXT NOT NULL,
    action TEXT NOT NULL, created_at TEXT NOT NULL
);
"""

KB_TABLES = ('law_chunks', 'mr_kb_versions', 'mr_document_versions', 'mr_chunks',
             'mr_kb_documents', 'mr_active', 'mr_active_chunk_map', 'mr_release_history')
KB_RELATION = re.compile(r'\b(?:' + '|'.join(KB_TABLES) + r')\b', re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, *, sqlite_path: str | Path | None = None, pg_dsn: str | None = None,
                 kb_schema: str = 'public'):
        if bool(sqlite_path) == bool(pg_dsn):
            raise IngestionError("必须且只能选择 SQLite 文件或显式 PG_DSN。")
        self.postgres = pg_dsn is not None
        if not isinstance(kb_schema, str) or not re.fullmatch(r'public|mvp_test_[0-9a-f]{32}', kb_schema):
            raise IngestionError('知识库目标必须是 public 或显式的自有 mvp_test_<32hex> Schema。')
        self.kb_schema = kb_schema
        self._initializing = False
        if self.postgres:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
            except ImportError as exc:
                raise IngestionError("PostgreSQL 驱动未安装，请安装 requirements.txt。") from exc
            self.connection = psycopg2.connect(pg_dsn, connect_timeout=5,
                                                application_name="market_regulation_mvp",
                                                cursor_factory=RealDictCursor)
            self.connection.autocommit = True
        else:
            path = Path(sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(str(path), isolation_level=None, timeout=30)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys=ON")
        self._in_transaction = False

    def verify_schema(self, *, allow_missing: bool = False):
        """发送业务 SQL 前重新核验，不能借 public 回退或临时同名表跨域。"""
        if not self.postgres:
            return
        with self.connection.cursor() as cursor:
            cursor.execute("""SELECT current_schema() AS current_schema,
                to_regnamespace(%s)::oid AS namespace_oid,
                to_regtype('vector')::oid AS visible_vector,
                to_regtype('public.vector')::oid AS public_vector,
                (SELECT pg_get_userbyid(nspowner)=current_user FROM pg_namespace
                 WHERE oid=to_regnamespace(%s)) AS owns_schema""", (self.kb_schema, self.kb_schema))
            identity = cursor.fetchone()
            if not identity['namespace_oid'] or identity['current_schema'] != self.kb_schema:
                raise IngestionError('知识库 Schema 身份不匹配，已拒绝操作。')
            if self.kb_schema != 'public' and not identity['owns_schema']:
                raise IngestionError('只能使用当前角色拥有的 QA Schema。')
            if (identity['visible_vector'] != identity['public_vector'] or
                    not identity['public_vector'] and not (allow_missing and self.kb_schema == 'public')):
                raise IngestionError('知识库必须使用既有 public.vector 类型。')
            cursor.execute("""SELECT x.name,c.oid AS expected_oid,c.relnamespace AS namespace_oid,
                c.relkind,to_regclass(x.name)::oid AS visible_oid,
                EXISTS(SELECT 1 FROM pg_constraint f JOIN pg_class t ON t.oid=f.confrelid
                       WHERE f.conrelid=c.oid AND f.contype='f'
                       AND t.relnamespace<>c.relnamespace) AS foreign_domain
                FROM unnest(%s::text[]) AS x(name)
                LEFT JOIN pg_class c ON c.oid=to_regclass(format('%%I.%%I',%s,x.name))""",
                (list(KB_TABLES), self.kb_schema))
            relations = cursor.fetchall()
        if len(relations) != len(KB_TABLES):
            raise IngestionError('知识库关系核验不完整。')
        for relation in relations:
            if not relation['expected_oid'] and allow_missing:
                continue
            if (not relation['expected_oid'] or relation['expected_oid'] != relation['visible_oid']
                    or relation['namespace_oid'] != identity['namespace_oid']
                    or relation['relkind'] not in {'r', 'p'} or relation['foreign_domain']):
                raise IngestionError('知识库关系缺失或跨 Schema，已拒绝操作。')
        return sum(bool(relation['expected_oid']) for relation in relations)

    def execute(self, sql: str, params: dict | None = None):
        if self.postgres:
            if KB_RELATION.search(sql):
                self.verify_schema(allow_missing=self._initializing)
            sql = re.sub(r"(?<!:):([a-zA-Z_]\w*)", r"%(\1)s", sql)
            cursor = self.connection.cursor()
            cursor.execute(sql, params or {})
        else:
            cursor = self.connection.execute(sql, params or {})
        return cursor

    def one(self, sql: str, params: dict | None = None) -> dict | None:
        cursor = self.execute(sql, params)
        try:
            row = cursor.fetchone()
            return dict(row) if row is not None else None
        finally:
            cursor.close()

    def all(self, sql: str, params: dict | None = None) -> list[dict]:
        cursor = self.execute(sql, params)
        try:
            return [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    @contextlib.contextmanager
    def transaction(self, *, read_only: bool = False):
        if self._in_transaction:
            raise IngestionError("不支持嵌套事务。")
        self.execute("BEGIN").close()
        self._in_transaction = True
        try:
            if read_only and self.postgres:
                self.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY").close()
            yield
            self.execute("COMMIT").close()
        except BaseException:
            self.execute("ROLLBACK").close()
            raise
        finally:
            self._in_transaction = False

    def initialize(self):
        if self.postgres:
            present = self.verify_schema(allow_missing=True)
            if present not in {0, len(KB_TABLES)}:
                raise IngestionError('目标知识库只有部分表，禁止自动补建；须先核验完整性。')
        self._initializing = True
        try:
            self._initialize()
            self.verify_schema()
        finally:
            self._initializing = False

    def _initialize(self):
        with self.transaction():
            if self.postgres:
                statements = Path(__file__).with_name("postgres_schema.sql").read_text(encoding="utf-8")
                statements = "\n".join(line for line in statements.splitlines() if not line.lstrip().startswith("--"))
            else:
                statements = """CREATE TABLE IF NOT EXISTS law_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, law_name TEXT NOT NULL,
                    chapter TEXT, article_no TEXT NOT NULL, seq INTEGER NOT NULL,
                    content TEXT NOT NULL, token_len INTEGER, embedding TEXT NOT NULL,
                    updated_at TEXT NOT NULL, UNIQUE(law_name, article_no, seq))"""
            for statement in statements.split(";"):
                if statement.strip():
                    self.execute(statement).close()
            schema = VERSION_SCHEMA.replace("VECTOR_TYPE", "vector(1024)" if self.postgres else "TEXT")
            for statement in schema.split(";"):
                if statement.strip():
                    self.execute(statement).close()

    def active_version(self) -> str | None:
        record = self.one("SELECT kb_version FROM mr_active WHERE singleton=1")
        return record["kb_version"] if record else None

    def version(self, version: str) -> dict:
        record = self.one("SELECT * FROM mr_kb_versions WHERE kb_version=:version", {"version": version})
        if record is None:
            raise IngestionError("知识库版本不存在。")
        return record

    def create_version(self, version: str, processing_signature: str, model_signature: str,
                       dimension: int, *, full_snapshot: bool = False):
        with self.transaction():
            active = self.active_version()
            if active and not full_snapshot:
                previous = self.version(active)
                if previous["processing_signature"] != processing_signature:
                    raise IngestionError("处理配置或模型已改变，必须用完整输入和 --full-snapshot 重建。")
            if self.one("SELECT kb_version FROM mr_kb_versions WHERE kb_version=:v", {"v": version}):
                raise IngestionError("版本号已存在，请使用新的版本号。")
            self.execute("""INSERT INTO mr_kb_versions
                (kb_version,base_version,status,processing_signature,model_signature,dimension,created_at)
                VALUES (:v,:b,'BUILDING',:p,:m,:d,:t)""",
                {"v": version, "b": active, "p": processing_signature, "m": model_signature,
                 "d": dimension, "t": utc_now()}).close()
            if active and not full_snapshot:
                self.execute("""INSERT INTO mr_kb_documents(kb_version,doc_id,doc_version_id,source_path)
                    SELECT :v,doc_id,doc_version_id,source_path FROM mr_kb_documents WHERE kb_version=:b""",
                    {"v": version, "b": active}).close()

    def revision_exists(self, doc_version_id: str) -> bool:
        return self.one("SELECT doc_version_id FROM mr_document_versions WHERE doc_version_id=:id",
                        {"id": doc_version_id}) is not None

    def cached_vector(self, input_hash: str) -> list[float] | None:
        row = self.one("SELECT embedding FROM mr_chunks WHERE input_hash=:hash LIMIT 1", {"hash": input_hash})
        if row is None:
            return None
        return json.loads(row["embedding"]) if isinstance(row["embedding"], str) else list(row["embedding"])

    def attach_revision(self, version: str, doc_id: str, doc_version_id: str, source_path: str):
        if self.version(version)["status"] != "BUILDING":
            raise IngestionError("只能向 BUILDING 版本写入文档。")
        self.execute("""INSERT INTO mr_kb_documents(kb_version,doc_id,doc_version_id,source_path)
            VALUES (:v,:d,:r,:s) ON CONFLICT(kb_version,doc_id) DO UPDATE
            SET doc_version_id=excluded.doc_version_id, source_path=excluded.source_path""",
            {"v": version, "d": doc_id, "r": doc_version_id, "s": source_path}).close()

    def save_revision(self, *, version: str, doc_id: str, doc_version_id: str, source_hash: str,
                      law_name: str, source_path: str, metadata: dict, chunks: list[Chunk]):
        with self.transaction():
            self.execute("""INSERT INTO mr_document_versions
                (doc_version_id,doc_id,source_hash,law_name,metadata,chunk_count)
                VALUES (:id,:d,:h,:n,:m,:c)""",
                {"id": doc_version_id, "d": doc_id, "h": source_hash, "n": law_name,
                 "m": json_text(metadata), "c": len(chunks)}).close()
            vector_param = "CAST(:e AS vector)" if self.postgres else ":e"
            for chunk in chunks:
                self.execute("""INSERT INTO mr_chunks
                    (chunk_id,doc_version_id,law_name,chapter,article_no,seq,content,embedding_text,
                     input_hash,metadata,embedding)
                    VALUES (:id,:r,:n,:c,:a,:s,:t,:et,:ih,:m,""" + vector_param + ")",
                    {"id": chunk.chunk_id, "r": doc_version_id, "n": chunk.law_name, "c": chunk.chapter,
                     "a": chunk.article_no, "s": chunk.seq, "t": chunk.content, "et": chunk.embedding_text,
                     "ih": chunk.input_hash, "m": json_text(chunk.metadata),
                     "e": json_text(chunk.embedding)}).close()
            self.attach_revision(version, doc_id, doc_version_id, source_path)

    def finish_version(self, version: str, stats: dict):
        with self.transaction():
            collision = self.one("""SELECT c.law_name,c.article_no,c.seq,COUNT(*) AS n
                FROM mr_chunks c JOIN mr_kb_documents d ON c.doc_version_id=d.doc_version_id
                WHERE d.kb_version=:v GROUP BY c.law_name,c.article_no,c.seq HAVING COUNT(*)>1 LIMIT 1""",
                {"v": version})
            if collision:
                raise IngestionError("候选版中存在同名法规兼容键冲突；请先明确法规身份和在线版本选择。")
            count = self.one("""SELECT COUNT(*) AS n FROM mr_chunks c JOIN mr_kb_documents d
                ON c.doc_version_id=d.doc_version_id WHERE d.kb_version=:v""", {"v": version})["n"]
            if not count:
                raise IngestionError("空版本禁止发布。")
            stats["candidate_chunks"] = count
            self.execute("UPDATE mr_kb_versions SET status='STAGED',stats=:s WHERE kb_version=:v AND status='BUILDING'",
                         {"s": json_text(stats), "v": version}).close()

    def fail_version(self, version: str):
        self.execute("UPDATE mr_kb_versions SET status='FAILED' WHERE kb_version=:v AND status='BUILDING'",
                     {"v": version}).close()

    def publish(self, version: str, *, rollback: bool = False):
        from uuid import uuid4
        self.verify_schema()
        with self.transaction():
            if self.postgres:
                self.execute("SELECT pg_advisory_xact_lock(737113)").close()
                self.execute("LOCK TABLE law_chunks IN SHARE ROW EXCLUSIVE MODE").close()
            target = self.version(version)
            active = self.active_version()
            if active == version:
                return
            if target["status"] not in ({"ARCHIVED"} if rollback else {"STAGED"}):
                raise IngestionError("目标不是可发布候选版或可回滚历史版。")
            if not rollback and active != target["base_version"]:
                raise IngestionError("构建期间 ACTIVE 已变化，请基于最新版本重新构建。")
            unmanaged = self.one("""SELECT COUNT(*) AS n FROM law_chunks l LEFT JOIN mr_active_chunk_map m
                ON l.law_name=m.law_name AND l.article_no=m.article_no AND l.seq=m.seq
                WHERE m.chunk_id IS NULL""")["n"]
            if unmanaged:
                raise IngestionError("law_chunks 存在未接管的旧数据；MVP 请使用独立库/schema，禁止自动覆盖。")
            self.execute("""DELETE FROM law_chunks WHERE EXISTS (
                SELECT 1 FROM mr_active_chunk_map m WHERE law_chunks.law_name=m.law_name
                AND law_chunks.article_no=m.article_no AND law_chunks.seq=m.seq)""").close()
            self.execute("DELETE FROM mr_active_chunk_map").close()
            now_expression = "now()" if self.postgres else ":now"
            params = {"v": version}
            if not self.postgres:
                params["now"] = utc_now()
            self.execute("""INSERT INTO law_chunks(law_name,chapter,article_no,seq,content,token_len,embedding,updated_at)
                SELECT c.law_name,c.chapter,c.article_no,c.seq,c.content,length(c.content),c.embedding,""" +
                now_expression + """ FROM mr_chunks c JOIN mr_kb_documents d
                ON c.doc_version_id=d.doc_version_id WHERE d.kb_version=:v""", params).close()
            self.execute("""INSERT INTO mr_active_chunk_map(law_name,article_no,seq,chunk_id,kb_version)
                SELECT c.law_name,c.article_no,c.seq,c.chunk_id,:v FROM mr_chunks c JOIN mr_kb_documents d
                ON c.doc_version_id=d.doc_version_id WHERE d.kb_version=:v""", {"v": version}).close()
            self.execute("UPDATE mr_kb_versions SET status='ARCHIVED' WHERE status='ACTIVE'").close()
            self.execute("UPDATE mr_kb_versions SET status='ACTIVE' WHERE kb_version=:v", {"v": version}).close()
            self.execute("""INSERT INTO mr_active(singleton,kb_version) VALUES(1,:v)
                ON CONFLICT(singleton) DO UPDATE SET kb_version=excluded.kb_version""", {"v": version}).close()
            self.execute("""INSERT INTO mr_release_history(event_id,from_version,to_version,action,created_at)
                VALUES (:id,:f,:t,:a,:now)""", {"id": uuid4().hex, "f": active, "t": version,
                "a": "rollback" if rollback else "publish", "now": utc_now()}).close()

    def list_versions(self) -> list[dict]:
        return self.all("SELECT * FROM mr_kb_versions ORDER BY created_at")

    def close(self):
        self.connection.close()

