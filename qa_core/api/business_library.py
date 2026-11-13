"""法规与案例只读目录；正文引用既有解析记录，发布状态及人员范围双重过滤。"""
from contextlib import contextmanager
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from qa_core.document_parsing.mineru_client import MinerUError
from .common import guarded
from .read_store import ReviewReader


class LibraryRecord(BaseModel):
    doc_version_id: str
    kind: Literal['law','case']
    owner_id: str
    title: str
    number: str | None = None
    category: str | None = None
    authority: str | None = None
    published_on: str | None = None
    effective_on: str | None = None
    repealed_on: str | None = None
    effective_status: str | None = None
    verification_status: str
    document_id: str
    source_file_id: str
    parse_id: str
    kb_version: str


class LibraryList(BaseModel):
    status: Literal['ready','unpublished']
    kb_version: str | None
    list: list[LibraryRecord]
    total: int
    page: int
    page_size: int


class LibraryDetail(BaseModel):
    record: LibraryRecord
    original_text: str
    original_file_name: str
    text_status: Literal['ocr_not_manually_verified'] = 'ocr_not_manually_verified'
    structured: dict | None = None
    source_url: str


class LibraryParts(BaseModel):
    list: list[dict]
    total: int
    page: int
    page_size: int


class LibraryStore(ReviewReader):
    @contextmanager
    def selected(self, requested=None):
        with self.cursor() as cursor:
            if requested is None:
                cursor.execute('SELECT kb_version FROM public.mr_active WHERE singleton=1')
                active = cursor.fetchone()
                version = active['kb_version'] if active else None
            else:
                version = requested
            if version:
                cursor.execute("""SELECT 1 FROM public.mr_kb_versions v WHERE kb_version=%s
                    AND status IN ('ACTIVE','ARCHIVED') AND EXISTS(SELECT 1 FROM public.mr_release_history
                    WHERE to_version=v.kb_version AND action IN ('publish','rollback'))""",(version,))
                if not cursor.fetchone():
                    raise MinerUError('library_version_not_found',404)
                cursor.execute("SELECT to_regclass('business_library.records') AS relation")
                if cursor.fetchone()['relation'] is None:
                    raise MinerUError('library_schema_not_installed',503)
            yield cursor, version

    @staticmethod
    def scope(identity, alias='r'):
        if identity.is_admin:
            return 'TRUE', []
        return alias+'.owner_id=ANY(%s)',[list(identity.read_owners)]

    @staticmethod
    def fields():
        return '''r.doc_version_id,r.kind,r.owner_id,r.title,r.number,r.category,r.authority,
        r.published_on::text,r.effective_on::text,r.repealed_on::text,r.effective_status,
        r.verification_status,d.doc_id AS document_id,r.source_file_id,r.parse_id,k.kb_version'''

    @staticmethod
    def joins():
        return ''' FROM business_library.records r JOIN public.mr_document_versions d USING(doc_version_id)
        JOIN public.mr_kb_documents k USING(doc_version_id)'''

    def listing(self,identity,kind,page,size,query=None,violation=None,version=None):
        with self.selected(version) as (c,version):
            if not version:
                return dict(status='unpublished',kb_version=None,list=[],total=0,page=page,page_size=size)
            scope,args=self.scope(identity)
            where=' WHERE k.kb_version=%s AND r.kind=%s AND '+scope
            args=[version,kind,*args]
            if query:
                where+=' AND strpos(lower(r.title),lower(%s))>0'
                args.append(query)
            if violation:
                where+=' AND EXISTS(SELECT 1 FROM business_library.case_profiles cp WHERE cp.doc_version_id=r.doc_version_id AND strpos(lower(cp.violation),lower(%s))>0)'
                args.append(violation)
            c.execute('SELECT count(*) AS total'+self.joins()+where,args)
            total=c.fetchone()['total']
            c.execute('SELECT '+self.fields()+self.joins()+where+' ORDER BY r.title,r.doc_version_id LIMIT %s OFFSET %s',[*args,size,(page-1)*size])
            return dict(status='ready',kb_version=version,list=[dict(x) for x in c.fetchall()],total=total,page=page,page_size=size)

    def record(self,c,identity,kind,id,version):
        scope,args=self.scope(identity)
        c.execute('SELECT '+self.fields()+self.joins()+
                  ' WHERE k.kb_version=%s AND r.kind=%s AND r.doc_version_id=%s AND '+scope,
                  [version,kind,id,*args])
        row=c.fetchone()
        if not row:
            raise MinerUError('library_record_not_found',404)
        return dict(row)

    def detail(self,identity,kind,id,version=None,part=None,article=None,page=1,size=20):
        with self.selected(version) as (c,version):
            if not version:
                raise MinerUError('library_record_not_found',404)
            row=self.record(c,identity,kind,id,version)
            if part:
                if part=='references':
                    scope,args=self.scope(identity,'target')
                    sql=''' FROM business_library.case_law_references x
                    JOIN business_library.records target ON target.doc_version_id=x.law_version_id
                    JOIN public.mr_kb_documents k ON k.doc_version_id=x.law_version_id
                    WHERE x.case_version_id=%s AND k.kb_version=%s AND '''+scope
                    args=[id,version,*args]
                    fields='x.reference_id,x.law_version_id,x.article_id,x.citation,x.source,x.method,x.verification_status'
                    order='x.reference_id'
                elif part=='articles':
                    sql=' FROM business_library.articles x WHERE x.doc_version_id=%s'
                    args=[id]
                    fields='x.article_id,x.chapter_id,x.number,x.title,x.ordinal'
                    order='x.ordinal,x.article_id'
                else:
                    sql=' FROM business_library.chapters x WHERE x.doc_version_id=%s'
                    args=[id]
                    fields='x.chapter_id,x.number,x.title,x.ordinal'
                    order='x.ordinal,x.chapter_id'
                c.execute('SELECT count(*) AS total'+sql,args)
                total=c.fetchone()['total']
                c.execute('SELECT '+fields+sql+' ORDER BY '+order+' LIMIT %s OFFSET %s',[*args,size,(page-1)*size])
                return dict(list=[dict(x) for x in c.fetchall()],total=total,page=page,page_size=size)
            c.execute('SELECT raw_text,file_name FROM document_review.documents WHERE parse_id=%s',(row['parse_id'],))
            original=c.fetchone()
            text=original['raw_text']
            structured=None
            if article:
                c.execute('''SELECT article_id,chapter_id,number,title,ordinal,raw_start,raw_end,page_start,page_end
                    FROM business_library.articles WHERE article_id=%s AND doc_version_id=%s''',(article,id))
                value=c.fetchone()
                if not value:
                    raise MinerUError('library_article_not_found',404)
                structured=dict(value)
                text=text[value['raw_start']:value['raw_end']]
                c.execute('SELECT chunk_id FROM business_library.article_chunks WHERE article_id=%s ORDER BY chunk_id',(article,))
                structured['chunk_ids']=[x['chunk_id'] for x in c.fetchall()]
            elif kind=='case':
                c.execute('''SELECT region,violation,facts,investigation,evidence_summary,penalty_type,
                    penalty_amount::text,penalty_result,field_sources FROM business_library.case_profiles
                    WHERE doc_version_id=%s''',(id,))
                value=c.fetchone()
                structured=dict(value) if value else None
            return dict(record=row,original_text=text,original_file_name=original['file_name'],structured=structured,
                        source_url='/api/parse/files/'+row['source_file_id']+'/source')


