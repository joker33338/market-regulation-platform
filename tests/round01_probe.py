"""Read-only corpus inventory; emits anonymous aggregate evidence only."""
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
from collections import Counter
from pathlib import Path


def main():
    import fitz
    root = Path(os.environ['MARKET_REGULATION_TEST_CORPUS'])
    files = sorted(p for p in root.rglob('*') if p.is_file())
    counts, hashes, pdf = Counter(), Counter(), Counter()
    sizes, samples = [], []
    image_checks = Counter()
    for index, path in enumerate(files, 1):
        sid = f'S{index:05d}'
        size = path.stat().st_size
        sizes.append(size)
        counts[path.suffix.lower() or '(none)'] += 1
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                h.update(block)
        hashes[h.hexdigest()] += 1
        if path.suffix.lower() in {'.jpg','.png','.jpeg'}:
            from PIL import Image
            try:
                with Image.open(path) as image:
                    image.verify()
                image_checks['readable'] += 1
            except Exception:
                image_checks['unreadable'] += 1
        if path.suffix.lower() == '.pdf':
            try:
                with fitz.open(path) as doc:
                    pdf['files'] += 1
                    pdf['pages'] += len(doc)
                    text_pages = sum(bool(p.get_text().strip()) for p in doc)
                    pdf['text_layer_pages'] += text_pages
                    pdf['no_text_layer_pages'] += len(doc)-text_pages
                    pdf['mixed_files' if 0 < text_pages < len(doc) else 'text_files' if text_pages else 'no_text_files'] += 1
            except Exception:
                pdf['unreadable'] += 1
        if path.suffix.lower() in {'.docx', '.pdf', '.png', '.jpg', '.xlsx', '.doc', '.txt'}:
            samples.append((sid, path))
    packages = {}
    for name in ['pymupdf','paddleocr','paddlepaddle','sentence-transformers','torch','fastapi','psycopg','openpyxl','python-docx']:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = 'MISSING'
    from qa_core.document_parsing.config import ParsingConfig
    models = {}
    for method in ['ocr','structure']:
        try:
            ParsingConfig.from_env().validate_models(method)
            models[method] = 'files_present'
        except Exception as exc:
            models[method] = type(exc).__name__
    # Native smoke only: OCR inference is separately bounded.
    from qa_core.document_parsing.document_router import DocumentParser
    smoke, selected = [], Counter()
    with DocumentParser() as parser:
        for sid, path in samples:
            ext = path.suffix.lower()
            if selected[ext] >= 2 or ext in {'.png','.jpg'}:
                continue
            if ext == '.pdf':
                with fitz.open(path) as doc:
                    if any(not p.get_text().strip() for p in doc):
                        continue
            selected[ext] += 1
            try:
                result = parser.parse(path)
                smoke.append(dict(id=sid, type=ext, status=result.parsing_status, pages=len(result.pages), tables=sum(len(p.tables) for p in result.pages)))
            except Exception as exc:
                smoke.append(dict(id=sid,type=ext,status=type(exc).__name__))
    evidence = dict(python=platform.python_version(), packages=packages, models=models,
                    total=len(files), types=dict(counts), total_bytes=sum(sizes), max_bytes=max(sizes,default=0),
                    empty=sum(s==0 for s in sizes), images=dict(image_checks),
                    size_bins={'lt_1MiB':sum(s<1048576 for s in sizes),'1_to_5MiB':sum(1048576<=s<5242880 for s in sizes),'ge_5MiB':sum(s>=5242880 for s in sizes)},
                    duplicate_groups=sum(n>1 for n in hashes.values()),
                    duplicate_excess=sum(n-1 for n in hashes.values()), pdf=dict(pdf), smoke=smoke)
    Path('local/round01/inventory.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence,ensure_ascii=True))


if __name__ == '__main__':
    main()
