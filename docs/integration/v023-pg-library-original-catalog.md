# v0.2.3 PostgreSQL 原结构目录核查

2026-11-13 从目标数据库 information_schema / pg_catalog 只读采集；不包含业务正文、源文件名称或凭据。此文件记录升级前原表。

## document_review.blocks

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| parse_id | text | NO |
| page_number | integer | NO |
| block_index | integer | NO |
| source_block_id | text | NO |
| kind | text | NO |
| raw_text | text | NO |
| bbox | jsonb | YES |
| confidence | double precision | YES |
| reading_order | integer | NO |
| source_location | jsonb | NO |

约束：

- `blocks_parse_id_page_number_fkey`：`FOREIGN KEY (parse_id, page_number) REFERENCES document_review.pages(parse_id, page_number)`
- `blocks_pkey`：`PRIMARY KEY (parse_id, page_number, block_index)`

索引：

- `blocks_pkey`：`CREATE UNIQUE INDEX blocks_pkey ON document_review.blocks USING btree (parse_id, page_number, block_index)`
- `document_review_blocks_kind_idx`：`CREATE INDEX document_review_blocks_kind_idx ON document_review.blocks USING btree (kind)`

## document_review.cells

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| parse_id | text | NO |
| page_number | integer | NO |
| table_index | integer | NO |
| cell_index | integer | NO |
| row_index | integer | NO |
| column_index | integer | NO |
| row_span | integer | NO |
| column_span | integer | NO |
| cell_text | text | NO |
| is_header | boolean | NO |
| bbox | jsonb | YES |
| source_location | jsonb | NO |
| original_cell | jsonb | NO |

约束：

- `cells_parse_id_page_number_table_index_fkey`：`FOREIGN KEY (parse_id, page_number, table_index) REFERENCES document_review.tables(parse_id, page_number, table_index)`
- `cells_pkey`：`PRIMARY KEY (parse_id, page_number, table_index, cell_index)`

索引：

- `cells_pkey`：`CREATE UNIQUE INDEX cells_pkey ON document_review.cells USING btree (parse_id, page_number, table_index, cell_index)`

## document_review.documents

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| parse_id | text | NO |
| document_id | text | NO |
| report_sha256 | text | NO |
| file_name | text | NO |
| file_type | text | NO |
| parsing_status | text | NO |
| requires_review | boolean | NO |
| source_location | jsonb | NO |
| quality | jsonb | NO |
| raw_text | text | NO |
| markdown_content | text | NO |
| original_result | jsonb | NO |
| imported_at | timestamp with time zone | NO |

约束：

- `documents_pkey`：`PRIMARY KEY (parse_id)`

索引：

- `document_review_documents_source_idx`：`CREATE INDEX document_review_documents_source_idx ON document_review.documents USING btree (document_id)`
- `documents_pkey`：`CREATE UNIQUE INDEX documents_pkey ON document_review.documents USING btree (parse_id)`

## document_review.findings

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| parse_id | text | NO |
| finding_index | integer | NO |
| page_number | integer | YES |
| code | text | NO |
| severity | text | NO |
| message | text | NO |
| review_status | text | NO |
| details | jsonb | NO |

约束：

- `findings_parse_id_fkey`：`FOREIGN KEY (parse_id) REFERENCES document_review.documents(parse_id)`
- `findings_pkey`：`PRIMARY KEY (parse_id, finding_index)`

索引：

- `findings_pkey`：`CREATE UNIQUE INDEX findings_pkey ON document_review.findings USING btree (parse_id, finding_index)`

## document_review.images

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| parse_id | text | NO |
| page_number | integer | NO |
| image_index | integer | NO |
| relative_path | text | NO |
| sha256 | text | NO |
| byte_size | bigint | NO |
| mime_type | text | NO |
| bbox | jsonb | YES |
| metadata | jsonb | NO |
| image_data | bytea | NO |

约束：

- `images_parse_id_page_number_fkey`：`FOREIGN KEY (parse_id, page_number) REFERENCES document_review.pages(parse_id, page_number)`
- `images_pkey`：`PRIMARY KEY (parse_id, page_number, image_index)`

索引：

- `images_pkey`：`CREATE UNIQUE INDEX images_pkey ON document_review.images USING btree (parse_id, page_number, image_index)`

