-- 回退仅恢复原范围校验函数；不删除审核正文、条款、版本或历史数据。
BEGIN;
SET LOCAL lock_timeout='5s';
CREATE OR REPLACE FUNCTION business_library.check_article() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM business_library.records r JOIN document_review.documents p USING(parse_id)
 WHERE r.doc_version_id=NEW.doc_version_id AND NEW.raw_end<=char_length(p.raw_text)) THEN
 RAISE EXCEPTION 'library_text_range_invalid' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
COMMENT ON FUNCTION business_library.check_article() IS NULL;
COMMIT;
