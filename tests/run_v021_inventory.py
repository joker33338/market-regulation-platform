"""只读盘点场景目录；匿名摘要可提交，路径映射仅保存在忽略目录。"""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from collections import Counter
from zipfile import ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    common = Path(subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--path-format=absolute', '--git-common-dir'], text=True, encoding='utf-8').strip())
    config = json.loads((common/'agent-local.json').read_text('utf-8-sig'))
    os.environ['MARKET_REGULATION_TEST_CORPUS'] = config['corpus']
    corpus = Path(os.environ['MARKET_REGULATION_TEST_CORPUS'])
    import fitz
    from PIL import Image
    candidates = []
    for folder in sorted(corpus.iterdir()):
        match = re.match(r'^(0[1-9]|1[0-2])(?:\D|$)', folder.name)
        if folder.is_dir() and match:
            candidates.extend((match[1], p) for p in sorted(folder.rglob('*')) if p.is_file())
    labels = []
    for file in corpus.glob('*.csv'):
        with file.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if {'file', 'page', 'correct_type', 'expected_engine'}.issubset(reader.fieldnames or []):
                labels.extend(reader)
    local = root/'local/v021'
    local.mkdir(parents=True, exist_ok=True)
    records, mapping, pages = [], {}, []
    hashes = Counter()
    by_path = {}
    for index, (scenario, path) in enumerate(candidates, 1):
        sid = f'S{index:05d}'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[digest] += 1
        record = dict(id=sid, scenario=scenario, extension=path.suffix.lower(), bytes=path.stat().st_size,
                      sha256=digest, valid=False, pages=0, label_status='NOT_LABELED')
        mapping[sid] = str(path)
        by_path[path.resolve()] = record
        try:
            if path.suffix.lower()=='.pdf':
                with fitz.open(path) as pdf:
                    if pdf.needs_pass:raise ValueError('encrypted')
                    record.update(valid=len(pdf)>0, pages=len(pdf))
                    for number, page in enumerate(pdf, 1):
                        text = len(''.join(page.get_text().split()))
                        pages.append(dict(id=sid, page=number, text_chars=text, images=len(page.get_images()),
                                          metadata_type='text' if text else 'scan' if page.get_images() else 'blank'))
            elif path.suffix.lower()=='.docx':
                with ZipFile(path) as archive:
                    record.update(valid='word/document.xml' in archive.namelist(), pages=None)
            elif path.suffix.lower() in {'.jpg','.jpeg','.png'}:
                with Image.open(path) as image:
                    image.verify()
                record.update(valid=True,pages=1)
            else:
                record['reason']='UNSUPPORTED'
        except Exception as error:
            record['reason']=type(error).__name__
        records.append(record)
    matched=out_of_range=outside=missing=file_level=0
    type_counts=Counter();engine_counts=Counter()
    normalized_labels=[]
    for row in labels:
        target=(corpus/row['file'].replace('\\','/')).resolve()
        record=by_path.get(target)
        if record is None:
            if target.is_file():outside+=1
            else:missing+=1
            continue
        try:number=int(row['page'])
        except (ValueError,TypeError):out_of_range+=1;continue
        if number==0 and record['scenario']=='12':
            file_level+=1
            record['label_status']='FILE_LEVEL'
            continue
        if number<1 or (record['pages'] is not None and number>record['pages']):out_of_range+=1;continue
        matched+=1
        record['label_status']='LABELED'
        expected=row['expected_engine'];correct=row['correct_type']
        type_counts[correct]+=1;engine_counts[expected]+=1
        normalized_labels.append(dict(id=record['id'],page=number,correct_type=correct,expected_engine=expected))
    summary=dict(source_commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True, encoding='utf-8').strip(),
                 scenario_files=len(records),scenario_counts=dict(Counter(r['scenario'] for r in records)),
                 valid_files=sum(r['valid'] for r in records),valid_pdf_pages=sum((r['pages'] or 0) for r in records if r['valid'] and r['extension']=='.pdf'),
                 unique_hashes=len(hashes),duplicate_files=sum(n-1 for n in hashes.values()),
                 label_rows=len(labels),matched_label_rows=matched,missing_label_files=missing,
                 labels_outside_scenarios=outside,label_page_errors=out_of_range,file_level_label_rows=file_level,
                 labeled_files=sum(r['label_status']=='LABELED' for r in records),label_types=dict(type_counts),label_engines=dict(engine_counts),
                 records=records,pages=pages,labels=normalized_labels)
    (local/'private-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
    (local/'inventory.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in {'records','pages','labels'}},ensure_ascii=False))


if __name__=='__main__':
    main()