def register_business_library(app,principal,reader):
    router=APIRouter(tags=['business-library'])

    def store():
        if not reader.kb_dsn:
            raise MinerUError('knowledge_database_not_configured',503)
        return LibraryStore(reader.kb_dsn)

    def register(kind,path):
        @router.get(path,response_model=LibraryList,name=kind+'_library_list')
        @guarded
        def listing(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
                    query:str|None=Query(None,max_length=200),violation:str|None=Query(None,max_length=200),
                    kb_version:str|None=Query(None,min_length=1,max_length=128),identity=Depends(principal)):
            if kind=='law' and violation is not None:
                raise MinerUError('violation_filter_case_only',422)
            return store().listing(identity,kind,page,page_size,query,violation,kb_version)

        @router.get(path+'/{doc_version_id}',response_model=LibraryDetail,name=kind+'_library_detail')
        @guarded
        def detail(doc_version_id:str,kb_version:str|None=Query(None,min_length=1,max_length=128),identity=Depends(principal)):
            return store().detail(identity,kind,doc_version_id,kb_version)

    register('law','/api/library/laws')
    register('case','/api/library/cases')

    @router.get('/api/library/laws/{doc_version_id}/chapters',response_model=LibraryParts)
    @guarded
    def chapters(doc_version_id:str,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
                 kb_version:str|None=Query(None,min_length=1,max_length=128),identity=Depends(principal)):
        return store().detail(identity,'law',doc_version_id,kb_version,part='chapters',page=page,size=page_size)

    @router.get('/api/library/laws/{doc_version_id}/articles/{article_id}',response_model=LibraryDetail)
    @guarded
    def article(doc_version_id:str,article_id:str,kb_version:str|None=Query(None,min_length=1,max_length=128),identity=Depends(principal)):
        return store().detail(identity,'law',doc_version_id,kb_version,article=article_id)

    @router.get('/api/library/laws/{doc_version_id}/articles',response_model=LibraryParts)
    @guarded
    def articles(doc_version_id:str,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
                 kb_version:str|None=Query(None,min_length=1,max_length=128),identity=Depends(principal)):
        return store().detail(identity,'law',doc_version_id,kb_version,part='articles',page=page,size=page_size)

    @router.get('/api/library/cases/{doc_version_id}/references',response_model=LibraryParts)
    @guarded
    def references(doc_version_id:str,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
                   kb_version:str|None=Query(None,min_length=1,max_length=128),identity=Depends(principal)):
        return store().detail(identity,'case',doc_version_id,kb_version,part='references',page=page,size=page_size)

    app.include_router(router)
