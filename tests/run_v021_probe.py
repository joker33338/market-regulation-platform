"""按匿名ID执行受限离线路由检查，原始输出仅留本地忽略目录。"""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument('--id',required=True)
    arg.add_argument('--tables',choices=['on','off'],default='off')
    arg.add_argument('--runtime',choices=['fake','real'],default='fake')
    arg.add_argument('--mode',choices=['auto','structure'],default='auto')
    arg.add_argument('--page',type=int,default=1)
    a=arg.parse_args()
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    common=Path(subprocess.check_output(['git','-C',str(root),'rev-parse','--path-format=absolute','--git-common-dir'],text=True,encoding='utf-8').strip())
    local=root/'local/v021'
    config=json.loads((common/'agent-local.json').read_text('utf-8'))
    os.environ.update(MARKET_REGULATION_TEST_CORPUS=config['corpus'],OCR_MODEL_ROOT=str(Path(config['originalRoot'])/'models/ocr'),
                     HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True')
    from qa_core.document_parsing.document_router import DocumentParser
    from qa_core.document_parsing.config import ParsingConfig
    from tests.test_document_parsing import FakeRuntime
    path=Path(json.loads((local/'private-map.json').read_text('utf-8'))[a.id])
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    started=time.perf_counter()
    parsing=replace(ParsingConfig.from_env(),enable_tables=a.tables=='on',worker_timeout=180)
    runtime=FakeRuntime() if a.runtime=='fake' else None
    value=dict(id=a.id,runtime=a.runtime,tables_enabled=parsing.enable_tables,mode=a.mode,selected_page=a.page)
    prefix=a.id+'-'+a.runtime+'-'+a.tables+'-p'+str(a.page)
    try:
        with DocumentParser(parsing,runtime=runtime) as parser:
            result=parser.parse(path,mode=a.mode,page_numbers=[a.page] if a.runtime=='real' and path.suffix.lower()=='.pdf' else None)
        (local/(prefix+'-raw.json')).write_text(result.to_json(),encoding='utf-8')
        value.update(status=result.parsing_status,pages=[dict(page=p.page_number,method=p.parsing_method,status=p.parsing_status,
             chars=len(p.normalized_text),tables=len(p.tables),cells=sum(len(t.cells) for t in p.tables),
             confidence=p.confidence,network_attempts=p.network_blocked_attempts,elapsed=p.processing_time,error_type=p.error_type) for p in result.pages])
    except Exception as error:value.update(status='ERROR',error_type=type(error).__name__)
    value.update(elapsed=time.perf_counter()-started,sha256_unchanged=digest==hashlib.sha256(path.read_bytes()).hexdigest())
    (local/(prefix+'-summary.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
