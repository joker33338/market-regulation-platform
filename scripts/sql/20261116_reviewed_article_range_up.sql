-- 仅在明确批准的目标库执行；不修改原始OCR、已有记录或ACTIVE。
BEGIN;
SET LOCAL lock_timeout='5s';
CREATE OR REPLACE FUNCTION business_library.check_article() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM business_library.records r
  JOIN document_review.documents p USING(parse_id)
  JOIN public.mr_document_versions d ON d.doc_version_id=r.doc_version_id
  WHERE r.doc_version_id=NEW.doc_version_id AND (
   (NOT (d.metadata::jsonb ? 'reviewed_text') AND NEW.raw_end<=char_length(p.raw_text))
   OR (
    jsonb_typeof(d.metadata::jsonb->'reviewed_text')='string'
    AND jsonb_typeof(d.metadata::jsonb->'reviewed_page_revisions')='array'
    AND jsonb_array_length(d.metadata::jsonb->'reviewed_page_revisions')>0
    AND nullif(d.metadata::jsonb->'api_review_reference'->>'revision_id','') IS NOT NULL
    AND NEW.raw_end<=char_length(d.metadata::jsonb->>'reviewed_text')
   )
  )
 ) THEN
  RAISE EXCEPTION 'library_text_range_invalid' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
COMMENT ON FUNCTION business_library.check_article() IS 'business_library_reviewed_ranges_v1';
COMMIT;
