"""断网只读核验Fix原始auto产物，不执行模型、服务、云请求或数据库写入。"""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


def verify(root, output):
    sys.path.insert(0, '/app')
    import qa_core
    from qa_core.document_parsing.mineru_artifacts import unpack, normalize_artifacts
    from qa_core.document_parsing.mineru_config import MinerUConfig
    assert Path(qa_core.__file__).is_relative_to('/app/qa_core')
    read = lambda name: json.loads((root/name).read_text('utf-8'))
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    summary = read('verification-summary.json')
    plan = read('approved-plan.json')
    result = read('final-result.json')
    for name, sha in summary['evidence_sha256'].items():
        assert digest(root/name) == sha, name
    assert plan['source_commit'] == 'c91547d393ca6b049e216c0051e25271d06d7359'
    assert digest(root/'synthetic-auto-final.png') == plan['sha256']
    ledger = read('finite-http-ledger.json')
    assert len(ledger) == 5 and all(x['response_status'] == 200 for x in ledger)
    assert [x['method'] for x in ledger] == ['POST','GET','PUT','GET','GET']
    assert all(result['checks'].values()) and len(result['checks']) == 11
    log = (root/'execution.log').read_text('utf-8')
    assert "Creating model: ('PP-OCRv5_mobile_det'" in log
    assert "Creating model: ('PP-OCRv5_mobile_rec'" in log
    assert read('local-inference-success.json')[0]['nonempty_text'] is True
    final_paths = [p for p in (root/'tasks').rglob('normalized.json')
                   if 'routing_trace' in json.loads(p.read_text('utf-8')).get('quality',{})]
    assert len(final_paths) == 1
    final = json.loads(final_paths[0].read_text('utf-8'))
    assert digest(final_paths[0]) == summary['finals'][0]['sha256']
    trace = final['quality']['routing_trace']
    local, remote = (trace['raw_results'][k] for k in ['local','remote'])
    text = lambda d: '\n'.join(p['raw_text'] for p in d['pages'])
    assert local['parsing_status'] == 'success' and len(text(local).strip()) == 8
    assert len(text(remote).strip()) == 8
    assert trace['fallback_reason'] == ['short_page'] and trace.get('failure_reason') is None
    assert trace['selected_engine'] == ['mineru_official'] and final['requires_review']
    assert local['document_id'] == remote['document_id'] == plan['sha256']
    assert local['source_location']['source_file_id'] == remote['source_location']['source_file_id'] == 'SYN-AUTO-FINAL-01'
    assert [p['page_number'] for p in local['pages']] == [1]
    assert [p['page_number'] for p in remote['pages']] == [1]
    payloads = []
    for p in root.rglob('tasks.sqlite3'):
        con = sqlite3.connect('file:'+p.as_posix()+'?mode=ro&immutable=1', uri=True)
        rows = con.execute('SELECT payload FROM parse_tasks').fetchall()
        con.close()
        assert len(rows) == 1
        payloads.append(json.loads(rows[0][0]))
    assert len(payloads) == 2 and all(t['status']=='completed' for t in payloads)
    child = next(t for t in payloads if t['mode']=='remote')
    file = child['files'][0]
    archives = list(root.rglob('artifact.bin'))
    assert len(archives) == 1
    artifacts = unpack(archives[0].read_bytes(), MinerUConfig(provider='official', api_url='https://mineru.net/api'))
    original = json.loads(next(v for k,v in artifacts.items() if k.endswith('_content_list.json') or k=='content_list.json'))
    assert original and any(x.get('text','').strip() for x in original)
    rebuilt = normalize_artifacts(child, file, artifacts).to_dict()
    assert text(rebuilt) == text(remote) and rebuilt['document_id'] == remote['document_id']
    assert text(final) == text(remote)
    output.write_text(json.dumps(dict(status='PASS',source_commit=plan['source_commit'],
        evidence_hashes_verified=len(summary['evidence_sha256']), raw_zip_normalization='PASS',
        raw_candidate_and_final_text_match=True, source_and_pages_match=True,
        completed_parent_and_child=True, real_model_log_and_payload=True,
        execution_checks=11, http_observed=5, new_http_requests=0,
        database_used=False, business_import=str(qa_core.__file__)),indent=2),encoding='utf-8')


if __name__ == '__main__':
    verify(Path('/evidence'),Path('/state/independent-audit.json'))
