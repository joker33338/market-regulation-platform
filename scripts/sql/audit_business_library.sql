-- 正式环境仅执行只读事务；只输出目录和聚合值，不输出正文或来源路径。
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='15s';
SELECT json_build_object('database',current_database(),'user',current_user,'version',version(),
 'read_only',current_setting('transaction_read_only'));
SELECT json_agg(x) AS columns FROM (SELECT table_schema,table_name,column_name,data_type,is_nullable
 FROM information_schema.columns WHERE table_schema IN ('public','document_review') ORDER BY 1,2,ordinal_position)x;
SELECT json_agg(x) AS constraints FROM (SELECT n.nspname,c.relname,k.conname,k.contype,pg_get_constraintdef(k.oid) AS definition
 FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname IN ('public','document_review') ORDER BY 1,2,3)x;
SELECT json_agg(x) AS indexes FROM (SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes
 WHERE schemaname IN ('public','document_review') ORDER BY 1,2,3)x;
SELECT json_build_object('parsed_documents',(SELECT count(*) FROM document_review.documents),
 'source_file_linked',(SELECT count(*) FROM document_review.documents WHERE nullif(source_location->>'source_file_id','') IS NOT NULL),
 'owner_linked',(SELECT count(*) FROM document_review.documents WHERE nullif(source_location->>'owner_id','') IS NOT NULL),
 'document_versions',(SELECT count(*) FROM public.mr_document_versions),
 'chunks',(SELECT count(*) FROM public.mr_chunks),'legacy_chunks',(SELECT count(*) FROM public.law_chunks),
 'kb_versions',(SELECT count(*) FROM public.mr_kb_versions),
 'active',(SELECT kb_version FROM public.mr_active WHERE singleton=1));
SELECT json_agg(x) FROM (SELECT coalesce(metadata::jsonb->>'document_type','unknown') AS document_type,
 count(*) AS versions,count(*) FILTER(WHERE nullif(metadata::jsonb->>'issuing_authority','') IS NOT NULL) AS authority_present,
 count(*) FILTER(WHERE nullif(metadata::jsonb->>'effective_status','') IS NOT NULL) AS effect_present
 FROM public.mr_document_versions GROUP BY 1)x;
SELECT json_agg(x) FROM (SELECT coalesce(d.metadata::jsonb->>'document_type','unknown') AS document_type,
 count(*) AS chunks,count(*) FILTER(WHERE nullif(c.chapter,'') IS NOT NULL) AS chapter_chunks,
 count(*) FILTER(WHERE nullif(c.article_no,'') IS NOT NULL) AS article_chunks
 FROM public.mr_chunks c JOIN public.mr_document_versions d USING(doc_version_id) GROUP BY 1)x;
SELECT json_build_object('orphan_chunks',(SELECT count(*) FROM public.mr_chunks c LEFT JOIN public.mr_document_versions d USING(doc_version_id) WHERE d.doc_version_id IS NULL),
 'orphan_kb_documents',(SELECT count(*) FROM public.mr_kb_documents k LEFT JOIN public.mr_document_versions d USING(doc_version_id) WHERE d.doc_version_id IS NULL),
 'duplicate_parse_hash_groups',(SELECT count(*) FROM (SELECT document_id FROM document_review.documents GROUP BY 1 HAVING count(*)>1)x),
 'version_links',(SELECT count(*) FROM public.mr_kb_documents),
 'active_documents',(SELECT count(*) FROM public.mr_kb_documents k JOIN public.mr_active a USING(kb_version)),
 'active_chunks',(SELECT count(*) FROM public.mr_active_chunk_map));
COMMIT;
