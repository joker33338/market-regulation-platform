"""REVIEW ONLY: explicit approval required; never run by default orchestration.
Preserves only cleanup; original legacy method assertions remain unchanged.
"""
import argparse,json,os,re,sys
from pathlib import Path
from unittest.mock import patch
import unittest
p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,required=True)
p.add_argument('--approve-retained-test-schema',action='store_true')
a=p.parse_args()
if not a.approve_retained_test_schema:p.error('DDL approval required; this entry is review-only by default')
sys.path.insert(0,str(a.source.resolve()))
from qa_core.storage.database import Database
from tests import test_postgres_integration as test_module
class PreserveSchema(Database):
    def __init__(self,**kw):
        super().__init__(**kw)
        row=self.one("SELECT current_database() AS db,current_setting('qa.round01_isolated',true) AS marker")
        if row['db']!='qa_round01' or row['marker']!='test-only':raise RuntimeError('Not the existing QA-only database')
        ext=self.one("SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'")
        if not ext or ext['nspname']!='public':raise RuntimeError('Preexisting public vector extension required; no installation allowed')
        self.retained=None
    def execute(self,sql,params=None):
        normalized=' '.join(sql.split())
        if normalized.startswith('CREATE SCHEMA '):
            name=normalized.removeprefix('CREATE SCHEMA ')
            if not re.fullmatch('mvp_test_[0-9a-f]{32}',name):raise RuntimeError('Unsafe schema')
            if self.one('SELECT oid FROM pg_namespace WHERE nspname=:name',{'name':name}):raise RuntimeError('Schema already exists')
            self.retained=name
        if normalized=='CREATE EXTENSION IF NOT EXISTS vector':return super().execute('SELECT 1')
        if normalized.startswith(('DROP ','TRUNCATE ','ALTER ')):
            if self.retained and normalized=='DROP SCHEMA '+self.retained+' CASCADE':
                print(json.dumps({'cleanup':'suppressed','retained_schema':self.retained}))
                return super().execute('SELECT 1')
            raise RuntimeError('Destructive DDL forbidden')
        return super().execute(sql,params)
with patch.object(test_module,'Database',PreserveSchema):
    suite=unittest.defaultTestLoader.loadTestsFromName('PostgreSQLIntegration.test_isolated_schema_build_publish_query_rollback',test_module)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() and not result.skipped else 2)
