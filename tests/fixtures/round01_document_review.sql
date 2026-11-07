-- 仅供新建的QA专用容器使用。列类型/主键经现有库只读元数据核对；
-- 外键为本测试夹具的约束，不代表对业务库执行或要求迁移。
CREATE EXTENSION IF NOT EXISTS vector;
ALTER DATABASE qa_round01 SET qa.round01_isolated = 'test-only';
CREATE SCHEMA document_review;
CREATE TABLE document_review.documents (
 parse_id text PRIMARY KEY, document_id text NOT NULL, report_sha256 text NOT NULL,
 file_name text NOT NULL, file_type text NOT NULL, parsing_status text NOT NULL,
 requires_review boolean NOT NULL, source_location jsonb NOT NULL, quality jsonb NOT NULL,
 raw_text text NOT NULL, markdown_content text NOT NULL, original_result jsonb NOT NULL,
 imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE document_review.pages (
 parse_id text NOT NULL REFERENCES document_review.documents(parse_id), page_number integer NOT NULL,
 parsing_method text NOT NULL, parsing_status text NOT NULL, raw_text text NOT NULL,
 normalized_text text NOT NULL, markdown_content text NOT NULL, confidence double precision,
 warnings jsonb NOT NULL, source_location jsonb NOT NULL, raw_result jsonb NOT NULL,
 processing_seconds double precision NOT NULL, PRIMARY KEY(parse_id,page_number)
);
CREATE TABLE document_review.blocks (
 parse_id text NOT NULL, page_number integer NOT NULL, block_index integer NOT NULL,
 source_block_id text NOT NULL, kind text NOT NULL, raw_text text NOT NULL, bbox jsonb,
 confidence double precision, reading_order integer NOT NULL, source_location jsonb NOT NULL,
 PRIMARY KEY(parse_id,page_number,block_index),
 FOREIGN KEY(parse_id,page_number) REFERENCES document_review.pages(parse_id,page_number)
);
CREATE TABLE document_review.tables (
 parse_id text NOT NULL, page_number integer NOT NULL, table_index integer NOT NULL,
 source_table_id text NOT NULL, html text NOT NULL, markdown text NOT NULL, table_rows jsonb NOT NULL,
 row_count integer NOT NULL, column_count integer NOT NULL, bbox jsonb, source_location jsonb NOT NULL,
 warnings jsonb NOT NULL, PRIMARY KEY(parse_id,page_number,table_index),
 FOREIGN KEY(parse_id,page_number) REFERENCES document_review.pages(parse_id,page_number)
);
CREATE TABLE document_review.cells (
 parse_id text NOT NULL, page_number integer NOT NULL, table_index integer NOT NULL,
 cell_index integer NOT NULL, row_index integer NOT NULL, column_index integer NOT NULL,
 row_span integer NOT NULL, column_span integer NOT NULL, cell_text text NOT NULL,
 is_header boolean NOT NULL, bbox jsonb, source_location jsonb NOT NULL, original_cell jsonb NOT NULL,
 PRIMARY KEY(parse_id,page_number,table_index,cell_index),
 FOREIGN KEY(parse_id,page_number,table_index) REFERENCES document_review.tables(parse_id,page_number,table_index)
);
