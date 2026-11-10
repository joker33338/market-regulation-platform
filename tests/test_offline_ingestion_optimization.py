"""OFF-QA-01～16 的独立合成验收；真值、数据库和 Fix 工作树均不修改。"""
import contextlib
from copy import deepcopy
from dataclasses import replace
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from qa_core.document_parsing.schemas import DocumentResult, LayoutBlock, PageResult, TableResult
from qa_core.document_parsing.bridge import to_legal_document
from qa_core.indexing.chunking import bounded_parts, split_articles
from qa_core.indexing.legal_structure import parse_articles
from qa_core.indexing.models import LegalDocument, SourceLine
from qa_core.indexing.preview import preview_chunks
from qa_core.indexing.service import prepare_document, ingest_documents
from qa_core.config.settings import CHUNKER_VERSION, Settings
from qa_core.utils import IngestionError, stable_hash

SOURCE = Path(os.environ['OFFLINE_QA_SOURCE']) if os.getenv('OFFLINE_QA_SOURCE') else Path(__import__('qa_core').__file__).resolve().parents[1]


def result(lines, *, status='success', title='合成材料', page=1):
    blocks = [LayoutBlock(str(i), 'text', text, [10, i*20, 200, i*20+18], reading_order=i,
                          source_location={'file_path':'synthetic.txt','page':page}) for i, text in enumerate(lines)]
    return DocumentResult('synthetic-sha',title,'.txt',{'file_path':'synthetic.txt'},
                          [PageResult(page,'native_text',raw_text='\n'.join(lines),layout_blocks=blocks)],
                          parsing_status=status)


def content_without_label(chunks):
    return ''.join(c['content'][len(c['article_no']):].strip().replace('\n','') for c in chunks)


