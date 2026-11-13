"""将真实入库候选同步到法规目录；发布可见性仍由原KB版本控制。"""
import json
from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.storage.law_intake import structure_ranges
from qa_core.utils import IngestionError,stable_hash

MARKER='business_library_source_v2'

def ensure_projection_schema(database):
    if not database.postgres:return
    with database.connection.cursor() as c:
        c.execute("SELECT obj_description(to_regprocedure('business_library.check_record()'),'pg_proc') AS marker")
        row=c.fetchone()
    if not row or row['marker']!=MARKER:
        raise MinerUError('library_schema_upgrade_required',503)

def project_library(database,version):
    if not database.postgres:return
    ensure_projection_schema(database)
    with database.transaction():
        with database.connection.cursor() as c:
            c.execute('SELECT d.* FROM public.mr_document_versions d JOIN public.mr_kb_documents k\n                USING(doc_version_id) WHERE k.kb_version=%s',(version,))
            documents=list(c.fetchall())
            for document in documents:
                metadata=json.loads(document['metadata'])
                reference=metadata.get('api_review_reference')
                if not reference:
                    raise IngestionError('候选来源缺少审核绑定，不能同步法规目录')
                owner=reference['owner_id'];parse_id=reference['parse_id']
                c.execute("SELECT * FROM document_review.documents WHERE parse_id=%s AND source_location->>'owner_id'=%s FOR SHARE",(parse_id,owner))
                source=c.fetchone()
                if not source or metadata.get('file_sha256')!=source['document_id']:
                    raise IngestionError('法规目录来源身份不一致')
                file_id=source['source_location'].get('source_file_id')
                if not file_id:raise IngestionError('法规原件身份缺失')
                doc_version=document['doc_version_id']
                c.execute("INSERT INTO business_library.records\n                    (doc_version_id,kind,owner_id,parse_id,source_file_id,title,facts_source)\n                    VALUES(%s,'law',%s,%s,%s,%s,'reviewed_parser_and_explicit_ingestion_title')\n                    ON CONFLICT(doc_version_id) DO NOTHING RETURNING doc_version_id",
                    (doc_version,owner,parse_id,file_id,document['law_name']))
                if not c.fetchone():continue
                # 结构仍标为待核验；批准正文不代表法律元数据及自动条款已逐项核验。
                chapters,articles=structure_ranges(source['raw_text'])
                for chapter in chapters:
                    chapter['id']=stable_hash('published-chapter-v1',doc_version,chapter['ordinal'])
                    c.execute('INSERT INTO business_library.chapters\n                        (chapter_id,doc_version_id,number,title,ordinal) VALUES(%s,%s,%s,%s,%s)',
                        (chapter['id'],doc_version,chapter['number'],chapter['title'],chapter['ordinal']))
                c.execute('SELECT chunk_id,article_no FROM public.mr_chunks WHERE doc_version_id=%s',(doc_version,))
                chunks=list(c.fetchall())
                for article in articles:
                    aid=stable_hash('published-article-v1',doc_version,article['number'])
                    chapter=chapters[article['chapter']]['id'] if article['chapter'] is not None else None
                    c.execute("INSERT INTO business_library.articles\n                        (article_id,doc_version_id,chapter_id,number,ordinal,raw_start,raw_end,page_start,page_end,facts_source)\n                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'reviewed_parser_explicit_heading_unverified')",
                        (aid,doc_version,chapter,article['number'],article['ordinal'],article['raw_start'],article['raw_end'],article['page_start'],article['page_end']))
                    for chunk in chunks:
                        if chunk['article_no']==article['number']:
                            c.execute('INSERT INTO business_library.article_chunks(article_id,doc_version_id,chunk_id) VALUES(%s,%s,%s)',(aid,doc_version,chunk['chunk_id']))