## document_review.pages

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| parse_id | text | NO |
| page_number | integer | NO |
| parsing_method | text | NO |
| parsing_status | text | NO |
| raw_text | text | NO |
| normalized_text | text | NO |
| markdown_content | text | NO |
| confidence | double precision | YES |
| warnings | jsonb | NO |
| source_location | jsonb | NO |
| raw_result | jsonb | NO |
| processing_seconds | double precision | NO |

约束：

- `pages_page_number_check`：`CHECK ((page_number > 0))`
- `pages_parse_id_fkey`：`FOREIGN KEY (parse_id) REFERENCES document_review.documents(parse_id)`
- `pages_pkey`：`PRIMARY KEY (parse_id, page_number)`

索引：

- `pages_pkey`：`CREATE UNIQUE INDEX pages_pkey ON document_review.pages USING btree (parse_id, page_number)`

## document_review.tables

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| parse_id | text | NO |
| page_number | integer | NO |
| table_index | integer | NO |
| source_table_id | text | NO |
| html | text | NO |
| markdown | text | NO |
| table_rows | jsonb | NO |
| row_count | integer | NO |
| column_count | integer | NO |
| bbox | jsonb | YES |
| source_location | jsonb | NO |
| warnings | jsonb | NO |

约束：

- `tables_parse_id_page_number_fkey`：`FOREIGN KEY (parse_id, page_number) REFERENCES document_review.pages(parse_id, page_number)`
- `tables_pkey`：`PRIMARY KEY (parse_id, page_number, table_index)`

索引：

- `tables_pkey`：`CREATE UNIQUE INDEX tables_pkey ON document_review.tables USING btree (parse_id, page_number, table_index)`

## document_review.v_document_summary

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| parse_id | text | YES |
| file_name | text | YES |
| source_sha256 | text | YES |
| parsing_status | text | YES |
| requires_review | boolean | YES |
| imported_at | timestamp with time zone | YES |
| pages | bigint | YES |
| blocks | bigint | YES |
| tables | bigint | YES |
| cells | bigint | YES |
| images | bigint | YES |
| findings | bigint | YES |

约束：


索引：


## document_review.v_page_text

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| file_name | text | YES |
| parse_id | text | YES |
| page_number | integer | YES |
| parsing_method | text | YES |
| parsing_status | text | YES |
| raw_text | text | YES |
| normalized_text | text | YES |
| markdown_content | text | YES |
| confidence | double precision | YES |
| warnings | jsonb | YES |
| source_location | jsonb | YES |
| raw_result | jsonb | YES |
| processing_seconds | double precision | YES |

约束：


索引：


## document_review.v_review_queue

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| file_name | text | YES |
| parse_id | text | YES |
| finding_index | integer | YES |
| page_number | integer | YES |
| code | text | YES |
| severity | text | YES |
| message | text | YES |
| review_status | text | YES |
| details | jsonb | YES |

约束：


索引：


## document_review.v_table_cells

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| file_name | text | YES |
| parse_id | text | YES |
| page_number | integer | YES |
| table_index | integer | YES |
| cell_index | integer | YES |
| row_index | integer | YES |
| column_index | integer | YES |
| row_span | integer | YES |
| column_span | integer | YES |
| cell_text | text | YES |
| is_header | boolean | YES |
| bbox | jsonb | YES |
| source_location | jsonb | YES |
| original_cell | jsonb | YES |

约束：


索引：


## public.law_chunks

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| id | bigint | NO |
| law_name | text | NO |
| chapter | text | YES |
| article_no | text | NO |
| seq | integer | NO |
| content | text | NO |
| token_len | integer | YES |
| embedding | USER-DEFINED | NO |
| updated_at | timestamp with time zone | NO |

约束：

- `law_chunks_law_name_article_no_seq_key`：`UNIQUE (law_name, article_no, seq)`
- `law_chunks_pkey`：`PRIMARY KEY (id)`

索引：

- `law_chunks_article_idx`：`CREATE INDEX law_chunks_article_idx ON public.law_chunks USING btree (law_name, article_no)`
- `law_chunks_hnsw_idx`：`CREATE INDEX law_chunks_hnsw_idx ON public.law_chunks USING hnsw (embedding vector_cosine_ops)`
- `law_chunks_law_name_article_no_seq_key`：`CREATE UNIQUE INDEX law_chunks_law_name_article_no_seq_key ON public.law_chunks USING btree (law_name, article_no, seq)`
- `law_chunks_name_idx`：`CREATE INDEX law_chunks_name_idx ON public.law_chunks USING btree (law_name)`
- `law_chunks_pkey`：`CREATE UNIQUE INDEX law_chunks_pkey ON public.law_chunks USING btree (id)`

