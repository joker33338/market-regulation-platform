-- 只有不存在依赖扩展来源绑定的目录时才回退，不删除任何记录。
BEGIN;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM business_library.records r JOIN public.mr_document_versions d USING(doc_version_id)
 JOIN document_review.documents p USING(parse_id) WHERE d.source_hash<>p.document_id) THEN
 RAISE EXCEPTION 'published_library_sources_need_v2'; END IF;
END $$;
CREATE OR REPLACE FUNCTION business_library.check_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM document_review.documents p JOIN public.mr_document_versions d
 ON d.doc_version_id=NEW.doc_version_id AND d.source_hash=p.document_id
 WHERE p.parse_id=NEW.parse_id AND p.source_location->>'owner_id'=NEW.owner_id
 AND p.source_location->>'source_file_id'=NEW.source_file_id) THEN
 RAISE EXCEPTION 'library_source_mismatch' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
COMMENT ON FUNCTION business_library.check_record() IS NULL;
COMMIT;
