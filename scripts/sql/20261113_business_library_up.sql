-- 增量结构：经用户批准并完成备份验证后执行；不回填、不触碰原表及 ACTIVE。
BEGIN;
SET LOCAL lock_timeout='5s';
CREATE SCHEMA business_library;
CREATE TABLE business_library.records (
 doc_version_id text PRIMARY KEY REFERENCES public.mr_document_versions(doc_version_id),
 kind text NOT NULL CHECK(kind IN ('law','case')),
 owner_id text NOT NULL CHECK(length(owner_id)>0),
 parse_id text NOT NULL REFERENCES document_review.documents(parse_id),
 source_file_id text NOT NULL CHECK(length(source_file_id)>0),
 title text NOT NULL CHECK(length(title)>0),
 number text, category text, authority text, published_on date, effective_on date, repealed_on date,
 effective_status text, facts_source text NOT NULL CHECK(length(facts_source)>0),
 verification_status text NOT NULL DEFAULT 'pending' CHECK(verification_status IN ('pending','verified','rejected')),
 verified_by text, verified_at timestamptz,
 CHECK(verification_status<>'verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)),
 UNIQUE(doc_version_id,kind)
);
CREATE INDEX library_records_scope_idx ON business_library.records(owner_id,kind,title,doc_version_id);
CREATE INDEX library_records_parse_idx ON business_library.records(parse_id);
CREATE TABLE business_library.chapters (
 chapter_id text PRIMARY KEY, doc_version_id text NOT NULL,
 kind text NOT NULL DEFAULT 'law' CHECK(kind='law'),
 number text NOT NULL, title text, ordinal integer NOT NULL CHECK(ordinal>=0),
 FOREIGN KEY(doc_version_id,kind) REFERENCES business_library.records(doc_version_id,kind),
 UNIQUE(doc_version_id,ordinal), UNIQUE(chapter_id,doc_version_id)
);
CREATE TABLE business_library.articles (
 article_id text PRIMARY KEY, doc_version_id text NOT NULL,
 kind text NOT NULL DEFAULT 'law' CHECK(kind='law'), chapter_id text,
 number text NOT NULL, title text, ordinal integer NOT NULL CHECK(ordinal>=0),
 raw_start integer NOT NULL CHECK(raw_start>=0), raw_end integer NOT NULL CHECK(raw_end>raw_start),
 page_start integer CHECK(page_start>0), page_end integer CHECK(page_end>=page_start),
 facts_source text NOT NULL CHECK(length(facts_source)>0),
 FOREIGN KEY(doc_version_id,kind) REFERENCES business_library.records(doc_version_id,kind),
 FOREIGN KEY(chapter_id,doc_version_id) REFERENCES business_library.chapters(chapter_id,doc_version_id),
 UNIQUE(doc_version_id,ordinal), UNIQUE(doc_version_id,number), UNIQUE(article_id,doc_version_id)
);
CREATE TABLE business_library.article_chunks (
 article_id text NOT NULL, doc_version_id text NOT NULL,
 chunk_id text NOT NULL REFERENCES public.mr_chunks(chunk_id),
 PRIMARY KEY(article_id,chunk_id),
 FOREIGN KEY(article_id,doc_version_id) REFERENCES business_library.articles(article_id,doc_version_id)
);
CREATE INDEX library_article_chunks_chunk_idx ON business_library.article_chunks(chunk_id);
CREATE TABLE business_library.case_profiles (
 doc_version_id text PRIMARY KEY, kind text NOT NULL DEFAULT 'case' CHECK(kind='case'),
 region text, violation text, facts text, investigation text, evidence_summary text,
 penalty_type text, penalty_amount numeric(20,2) CHECK(penalty_amount>=0), penalty_result text,
 field_sources jsonb NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(field_sources)='object'),
 FOREIGN KEY(doc_version_id,kind) REFERENCES business_library.records(doc_version_id,kind)
);
CREATE TABLE business_library.case_law_references (
 reference_id text PRIMARY KEY, case_version_id text NOT NULL,
 case_kind text NOT NULL DEFAULT 'case' CHECK(case_kind='case'),
 law_version_id text NOT NULL, law_kind text NOT NULL DEFAULT 'law' CHECK(law_kind='law'),
 article_id text, citation text NOT NULL, source text NOT NULL, method text NOT NULL,
 verification_status text NOT NULL DEFAULT 'pending' CHECK(verification_status IN ('pending','verified','rejected')),
 verified_by text, verified_at timestamptz,
 FOREIGN KEY(case_version_id,case_kind) REFERENCES business_library.records(doc_version_id,kind),
 FOREIGN KEY(law_version_id,law_kind) REFERENCES business_library.records(doc_version_id,kind),
 FOREIGN KEY(article_id,law_version_id) REFERENCES business_library.articles(article_id,doc_version_id),
 CHECK(verification_status<>'verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL))
);
CREATE INDEX library_case_law_target_idx ON business_library.case_law_references(law_version_id,article_id);
CREATE INDEX library_case_law_source_idx ON business_library.case_law_references(case_version_id);
-- 跨表来源校验：不允许给其他 owner、文件或文档版本挂错正文。
CREATE FUNCTION business_library.check_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM document_review.documents p JOIN public.mr_document_versions d
 ON d.doc_version_id=NEW.doc_version_id AND d.source_hash=p.document_id
 WHERE p.parse_id=NEW.parse_id AND p.source_location->>'owner_id'=NEW.owner_id
 AND p.source_location->>'source_file_id'=NEW.source_file_id) THEN
 RAISE EXCEPTION 'library_source_mismatch' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER library_record_source BEFORE INSERT OR UPDATE ON business_library.records
 FOR EACH ROW EXECUTE FUNCTION business_library.check_record();
CREATE FUNCTION business_library.check_article() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM business_library.records r JOIN document_review.documents p USING(parse_id)
 WHERE r.doc_version_id=NEW.doc_version_id AND NEW.raw_end<=char_length(p.raw_text)) THEN
 RAISE EXCEPTION 'library_text_range_invalid' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER library_article_range BEFORE INSERT OR UPDATE ON business_library.articles
 FOR EACH ROW EXECUTE FUNCTION business_library.check_article();
CREATE FUNCTION business_library.check_chunk() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.mr_chunks WHERE chunk_id=NEW.chunk_id AND doc_version_id=NEW.doc_version_id) THEN
 RAISE EXCEPTION 'library_chunk_version_mismatch' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER library_chunk_version BEFORE INSERT OR UPDATE ON business_library.article_chunks
 FOR EACH ROW EXECUTE FUNCTION business_library.check_chunk();
-- 不自动授予现有账号任何新写权限；只读 API 账号需单独批准 USAGE/SELECT。
COMMIT;
