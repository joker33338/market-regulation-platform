"""真实本地模型链路；仅连接已显式准备的隔离服务，不得指向8180。"""
import requests,fitz,json,time,hashlib,os
from pathlib import Path
from uuid import uuid4
BASE=os.environ.get('V023_PIPELINE_BASE_URL','http://127.0.0.1:18186')
if os.environ.get('V023_REAL_PIPELINE')!='1' or BASE!='http://127.0.0.1:18186':
 raise RuntimeError('仅允许获准的18186隔离服务')
OUT=Path('local/release-v023/native-pipeline');OUT.mkdir(exist_ok=True)
s=requests.Session()
def call(method,path,status=200,**kw):
 r=s.request(method,BASE+path,timeout=240,**kw)
 assert r.status_code==status,(method,path,r.status_code,r.text[:1200])
 return r

def receipt(stage,**extra):
 print(json.dumps(dict(stage=stage,**extra),ensure_ascii=False),flush=True)

def main():
 response=call('POST','/api/auth/login',json={'username':'synthetic-admin','password':'Synthetic-Release-Only-2026'})
 s.headers['Authorization']='Bearer '+response.json()['access_token']
 doc=fitz.open();page=doc.new_page()
 text='合成验证管理办法\n第一章 总则\n第一条 为验证系统真实解析、人工审核和检索链路，制定本合成管理办法。本文仅供独立测试，不是实际法律法规。\n第二条 测试人员应当核验上传文件、解析结果和来源引用。审核通过后应当通过显式入库与发布操作形成可检索版本，禁止自动发布。\n第三条 系统应当记录真实操作身份，保护原始结果，保留历史审核事件和版本记录。'
 assert page.insert_textbox(fitz.Rect(55,55,540,780),text,fontname='china-s',fontsize=14)>0
 data=doc.tobytes();doc.close()
 upload=call('POST','/api/parse/files?file_name=synthetic-release.pdf',data=data,headers={'Content-Type':'application/octet-stream'},status=201).json()
 fid=upload['file_id'];assert upload['sha256']==hashlib.sha256(data).hexdigest()
 task=call('POST','/api/parse/tasks',json={'file_ids':[fid]},headers={'Idempotency-Key':uuid4().hex},status=202).json()
 tid=task['task_id'];deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  task=call('GET','/api/parse/tasks/'+tid).json()
  if task['status'] in ('completed','failed','canceled','timed_out'):break
  time.sleep(.4)
 (OUT/'task.json').write_text(json.dumps(task,ensure_ascii=False),encoding='utf-8')
 assert task['status']=='completed',task
 pid=task['files'][0]['database_parse_id'];assert pid
 assert call('GET',f'/api/parse/files/{fid}/source').content==data
 before=call('GET','/api/review/'+pid).json();(OUT/'review-before.json').write_text(json.dumps(before,ensure_ascii=False),encoding='utf-8')
 assert before['file_name']=='synthetic-release.pdf',before['file_name']
 assert task['files'][0]['selected_engine']==['native_pdf'],task['files'][0]['selected_engine']
 receipt('upload_parse_pg',engine=task['files'][0]['selected_engine'],parse_id_present=bool(pid),source_unchanged=True)
 approval=call('POST',f'/api/review/{pid}/approve',json={'base_result_id':pid,'expected_version':0},headers={'Idempotency-Key':uuid4().hex}).json()
 assert approval['operator_id'].startswith('account-'),approval
 receipt('mysql_approve',version=approval['version'],operator_recorded=bool(approval['operator_id']))
 body={'kb_version':'real-local-v1','documents':[{'parse_id':pid,'law_name':'合成验证管理办法','law_id':'synthetic-release-law','expected_review_version':1}]}
 pre=call('POST','/api/ingestion/precheck',json=body).json();assert pre['eligible'],pre
 started=time.monotonic()
 build=call('POST','/api/ingestion/batches',json=body,headers={'Idempotency-Key':uuid4().hex},status=201).json()
 assert build['status']=='STAGED',build
 receipt('real_bge_build',seconds=round(time.monotonic()-started,2),status=build['status'])
 call('POST','/api/ingestion/publish',json={'kb_version':body['kb_version'],'expected_active_version':None},headers={'Idempotency-Key':uuid4().hex})
 library=call('GET','/api/library/laws').json();assert library['total']==1,library
 for mode in ('keyword','hybrid'):
  search=call('POST','/api/knowledge/search',json={'query':'审核','mode':mode}).json()
  assert search['status']=='ready' and search['count']>0,search
  (OUT/(mode+'-search.json')).write_text(json.dumps(search,ensure_ascii=False),encoding='utf-8')
 receipt('publish_catalog_search',law_count=library['total'],modes=['keyword','hybrid'])
 body['kb_version']='real-local-v2'
 call('POST','/api/ingestion/batches',json=body,headers={'Idempotency-Key':uuid4().hex},status=201)
 call('POST','/api/ingestion/publish',json={'kb_version':body['kb_version'],'expected_active_version':'real-local-v1'},headers={'Idempotency-Key':uuid4().hex})
 call('POST','/api/ingestion/rollback',json={'kb_version':'real-local-v1','expected_active_version':'real-local-v2'},headers={'Idempotency-Key':uuid4().hex})
 after=call('GET','/api/review/'+pid).json()
 (OUT/'review-after.json').write_text(json.dumps(after,ensure_ascii=False),encoding='utf-8')
 assert all(before[k]==after.get(k) for k in before if k not in {'review_ledger','review_write_supported'}), '原始结果发生变化'
 receipt('rollback_source_protection',passed=True)
 (OUT/'result.json').write_text(json.dumps({'passed':True,'real_models':True,'source_file_id':fid,'parse_id':pid,'task_id':tid,'version':'real-local-v1'},ensure_ascii=False),encoding='utf-8')

if __name__=='__main__':main()
