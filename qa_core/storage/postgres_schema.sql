-- 仅在显式 init-db 时执行，不修改既有来源表。
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS law_chunks (
    id BIGSERIAL PRIMARY KEY,
    law_name TEXT NOT NULL,
    chapter TEXT,
    article_no TEXT NOT NULL,
    seq INTEGER NOT NULL DEFAULT 1,
    content TEXT NOT NULL,
    token_len INTEGER,
    embedding vector(1024) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (law_name, article_no, seq)
);
CREATE INDEX IF NOT EXISTS law_chunks_hnsw_idx ON law_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS law_chunks_name_idx ON law_chunks (law_name);
CREATE INDEX IF NOT EXISTS law_chunks_article_idx ON law_chunks (law_name, article_no);

