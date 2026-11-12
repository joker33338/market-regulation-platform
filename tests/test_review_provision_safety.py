"""初始化工具的隔离安全测试；不连接MySQL、不执行真实DDL。"""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from contextlib import redirect_stderr


class ReviewProvisionSafetyTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('review_provision_test',root/'scripts/provision_review_mysql.py')
        self.module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp=tempfile.TemporaryDirectory(dir=root/'local')
        self.addCleanup(self.temp.cleanup)
        self.target=Path(self.temp.name)/'runtime.json'
        self.args=['provision','--database','market_review_test_abcdef','--config-out',str(self.target),
                   '--api-host','mysql']

    def invoke(self,connection,args=None):
        with patch('sys.argv',args or self.args), patch.dict(os.environ,{'REVIEW_MYSQL_ADMIN_JSON':json.dumps({'host':'synthetic','user':'admin','password':'synthetic'})}), patch('pymysql.connect',return_value=connection):
            self.module.main()

    def test_rejects_business_database_before_connect(self):
        args=list(self.args);args[2]='market_regulation'
        with patch('sys.argv',args),patch('pymysql.connect') as connect,redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.module.main()
        connect.assert_not_called()

    def test_existing_database_never_receives_ddl(self):
        connection=MagicMock();cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value=('market_review_test_abcdef',)
        with self.assertRaises(RuntimeError): self.invoke(connection)
        self.assertEqual(cursor.execute.call_count,1)
        self.assertTrue(cursor.execute.call_args.args[0].startswith('SELECT'))
        self.assertFalse(self.target.exists())
        connection.close.assert_called_once()

    def test_existing_config_not_overwritten(self):
        self.target.write_text('preserve',encoding='utf-8')
        with patch('sys.argv',self.args),patch('pymysql.connect') as connect,redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.module.main()
        connect.assert_not_called()
        self.assertEqual(self.target.read_text(),'preserve')

    def test_new_schema_grants_append_only_events(self):
        connection=MagicMock();cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value=None
        with patch('sys.stdout',io.StringIO()): self.invoke(connection)
        config=json.loads(self.target.read_text())
        self.assertNotEqual(config['user'],'root')
        self.assertNotIn('writers',config)
        grants=[call.args[0] for call in cursor.execute.call_args_list if call.args[0].startswith('GRANT')]
        self.assertEqual(len(grants),3)
        self.assertTrue(any('GRANT SELECT,INSERT ON' in sql and 'review_events' in sql for sql in grants))
        self.assertFalse(any('DELETE' in sql for sql in grants))
        connection.commit.assert_called_once()


if __name__=='__main__': unittest.main()
