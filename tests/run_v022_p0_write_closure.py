"""在同一冻结镜像中用独立SQLite及真实本地OCR完成P0；无网络、无PG、无Mock。"""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time


def main():
    sys.path.insert(0, '/app')
    for key in ('PG_DSN','PARSING_RESULT_PG_DSN','MVP_TEST_PG_DSN','QA_ISOLATED_PG_DSN','MINERU_API_KEY'):
        os.environ.pop(key, None)
    os.environ.update(OCR_MODEL_ROOT='/models/ocr', OCR_ENABLE_TABLES='0', HOME='/tmp/qa-home',
                      HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True')
    from PIL import Image, ImageDraw, ImageFont
    import fitz
    from fastapi.testclient import TestClient
    from qa_core.document_parsing.mineru_api import create_app
    from qa_core.document_parsing.mineru_config import MinerUConfig
    from qa_core.document_parsing.dual_engine import DualEngineConfig
    import qa_core
    assert str(qa_core.__file__).startswith('/app/qa_core/')
    root = Path('/state')
    assert not (root/'parsing').exists(), '不复用或覆盖已有测试状态'
    config = MinerUConfig(enabled=True, mode='local', result_dir=root/'parsing')
    app = create_app(config, tokens={'a'*32:'synthetic-p0-only'},
                     dual_config=DualEngineConfig(enabled=True, cloud_enabled=False))
    assert app.state.service.result_sink is None
    auth={'Authorization':'Bearer '+'a'*32}
    font=ImageFont.truetype('/qa-font.ttf',44)
    cases=[]
    with TestClient(app) as client:
        for label, lines in [('normal',['Public synthetic document for independent QA.', 'Invoice amount 123.45 on 2026-11-11.']),('short',['QA021'])]:
            image=Image.new('RGB',(1500,330),'white');draw=ImageDraw.Draw(image)
            for idx,line in enumerate(lines): draw.text((45,50+idx*85),line,font=font,fill='black')
            png=io.BytesIO();image.save(png,format='PNG')
            with fitz.open() as pdf:
                page=pdf.new_page(width=750,height=165);page.insert_image(page.rect,stream=png.getvalue())
                assert not page.get_text().strip(), '样本必须为纯图PDF，排除原生文本提取冒充OCR'
                content=pdf.tobytes()
            sha=hashlib.sha256(content).hexdigest();(root/(label+'.pdf')).write_bytes(content)
            upload=client.post('/api/parse/files?file_name=synthetic.pdf',headers=auth,content=content)
            assert upload.status_code==201
            fid=upload.json()['file_id'];assert upload.json()['sha256']==sha
            create=client.post('/api/parse/tasks',headers={**auth,'Idempotency-Key':'p0-'+label},
                               json={'file_ids':[fid],'strategy':'auto','allow_cloud_fallback':False,'sensitive':True})
            assert create.status_code==202
            task=create.json();tid=task['task_id'];states=[task['status']]
            deadline=time.monotonic()+150
            while time.monotonic()<deadline:
                task=client.get('/api/parse/tasks/'+tid,headers=auth).json()
                if task['status']!=states[-1]:states.append(task['status'])
                if task['status'] in {'completed','failed','partial','timed_out'}:break
                time.sleep(.2)
            (root/(label+'-task.json')).write_text(json.dumps(task),encoding='utf-8')
            assert task['status']=='completed', task.get('error')
            response=client.get('/api/parse/tasks/'+tid+'/results',headers=auth);assert response.status_code==200
            result=response.json()['results'][0];doc=result['document'];pages=doc['pages']
            (root/(label+'-result.json')).write_text(json.dumps(doc),encoding='utf-8')
            assert len(pages)==1 and pages[0]['page_number']==1
            assert pages[0]['parsing_method']=='ocr' and pages[0]['raw_text'].strip()
            assert pages[0]['layout_blocks'] and pages[0]['raw_result']
            assert pages[0]['model_load_time']>=0
            assert all(b.get('bbox') for b in pages[0]['layout_blocks'])
            assert doc['document_id']==sha and task['files'][0]['sha256']==sha
            assert doc['source_location']['source_file_id']==fid
            original=client.get('/api/parse/files/'+fid+'/source',headers=auth)
            assert original.status_code==200 and original.content==content
            history=client.get('/api/documents/'+fid+'/parse-history',headers=auth).json()['list']
            assert len(history)==1 and history[0]['task']['task_id']==tid and history[0]['source_file_id']==fid
            assert history[0]['file_id']==result['file_id']
            quality=doc['quality'];reasons=quality['routing']['reasons']
            if label=='normal':assert 'short_page' not in reasons
            else:assert 'short_page' in reasons
            assert doc['requires_review'] is True  # OCR正常结果也须人工复核，不伪造自动批准。
            again=client.post('/api/parse/tasks',headers={**auth,'Idempotency-Key':'p0-'+label},
                             json={'file_ids':[fid],'strategy':'auto','allow_cloud_fallback':False,'sensitive':True})
            assert again.json()['task_id']==tid
            cases.append(dict(label=label,upload_status=201,task_initial=create.json()['status'],states=states,
                              file_id=fid,task_id=tid,sha256=sha,task_file_id=result['file_id'],engine='paddle_ocr',
                              characters=len(pages[0]['raw_text'].strip()),blocks=len(pages[0]['layout_blocks']),
                              page_count=1,quality_reasons=reasons,requires_review=True,idempotent=True,
                              original_bytes_equal=True,source_linked=True))
        assert len({x['file_id'] for x in cases})==2 and len({x['task_id'] for x in cases})==2
        assert client.get('/api/documents',headers=auth).json()['total']==2
        # 第二次同名上传后，第一个原件依然完整。
        for case in cases:
            data=client.get('/api/parse/files/'+case['file_id']+'/source',headers=auth).content
            assert hashlib.sha256(data).hexdigest()==case['sha256']
    (root/'p0-result.json').write_text(json.dumps(dict(status='PASS',cases=cases,business_import=qa_core.__file__,
        network='none',mock_used=False,shared_state_mounted=False,postgres_connected=False,
        cloud_requests=0,original_files_not_overwritten=True),indent=2),encoding='utf-8')
    print('PASS: two isolated synthetic image-PDF API write closures with real OCR')


if __name__=='__main__': main()
