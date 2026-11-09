"""专项命令行必须保留显式环境开关，报告记录实际生效值。"""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import scripts.test_document_parsing as cli


class TableCLIConfigTests(unittest.TestCase):
    def check_config(self,environment,flags,expected):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,environment,clear=False):
            if 'OCR_ENABLE_TABLES' not in environment:
                os.environ.pop('OCR_ENABLE_TABLES',None)
            with patch.object(cli,'DocumentParser') as parser,patch.object(cli.MemorySampler,'start'),patch.object(cli.MemorySampler,'stop'),contextlib.redirect_stdout(io.StringIO()) as output:
                parser.return_value.__enter__.return_value.parse_batch.return_value=[]
                cli.main(['--input','synthetic.pdf','--output-dir',folder,*flags])
            self.assertEqual(parser.call_args.args[0].enable_tables,expected)
            import json
            reports=list(Path(folder).rglob('*.json'))
            benchmark=next(json.loads(p.read_text('utf-8')) for p in reports if 'tables' in json.loads(p.read_text('utf-8')))
            self.assertEqual(benchmark['tables'],expected)

    def test_Q021_002_explicit_env_survives_absent_flag(self):
        self.check_config({'OCR_ENABLE_TABLES':'1'},[],True)

    def test_unset_env_remains_disabled(self):
        self.check_config({},[],False)

    def test_explicit_flag_enables_tables(self):
        self.check_config({},['--tables'],True)


if __name__=='__main__':unittest.main()
