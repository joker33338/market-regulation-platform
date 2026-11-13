-- 仅在本次新增表全部为空时允许回退；有数据时拒绝，避免丢失核验成果。
BEGIN;
SET LOCAL lock_timeout='5s';
DO $$
BEGIN
 IF EXISTS(SELECT 1 FROM business_library.records) THEN
 RAISE EXCEPTION 'library_not_empty_preserve_data'; END IF;
END $$;
DROP TABLE business_library.case_law_references;
DROP TABLE business_library.case_profiles;
DROP TABLE business_library.article_chunks;
DROP TABLE business_library.articles;
DROP TABLE business_library.chapters;
DROP TABLE business_library.records;
DROP FUNCTION business_library.check_record();
DROP FUNCTION business_library.check_article();
DROP FUNCTION business_library.check_chunk();
DROP SCHEMA business_library;
COMMIT;
