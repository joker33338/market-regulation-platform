"""只对自建表格核对结构；在同一进程加载Paddle之前验证网络拒绝。"""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


def main():
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    common=Path(subprocess.check_output(['git','-C',str(root),'rev-parse','--path-format=absolute','--git-common-dir'],text=True,encoding='utf-8').strip())
    local=root/'local/v021';config=json.loads((common/'agent-local.json').read_text('utf-8'))
    os.environ.update(OCR_MODEL_ROOT=str(Path(config['originalRoot'])/'models/ocr'),OCR_ENABLE_TABLES='1',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True')
    from qa_core.document_parsing import runtime
    from qa_core.document_parsing.config import ParsingConfig
    from qa_core.document_parsing.paddle_structure import PaddleStructureService
    from PIL import Image,ImageDraw,ImageFont
    before='paddleocr' not in sys.modules
    if not before:raise RuntimeError('Paddle已提前导入，拒绝继续')
    runtime.install_offline_guard()
    blocked=[]
    for name,probe in [('DNS',lambda:socket.getaddrinfo('invalid.example',443)),
                       ('CONNECT',lambda:socket.create_connection(('192.0.2.1',443),timeout=1))]:
        try:probe()
        except OSError as e:
            blocked.append(name if 'network is disabled' in str(e) else 'UNVERIFIED')
        else:raise RuntimeError('网络拒绝自检失败，禁止加载模型')
    if blocked!=['DNS','CONNECT']:raise RuntimeError('无法证明预导入网络拒绝')
    truth=[['ITEM','QTY','PRICE'],['ALPHA','10','100'],['BETA','20','200']]
    image=Image.new('RGB',(1200,600),'white');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(str(Path(os.environ['WINDIR'])/'Fonts/arial.ttf'),38)
    for x in [80,420,760,1100]:draw.line((x,100,x,490),fill='black',width=4)
    for y in [100,230,360,490]:draw.line((80,y,1100,y),fill='black',width=4)
    for row,values in enumerate(truth):
        for col,value in enumerate(values):draw.text((100+col*340,145+row*130),value,fill='black',font=font)
    source=local/'synthetic-table.png';image.save(source)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    parsing=ParsingConfig.from_env();parsing.validate_models('structure')
    class DirectRuntime:
        def predict(self,method,path):return runtime._worker_predict(method,path,parsing)
    page=PaddleStructureService(DirectRuntime(),True).parse_image(str(source),1,{'sample_id':'SYN-T001'})
    normalized=lambda rows:[[str(c).strip().upper() for c in row] for row in rows]
    actual=[normalized(t.rows) for t in page.tables]
    value=dict(sample='SYN-T001',provenance='SYNTHETIC',guard_before_paddle=before,
        preimport_probes=blocked,tables_enabled=parsing.enable_tables,tables=len(page.tables),
        cells=sum(len(t.cells) for t in page.tables),expected=truth,actual=actual,
        exact_structure_and_text=normalized(truth) in actual,elapsed=page.processing_time,
        network_blocked_attempts=page.network_blocked_attempts,sha256_unchanged=digest==hashlib.sha256(source.read_bytes()).hexdigest())
    (local/'synthetic-structure.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