## public.mr_active

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| singleton | integer | NO |
| kb_version | text | NO |

约束：

- `mr_active_pkey`：`PRIMARY KEY (singleton)`
- `mr_active_singleton_check`：`CHECK ((singleton = 1))`

索引：

- `mr_active_pkey`：`CREATE UNIQUE INDEX mr_active_pkey ON public.mr_active USING btree (singleton)`

## public.mr_active_chunk_map

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| law_name | text | NO |
| article_no | text | NO |
| seq | integer | NO |
| chunk_id | text | NO |
| kb_version | text | NO |

约束：

- `mr_active_chunk_map_chunk_id_fkey`：`FOREIGN KEY (chunk_id) REFERENCES mr_chunks(chunk_id)`
- `mr_active_chunk_map_pkey`：`PRIMARY KEY (law_name, article_no, seq)`

索引：

- `mr_active_chunk_map_pkey`：`CREATE UNIQUE INDEX mr_active_chunk_map_pkey ON public.mr_active_chunk_map USING btree (law_name, article_no, seq)`

## public.mr_chunks

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| chunk_id | text | NO |
| doc_version_id | text | NO |
| law_name | text | NO |
| chapter | text | NO |
| article_no | text | NO |
| seq | integer | NO |
| content | text | NO |
| embedding_text | text | NO |
| input_hash | text | NO |
| metadata | text | NO |
| embedding | USER-DEFINED | NO |

约束：

- `mr_chunks_doc_version_id_fkey`：`FOREIGN KEY (doc_version_id) REFERENCES mr_document_versions(doc_version_id)`
- `mr_chunks_pkey`：`PRIMARY KEY (chunk_id)`

索引：

- `mr_chunks_document_idx`：`CREATE INDEX mr_chunks_document_idx ON public.mr_chunks USING btree (doc_version_id)`
- `mr_chunks_input_hash_idx`：`CREATE INDEX mr_chunks_input_hash_idx ON public.mr_chunks USING btree (input_hash)`
- `mr_chunks_pkey`：`CREATE UNIQUE INDEX mr_chunks_pkey ON public.mr_chunks USING btree (chunk_id)`

## public.mr_document_versions

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| doc_version_id | text | NO |
| doc_id | text | NO |
| source_hash | text | NO |
| law_name | text | NO |
| metadata | text | NO |
| chunk_count | integer | NO |

约束：

- `mr_document_versions_pkey`：`PRIMARY KEY (doc_version_id)`

索引：

- `mr_document_versions_pkey`：`CREATE UNIQUE INDEX mr_document_versions_pkey ON public.mr_document_versions USING btree (doc_version_id)`

## public.mr_kb_documents

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| kb_version | text | NO |
| doc_id | text | NO |
| doc_version_id | text | NO |
| source_path | text | NO |

约束：

- `mr_kb_documents_doc_version_id_fkey`：`FOREIGN KEY (doc_version_id) REFERENCES mr_document_versions(doc_version_id)`
- `mr_kb_documents_kb_version_fkey`：`FOREIGN KEY (kb_version) REFERENCES mr_kb_versions(kb_version)`
- `mr_kb_documents_pkey`：`PRIMARY KEY (kb_version, doc_id)`

索引：

- `mr_kb_documents_pkey`：`CREATE UNIQUE INDEX mr_kb_documents_pkey ON public.mr_kb_documents USING btree (kb_version, doc_id)`

## public.mr_kb_versions

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| kb_version | text | NO |
| base_version | text | YES |
| status | text | NO |
| processing_signature | text | NO |
| model_signature | text | NO |
| dimension | integer | NO |
| created_at | text | NO |
| stats | text | NO |

约束：

- `mr_kb_versions_pkey`：`PRIMARY KEY (kb_version)`

索引：

- `mr_kb_versions_pkey`：`CREATE UNIQUE INDEX mr_kb_versions_pkey ON public.mr_kb_versions USING btree (kb_version)`

## public.mr_release_history

| 字段 | 类型 | 允许 NULL |
|---|---|---|
| event_id | text | NO |
| from_version | text | YES |
| to_version | text | NO |
| action | text | NO |
| created_at | text | NO |

约束：

- `mr_release_history_pkey`：`PRIMARY KEY (event_id)`

索引：

- `mr_release_history_pkey`：`CREATE UNIQUE INDEX mr_release_history_pkey ON public.mr_release_history USING btree (event_id)`
