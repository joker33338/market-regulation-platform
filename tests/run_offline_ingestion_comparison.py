"""同一固定语料与参数的前后对照；仅在 QA 私密目录写证据。"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

from run_offline_ingestion_qa import QA, verify


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--source-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();source=args.source.resolve();out=args.output.resolve()
    if not source.is_relative_to(QA/'local') or not out.is_relative_to(QA/'local'):
        parser.error('快照和证据必须位于QA私密目录')
    verify(source,args.source_sha);out.mkdir(parents=True,exist_ok=True)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(source))
    from qa_core.indexing.document_loaders import load_file
    from qa_core.indexing.legal_structure import parse_articles
    from qa_core.indexing.chunking import split_articles
    from qa_core.indexing.models import LegalDocument, SourceLine
    from qa_core.indexing.service import prepare_document
    from qa_core.document_parsing.bridge import to_legal_document
    from qa_core.document_parsing.schemas import DocumentResult
    try:
        from qa_core.indexing.preview import preview_chunks
    except ModuleNotFoundError:preview_chunks=None
    corpus=Path(os.environ['MARKET_REGULATION_TEST_CORPUS'])
    legal_root=corpus/'13_离线入库专项'
    truth_path=next(legal_root.rglob('expected_chunks.json'))
    truth=json.loads(truth_path.read_text('utf-8-sig'))
    protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in corpus.rglob('*') if p.is_file()}

    def canonical(chunks):
        parts=[]
        for c in chunks:
            value=c['content'];label=c['article_no']
            if value.startswith(label):value=value[len(label):]
            parts.append(''.join(value.split()))
        return ''.join(parts)

    records=[];prepared={}
    for case in truth['cases']:
        file=legal_root/case['file']
        if not file.exists():
            choices=list(legal_root.rglob(Path(case['file']).name))
            if len(choices)!=1:
                records.append(dict(id=case['case_id'],status='BLOCKED',reason='source unresolved'));continue
            file=choices[0]
        record=dict(id=case['case_id'],expected=case['expected_status'],reference_strategy='delivered pre-optimization boundaries, unchanged')
        try:
            doc=load_file(file,law_name=case['law_name'],law_id=case['law_id'])
            timings=[]
            for _ in range(5):
                started=time.perf_counter()
                _,revision,chunks,metadata=prepare_document(doc,model_signature='QA-SAME-MODEL',max_chars=800)
                timings.append(time.perf_counter()-started)
            data=[asdict(c) for c in chunks];prepared[case['case_id']]=dict(revision=revision,processing_signature=metadata['processing_signature'])
            (out/(case['case_id']+'-chunks.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            groups={}
            for c in data:groups.setdefault(c['metadata']['parent_article_id'],[]).append(c)
            valid_fragment=sum(c['metadata']['fragment_index']==i and c['metadata']['fragment_total']==len(g)
                               for g in groups.values() for i,c in enumerate(g,1))
            parent_ok=sum(c['metadata']['parent_article_id']==__import__('qa_core.utils',fromlist=['stable_hash']).stable_hash(revision,c['article_no']) for c in data)
            record.update(status='ACCEPTED',articles=len({c['article_no'] for c in data}),chunks=len(data),
                max_content_chars=max(len(c['content']) for c in data),max_embedding_chars=max(len(c['embedding_text']) for c in data),
                body_matches_reference=canonical(data)==canonical(case.get('expected_chunks',[])),
                exact_old_chunk_boundaries=[c['content'] for c in data]==[c['content'] for c in case.get('expected_chunks',[])],
                articles_match_reference=[a.article_no for a in parse_articles(doc.lines)]==case.get('expected_articles'),
                parent_links=dict(valid=parent_ok,total=len(data)),
                fragment_sequence=dict(valid=valid_fragment,total=len(data)),
                provenance=dict(valid=sum(bool(c['metadata']['source_spans']) and all('page' in s and 'line' in s for s in c['metadata']['source_spans']) for c in data),total=len(data)),
                median_prepare_ms=statistics.median(timings)*1000,prepare_ms=[t*1000 for t in timings],
                semantic_accuracy='NOT_LABELED',revision=revision,processing_signature=metadata['processing_signature'])
        except Exception as e:record.update(status='REJECTED',error_type=type(e).__name__)
        records.append(record)

    cache=QA/'local/v021-final-a860abf'
    inventory=json.loads((cache/'inventory.json').read_text('utf-8'))
    mapping=json.loads((cache/'private-map.json').read_text('utf-8'))
    samples=[]
    for row in inventory['records']:
        sid=row['id'];file=Path(mapping[sid]);pred=cache/(sid+'-prediction.json')
        record=dict(id=sid,scenario=row['scenario'],cached_ocr_source_commit=inventory['source_commit'])
        if hashlib.sha256(file.read_bytes()).hexdigest()!=row['sha256']:
            record.update(status='BLOCKED_SOURCE_HASH_CHANGED');samples.append(record);continue
        if not pred.exists():
            record.update(status='NO_CACHED_PREDICTION',note='negative or safety rejection; original guard checked separately');samples.append(record);continue
        r=DocumentResult.from_dict(json.loads(pred.read_text('utf-8')))
        record['cached_prediction_sha256']=hashlib.sha256(pred.read_bytes()).hexdigest()
        record['cached_parse_status']=r.parsing_status
        if preview_chunks is None:
            record.update(status='BASELINE_PREVIEW_NOT_APPLICABLE')
            # 法规桥接的旧接口仍可对照，但不把案例强行当法规处理。
        else:
            try:
                started=time.perf_counter();p=preview_chunks(r,'case',max_chars=800);elapsed=time.perf_counter()-started
                target=out/'samples'/sid;target.mkdir(parents=True,exist_ok=True)
                (target/'chunk-preview.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
                groups={}
                for c in p['chunks']:groups.setdefault(c['metadata']['parent_section_id'],[]).append(c)
                record.update(status='PREVIEWED',chunks=p['chunk_count'],parents=p['parent_count'],tables=len(p['tables']),
                    body_roundtrip=p['quality']['body_roundtrip_equal'],quality=p['quality'],requires_review=p['requires_review'],
                    parent_links=dict(valid=sum(c['metadata']['parent_section_id'] in {x['parent_id'] for x in p['parents']} for c in p['chunks']),total=p['chunk_count']),
                    elapsed_ms=elapsed*1000,semantic_accuracy='NOT_LABELED',section_accuracy='NOT_LABELED')
            except Exception as e:record.update(status='REJECTED',error_type=type(e).__name__)
        samples.append(record)

    unchanged=all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items())
    bindings={n:m.__file__ for n,m in sys.modules.copy().items() if n.startswith('qa_core') and getattr(m,'__file__',None)}
    assert all(Path(p).resolve().is_relative_to(source) for p in bindings.values())
    verify(source,args.source_sha)
    value=dict(source_commit=args.source_sha,source_path=str(source),bindings=bindings,python=sys.version,
               max_chars=800,model_signature='QA-SAME-MODEL',corpus_protected_files=len(protected),corpus_unchanged=unchanged,
               legal_records=records,samples=samples,source_file_truth_sha256=hashlib.sha256(truth_path.read_bytes()).hexdigest(),
               preview_available=preview_chunks is not None,case_baseline_policy='baseline has no preview API; not a regression',
               cached_ocr_policy='historical parser JSON used as input to current chunk code; not current OCR measurements')
    (out/'comparison.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(source_commit=args.source_sha,legal=len(records),legal_statuses=dict(Counter(r['status'] for r in records)),samples=dict(Counter(r['status'] for r in samples)),corpus_unchanged=unchanged)))
    return 0 if unchanged else 1


if __name__=='__main__':raise SystemExit(main())
