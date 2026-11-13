-- 仅替换来源一致性函数，不回填、不变更旧记录或ACTIVE。
BEGIN;
SET LOCAL lock_timeout='5s';
CREATE OR REPLACE FUNCTION business_library.check_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM document_review.documents p JOIN public.mr_document_versions d
 ON d.doc_version_id=NEW.doc_version_id
 WHERE p.parse_id=NEW.parse_id AND p.source_location->>'owner_id'=NEW.owner_id
 AND p.source_location->>'source_file_id'=NEW.source_file_id
 AND (d.source_hash=p.document_id OR
      (d.metadata::jsonb->>'file_sha256'=p.document_id
       AND d.metadata::jsonb->'api_review_reference'->>'parse_id'=p.parse_id
       AND d.metadata::jsonb->'api_review_reference'->>'owner_id'=NEW.owner_id))) THEN
 RAISE EXCEPTION 'library_source_mismatch' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
COMMENT ON FUNCTION business_library.check_record() IS 'business_library_source_v2';
COMMIT;
