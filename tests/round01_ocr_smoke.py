"""Bounded offline real-document smoke; never prints document content."""
import json
import os
from pathlib import Path
from qa_core.document_parsing.document_router import DocumentParser


def main():
    paths = sorted(p for p in Path(os.environ['MARKET_REGULATION_TEST_CORPUS']).rglob('*') if p.is_file())
    evidence = []
    with DocumentParser() as parser:
        for suffix in ('.jpg', '.pdf'):
            index, path = next((i,p) for i,p in enumerate(paths,1) if p.suffix.lower()==suffix)
            result = parser.parse(path, page_numbers=[1] if suffix=='.pdf' else None)
            evidence.append(dict(id=f'S{index:05d}',type=suffix,status=result.parsing_status,
                                 pages=[dict(method=p.parsing_method,status=p.parsing_status,
                                             chars=len(p.normalized_text),error_type=p.error_type,
                                             error=p.error_message) for p in result.pages]))
            Path('local/round01/ocr-smoke.json').write_text(json.dumps(evidence),encoding='utf-8')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
