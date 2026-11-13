"""法规资料接收：保存未索引版本与待复核条款，不建立知识库成员或发布记录。"""
import json
import re

from qa_core.indexing.legal_structure import ARTICLE, HEADING, NUM, parse_articles
from qa_core.indexing.models import SourceLine
from qa_core.utils import IngestionError, stable_hash
from qa_core.document_parsing.mineru_client import MinerUError


def structure_ranges(text):
    """仅使用真实行首条号；不能完整识别或出现合订本重复条号时不创建条款。"""
    lines=text.splitlines(keepends=True)
    try:
        parsed=parse_articles([SourceLine(line.strip(),1,n+1) for n,line in enumerate(lines)])
    except IngestionError:
        return [],[]
    chapters=[];articles=[];headings=[];current=None;offset=0
    for line in lines:
        stripped=line.strip()
        heading=HEADING.fullmatch(stripped)
        if heading:
            headings.append(offset)
            if heading.group(1)=='编':
                current=None
            elif heading.group(1)=='章':
                current=len(chapters)
                number=''.join(re.match(rf'^(第\s*{NUM}\s*章)',stripped).group(1).split())
                chapters.append({'number':number,'title':stripped,'ordinal':current})
        match=ARTICLE.match(stripped)
        if match:
            number=''.join(match.group(1).split())
            articles.append({'number':number,'raw_start':offset+len(line)-len(line.lstrip()),
                             'chapter':current,'ordinal':len(articles)})
        offset+=len(line)
    if [x['number'] for x in articles]!=[x.article_no for x in parsed]:
        return [],[]
    for n,article in enumerate(articles):
        end=articles[n+1]['raw_start'] if n+1<len(articles) else len(text)
        end=min([end,*[h for h in headings if article['raw_start']<h<end]])
        article.update(raw_end=end,page_start=text.count('\f',0,article['raw_start'])+1,
                       page_end=text.count('\f',0,max(article['raw_start'],end-1))+1)
    return chapters,articles


def receive_law(dsn,owner_id,parse_id):
    """显式本机授权作业调用；无公开写路由，永不将接收等同于审核通过。"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    connection=psycopg2.connect(dsn,connect_timeout=5,application_name='law_catalog_intake')
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as c:
                c.execute('''SELECT * FROM document_review.documents WHERE parse_id=%s
                    AND source_location->>'owner_id'=%s FOR SHARE''',(parse_id,owner_id))
                source=c.fetchone()
                if not source:
                    raise MinerUError('document_not_found',404)
                if not source['requires_review'] or source['quality'].get('document_type')!='law':
                    raise MinerUError('law_intake_requires_pending_source',409)
                file_id=source['source_location'].get('source_file_id')
                if not file_id or not source['raw_text'].strip():
                    raise MinerUError('law_intake_source_incomplete',409)
                doc_id=stable_hash('unverified-source-document-v1',source['document_id'])
                version=stable_hash('unindexed-law-version-v1',doc_id,source['report_sha256'])
                metadata={'document_type':'law','owner_id':owner_id,'parse_id':parse_id,
                          'source_file_id':file_id,'processing_status':'INTAKE_NOT_INDEXED',
                          'title_basis':'original_filename_unverified','human_verified':False,
                          'publication_eligible':False}
                c.execute('''INSERT INTO public.mr_document_versions
                    (doc_version_id,doc_id,source_hash,law_name,metadata,chunk_count)
                    VALUES(%s,%s,%s,%s,%s,0) ON CONFLICT(doc_version_id) DO NOTHING''',
                    (version,doc_id,source['document_id'],source['file_name'],json.dumps(metadata)))
                c.execute('''INSERT INTO business_library.records
                    (doc_version_id,kind,owner_id,parse_id,source_file_id,title,facts_source)
                    VALUES(%s,'law',%s,%s,%s,%s,'original_filename_unverified')
                    ON CONFLICT(doc_version_id) DO NOTHING RETURNING doc_version_id''',
                    (version,owner_id,parse_id,file_id,source['file_name']))
                created=c.fetchone() is not None
                if created:
                    # 表格及不完整解析只接收原文，不将其摊平成法律条款。
                    original=source['original_result']
                    pages=original.get('pages',[])
                    blocked=source['parsing_status'] not in ('success','needs_review') or any(
                        p.get('tables') or p.get('parsing_status') not in ('success','needs_review') or
                        p.get('error_type') or p.get('source_location',{}).get('layout_review_required') or
                        p.get('source_location',{}).get('hidden_text_layer') for p in pages)
                    chapters,articles=([],[]) if blocked else structure_ranges(source['raw_text'])
                    for chapter in chapters:
                        chapter['id']=stable_hash('intake-chapter-v1',version,chapter['ordinal'])
                        c.execute('''INSERT INTO business_library.chapters
                            (chapter_id,doc_version_id,number,title,ordinal) VALUES(%s,%s,%s,%s,%s)''',
                            (chapter['id'],version,chapter['number'],chapter['title'],chapter['ordinal']))
                    for article in articles:
                        chapter_id=chapters[article['chapter']]['id'] if article['chapter'] is not None else None
                        c.execute('''INSERT INTO business_library.articles
                            (article_id,doc_version_id,chapter_id,number,ordinal,raw_start,raw_end,page_start,page_end,facts_source)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'parser_text_explicit_article_heading_unverified')''',
                            (stable_hash('intake-article-v1',version,article['number']),version,chapter_id,
                             article['number'],article['ordinal'],article['raw_start'],article['raw_end'],
                             article['page_start'],article['page_end']))
                c.execute('SELECT count(*) AS count FROM business_library.articles WHERE doc_version_id=%s',(version,))
                return {'doc_version_id':version,'document_id':doc_id,'created':created,
                        'articles':c.fetchone()['count'],'status':'INTAKE_NOT_INDEXED','published':False}
    finally:
        connection.close()