def cli_module():
    file=SOURCE/'scripts/preview_offline_ingestion.py'
    spec=importlib.util.spec_from_file_location('offline_qa_cli',file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class OfflineOptimizationAcceptance(unittest.TestCase):
    def assert_relationships(self, preview):
        parents={p['parent_id']:p for p in preview['parents']}
        groups={}
        for c in preview['chunks']:
            m=c['metadata'];pid=m.get('parent_article_id',m.get('parent_section_id'))
            self.assertIn(pid,parents)
            self.assertEqual(m.get('parent_article_text',m.get('parent_section_text')),parents[pid]['text'])
            self.assertTrue(m['source_spans']);self.assertEqual(m['source_span_precision'],'unit')
            self.assertTrue(all('page' in s and 'line' in s and s.get('bbox') for s in m['source_spans']))
            self.assertLessEqual(len(c['content']),preview['max_chars'])
            groups.setdefault(pid,[]).append(m)
        for group in groups.values():
            self.assertEqual([m['fragment_index'] for m in group],list(range(1,len(group)+1)))
            self.assertTrue(all(m['fragment_total']==len(group) for m in group))

    def test_OFF_QA_01_hierarchy_and_suffix(self):
        lines=['第一编 合成编','第一章 合成章','第一节 合成节','第一条 首条内容。','第二条之一 补充内容。']
        p=preview_chunks(result(lines),'law')
        self.assertEqual([x['label'] for x in p['parents']],['第一条','第二条之一'])
        m=p['chunks'][0]['metadata']
        self.assertEqual((m['part'],m['chapter'],m['section']),tuple(lines[:3]))
        self.assert_relationships(p)

    def test_OFF_QA_02_long_parent_exceptions_and_context(self):
        lines=['第一条 具备下列条件的，应当执行程序：','（一）'+('合成条件甲；'*25),'（二）'+('合成条件乙；'*25),'但是，依法豁免的除外，不得擅自删除。']
        p=preview_chunks(result(lines),'law',max_chars=96)
        self.assertEqual(len(p['parents']),1)
        expected=''.join(x.replace('第一条 ','',1) if i==0 else x for i,x in enumerate(lines))
        self.assertEqual(content_without_label(p['chunks']),expected)
        self.assertIn(lines[-1],p['parents'][0]['text'])
        self.assert_relationships(p)

    def test_OFF_QA_03_numbers_at_boundary(self):
        for token in ['2026年11月10日','123456.78万元','12.345%','〔2026〕12345号']:
            with self.subTest(token=token):
                text='甲'*60+token+'乙'*100
                parts=bounded_parts(text,64)
                self.assertEqual(''.join(parts),text)
                self.assertTrue(any(token in p for p in parts))
                self.assertTrue(all(len(p)<=64 for p in parts))
        with self.assertRaises(IngestionError):bounded_parts('1'*200,64)

    def test_OFF_QA_02_embedding_context_truncation_keeps_full_body(self):
        intro='共同适用的合成条件。'*50
        r=result(['第一条 '+intro,'（一）合成事项甲。','（二）合成事项乙。'],title='合成超长法规名称'*150)
        p=preview_chunks(r,'law',max_chars=96)
        self.assertIn(intro,p['parents'][0]['text'])
        self.assertTrue(p['quality']['body_roundtrip_equal'])
        self.assertTrue(all(c['metadata']['embedding_heading_truncated'] for c in p['chunks']))
        self.assertTrue(any(c['metadata']['embedding_context_truncated'] for c in p['chunks']))
        self.assertTrue(all(len(c['embedding_text'])<=96+64+32+2 for c in p['chunks']))

    def test_OFF_QA_04_short_units_are_packed(self):
        lines=['第一条 总体条件。']+[f'（{i}）条件甲；' for i in range(1,30)]
        p=preview_chunks(result(lines),'law',max_chars=80)
        self.assertLess(p['chunk_count'],len(lines))
        self.assert_relationships(p)
        self.assertTrue(p['quality']['body_roundtrip_equal'])

    def test_OFF_QA_05_stable_and_changed_revision(self):
        r=result(['第一条 '+('合成正文。'*40)])
        p=preview_chunks(r,'law',max_chars=96);q=preview_chunks(deepcopy(r),'law',max_chars=96)
        self.assertEqual(p,q)
        moved=deepcopy(r);moved.source_location['file_path']='moved/synthetic.txt'
        for b in moved.pages[0].layout_blocks:b.source_location['file_path']='moved/synthetic.txt'
        self.assertEqual(p['revision'],preview_chunks(moved,'law',max_chars=96)['revision'])
        self.assertNotEqual(p['revision'],preview_chunks(r,'law',max_chars=128)['revision'])
        moved.pages[0].layout_blocks[0].bbox=[1,2,3,4]
        self.assertNotEqual(p['revision'],preview_chunks(moved,'law',max_chars=96)['revision'])

    def test_OFF_QA_06_spaced_markdown_article_and_preface(self):
        p=preview_chunks(result(['重要前置适用说明。','# 第 一 条 合成正文。','第二条 其他正文。']),'law')
        self.assertEqual(p['parents'][0]['label'],'第一条')
        self.assertEqual(p['unassigned_preface'][0]['text'],'重要前置适用说明。')
        self.assertTrue(p['quality']['body_roundtrip_equal'])

    def test_OFF_QA_07_case_quotes_not_legal_articles(self):
        lines=['合成处罚决定书','一、违法事实','当事人实施合成行为。','二、处罚依据','依据第一条、第二条之规定办理。','三、处罚决定','决定作出合成处理。','四、救济途径','可以依法申请复议。']
        p=preview_chunks(result(lines),'case',max_chars=96)
        self.assertEqual([x['label'] for x in p['parents']][1:],['一、违法事实','二、处罚依据','三、处罚决定','四、救济途径'])
        self.assertTrue(all('article_no' not in c for c in p['chunks']))
        self.assertEqual(''.join(c['content'].replace('\n','') for c in p['chunks']),''.join(lines))
        self.assert_relationships(p)

    def test_OFF_QA_08_ordinary_numbered_body_and_long_title(self):
        lines=['一、普通物品列表','（一）合成物品甲','（二）合成物品乙','“处罚依据”仅是引述正文。','很长标题'+('甲'*150)]
        p=preview_chunks(result(lines,title='合成文件名'*80),'case',max_chars=96)
        self.assertEqual(p['parent_count'],1)
        self.assertEqual(''.join(c['content'].replace('\n','') for c in p['chunks']),''.join(lines))
        self.assertTrue(all(len(c['embedding_text'])<=96+128+80+10 for c in p['chunks']))

    def test_OFF_QA_09_missing_page_and_cross_page_provenance(self):
        r=result(['第一条 跨页正文。'])
        r.pages.append(PageResult(2,'ocr',raw_text='未覆盖的正文'))
        r.pages.append(PageResult(3,'native_pdf',raw_text=''))
        p=preview_chunks(r,'law')
        self.assertIn(2,p['quality']['pages_without_body_chunks'])
        self.assertTrue(p['requires_review']);self.assertFalse(p['rag_index_written'])
        r.pages[1].layout_blocks=[LayoutBlock('b2','text','跨页续文。',[1,2,3,4])]
        q=preview_chunks(r,'law');self.assertEqual(q['quality']['pages_without_body_chunks'],[])
        self.assertTrue(any(s['page']==2 for c in q['chunks'] for s in c['metadata']['source_spans']))

    def test_OFF_QA_10_exclusions_are_visible(self):
        r=result(['第一条 合成正文。'])
        for kind in ['header','footer','footnote','image','number']:
            r.pages[0].layout_blocks.append(LayoutBlock(kind,kind,'含法律解释的合成排除项。',[1,2,3,4]))
        p=preview_chunks(r,'law')
        self.assertEqual(len(p['quality']['excluded_layout_blocks']),5)
        self.assertTrue(p['requires_review']);self.assertTrue(p['warnings'])

    def test_OFF_QA_11_tables_preserved_or_rejected(self):
        r=result(['第一条 合成正文。'])
        r.pages[0].tables=[TableResult('t',rows=[['合成格'],['']],cells=[{'row':0,'column':0,'rowspan':2,'colspan':1,'text':'合成格'}],source_location={'page':1})]
        with self.assertRaises(IngestionError):preview_chunks(r,'law')
        p=preview_chunks(r,'case');self.assertEqual(p['tables'][0]['cells'],r.pages[0].tables[0].cells)
        self.assertEqual(p['tables'][0]['source_location'],{'page':1})
        r.pages[0].tables=[];r.pages[0].layout_blocks.append(LayoutBlock('t','table','表格缺结构'))
        with self.assertRaises(IngestionError):preview_chunks(r,'law')
        self.assertEqual(preview_chunks(r,'case')['quality']['pages_with_unstructured_tables'],[1])

    def test_OFF_QA_12_negative_results_and_limits(self):
        for status in ['failed','partial']:
            with self.subTest(status=status),self.assertRaises(IngestionError):preview_chunks(result(['第一条 合成正文。'],status=status),'law')
        for lines in [[],[''],['目录','第一条 正文'],['第一条 正文','第一条 重复']]:
            with self.subTest(lines=lines),self.assertRaises(IngestionError):preview_chunks(result(lines),'law')
        for size in [0,63,1601,True,80.5]:
            with self.subTest(size=size),self.assertRaises(IngestionError):preview_chunks(result(['第一条 正文']),'law',max_chars=size)
        self.assertTrue(preview_chunks(result(['第一条 正文'],status='needs_review'),'law')['requires_review'])

    def test_OFF_QA_13_three_cli_sources_same_result(self):
        cli=cli_module();r=result(['第一条 合成正文。'])
        config=MagicMock();connection=MagicMock();connection.cursor.return_value.__enter__.return_value.fetchone.return_value=(r.to_dict(),)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic.json';path.write_text(r.to_json(),encoding='utf-8')
            from types import SimpleNamespace
            a=SimpleNamespace(input=None,result=path,config=None,parse_id=None)
            from_json=cli.load_result(a)
            a.result=None;a.input=path
            with patch.object(cli,'DocumentParser') as parser,patch.object(cli,'file_sha256',return_value=r.document_id):
                parser.return_value.__enter__.return_value.parse.return_value=r
                from_file=cli.load_result(a)
            a.input=None;a.parse_id='synthetic-id';a.config=path
            path.write_text(json.dumps({'PARSING_RESULT_PG_DSN':'synthetic-private-dsn'}),encoding='utf-8')
            fake=MagicMock();fake.connect.return_value=connection
            with patch.dict('sys.modules',{'psycopg2':fake}):from_db=cli.load_result(a)
            for v in [from_file,from_db]:self.assertEqual(preview_chunks(from_json,'law'),preview_chunks(v,'law'))
            connection.set_session.assert_called_once_with(readonly=True)
            connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
                'SELECT original_result FROM document_review.documents WHERE parse_id=%s',('synthetic-id',))
            connection.rollback.assert_called_once();connection.close.assert_called_once()

    def test_OFF_QA_14_cli_protection_and_close_on_error(self):
        cli=cli_module()
        with patch.object(cli,'load_result') as load,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):cli.main(['--result','synthetic.json','--document-type','law','--max-chars','63','--output',str(SOURCE/'local/qa-invalid')])
            load.assert_not_called()
        root=SOURCE/'local';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            out=Path(folder);path=out/'chunk-preview.json';path.write_text(result(['第一条 合成正文。']).to_json(),encoding='utf-8');before=path.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                cli.main(['--result',str(path),'--document-type','law','--output',str(out)])
            self.assertEqual(path.read_bytes(),before)
            private=out/'config.json';private.write_text(json.dumps({'PARSING_RESULT_PG_DSN':'synthetic-secret'}),encoding='utf-8')
            db=MagicMock();db.rollback.side_effect=RuntimeError('synthetic-secret')
            fake=MagicMock();fake.connect.return_value=db
            from types import SimpleNamespace
            with patch.dict('sys.modules',{'psycopg2':fake}),self.assertRaises(RuntimeError):
                cli.load_result(SimpleNamespace(input=None,result=None,config=private,parse_id='synthetic'))
            db.close.assert_called_once()

    def test_OFF_QA_13_real_cli_file_and_json_equivalence(self):
        from qa_core.document_parsing.document_router import DocumentParser
        root=SOURCE/'local';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            base=Path(folder);path=base/'synthetic.txt';path.write_text('合成法规\n第一条 合成正文。\n第二条 其他正文。',encoding='utf-8')
            with DocumentParser() as parser:parsed=parser.parse(path)
            raw=base/'normalized.json';raw.write_text(parsed.to_json(),encoding='utf-8')
            env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
            for mode,input_path in [('input',path),('result',raw)]:
                execution=subprocess.run([sys.executable,'-B',str(SOURCE/'scripts/preview_offline_ingestion.py'),
                    '--'+mode,str(input_path),'--document-type','law','--output',str(base/mode)],
                    capture_output=True,env=env,timeout=30)
                self.assertEqual(execution.returncode,0,execution.stderr.decode('utf-8',errors='replace'))
            a=json.loads((base/'input/chunk-preview.json').read_text('utf-8'))
            b=json.loads((base/'result/chunk-preview.json').read_text('utf-8'))
            self.assertEqual(a,b);self.assertFalse(a['rag_index_written'])

    def test_OFF_QA_14_atomic_failure_preserves_existing_output(self):
        cli=cli_module();root=SOURCE/'local';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            base=Path(folder);raw=base/'input.json';raw.write_text(result(['第一条 合成正文。']).to_json(),encoding='utf-8')
            output=base/'out';output.mkdir();target=output/'chunk-preview.json';target.write_text('synthetic-sentinel',encoding='utf-8')
            with patch.object(cli.os,'replace',side_effect=OSError('synthetic-only')),contextlib.redirect_stdout(io.StringIO()) as log:
                code=cli.main(['--result',str(raw),'--document-type','law','--output',str(output)])
            self.assertEqual(code,1);self.assertEqual(target.read_text('utf-8'),'synthetic-sentinel')
            self.assertNotIn('synthetic-only',log.getvalue())
            self.assertFalse(list(output.glob('.chunk-preview-*')))

    def test_OFF_QA_14_output_symlink_cannot_overwrite_input(self):
        cli=cli_module();root=SOURCE/'local';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            base=Path(folder);raw=base/'input.json';raw.write_text(result(['第一条 合成正文。']).to_json(),encoding='utf-8')
            output=base/'out';output.mkdir();link=output/'chunk-preview.json';before=raw.read_bytes()
            try:link.symlink_to(raw)
            except OSError as error:self.skipTest('当前Windows令牌不能创建测试符号链接：'+type(error).__name__)
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                cli.main(['--result',str(raw),'--document-type','law','--output',str(output)])
            self.assertEqual(raw.read_bytes(),before)

    def test_OFF_QA_15_strategy_signature_and_active_not_published(self):
        import qa_core.indexing.service as service
        doc=LegalDocument('合成法规','synthetic-sha','synthetic.txt',[SourceLine('第一条 合成正文。')])
        a=prepare_document(doc,model_signature='synthetic',max_chars=800)
        with patch.object(service,'CHUNKER_VERSION','synthetic-next'):
            b=prepare_document(doc,model_signature='synthetic',max_chars=800)
        self.assertNotEqual(a[1],b[1]);self.assertNotEqual(a[3]['processing_signature'],b[3]['processing_signature'])
        database=MagicMock();database.postgres=False;database.revision_exists.return_value=False;database.cached_vector.return_value=None
        embed=MagicMock();embed.signature='synthetic';embed.dimension=2;embed.embed_documents.return_value=[[1.,0.]]
        ingest_documents([doc],database=database,embeddings=embed,settings=Settings(embedding_dimension=2),version='synthetic-candidate')
        database.publish.assert_not_called();database.initialize.assert_not_called()
        database.finish_version.assert_called_once();self.assertEqual(a[3]['chunker_version'],CHUNKER_VERSION)

    def test_OFF_QA_16_review_bridge_gates(self):
        r=result(['第一条 合成正文。'],status='needs_review')
        with self.assertRaises(IngestionError):to_legal_document(r,reviewer='',law_name='合成法规')
        preview=preview_chunks(r,'law')
        self.assertTrue(preview['requires_review']);self.assertTrue(all(c['metadata']['preview_only'] for c in preview['chunks']))
        self.assertFalse(any('reviewed_at' in str(c) for c in preview['chunks']))
        r.parsing_status='partial'
        with self.assertRaises(IngestionError):to_legal_document(r,reviewer='synthetic-reviewer',law_name='合成法规')


if __name__=='__main__':unittest.main()
