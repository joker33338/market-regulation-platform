"""SCA-001：无真实连接的关系身份边界测试，实际 PG 行为由独立 QA 验收。"""
import unittest
from unittest.mock import MagicMock, patch

from qa_core.storage.database import Database, KB_TABLES
from qa_core.utils import IngestionError


class SchemaIdentityTests(unittest.TestCase):
    def database(self, schema='public'):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = dict(current_schema=schema, namespace_oid=10,
                                           visible_vector=20, public_vector=20, owns_schema=True)
        cursor.fetchall.return_value = [dict(name=name, expected_oid=index+100, namespace_oid=10,
            visible_oid=index+100, relkind='r', foreign_domain=False) for index,name in enumerate(KB_TABLES)]
        with patch('psycopg2.connect', return_value=connection):
            database = Database(pg_dsn='synthetic-only', kb_schema=schema)
        return database, cursor

    def test_public_and_explicit_test_schema_are_accepted(self):
        for schema in ('public', 'mvp_test_'+'a'*32):
            db, cursor = self.database(schema)
            db.verify_schema()
            self.assertEqual(cursor.execute.call_args.args[1][1],schema)

    def test_invalid_schema_rejected_before_connect(self):
        for schema in ('document_review','mvp_test_bad','public;DROP SCHEMA public','',None):
            with self.subTest(schema=schema), patch('psycopg2.connect') as connect:
                with self.assertRaises(IngestionError):Database(pg_dsn='synthetic-only',kb_schema=schema)
                connect.assert_not_called()

    def test_wrong_search_path_or_namespace_is_rejected(self):
        for change in (dict(current_schema='document_review'),dict(namespace_oid=None)):
            db,cursor=self.database()
            cursor.fetchone.return_value.update(change)
            with self.assertRaises(IngestionError):db.active_version()
            self.assertFalse(any('SELECT kb_version FROM mr_active' in c.args[0] for c in cursor.execute.call_args_list))

    def test_missing_shadow_view_or_cross_schema_relation_fails_closed(self):
        for change in (dict(expected_oid=None),dict(visible_oid=999),dict(namespace_oid=99),
                       dict(relkind='v'),dict(foreign_domain=True)):
            with self.subTest(change=change):
                db,cursor=self.database('mvp_test_'+'a'*32)
                cursor.fetchall.return_value[0].update(change)
                with self.assertRaises(IngestionError):db.execute('DELETE FROM law_chunks')
                self.assertFalse(any(c.args[0]=='DELETE FROM law_chunks' for c in cursor.execute.call_args_list))

    def test_missing_test_table_cannot_fall_back_to_public(self):
        db,cursor=self.database('mvp_test_'+'a'*32)
        cursor.fetchall.return_value[2].update(expected_oid=None,visible_oid=1234)
        with self.assertRaises(IngestionError):db.verify_schema()

    def test_vector_type_shadow_is_rejected(self):
        db,cursor=self.database()
        cursor.fetchone.return_value['visible_vector']=99
        with self.assertRaises(IngestionError):db.verify_schema()

    def test_test_schema_must_be_owned_by_current_role(self):
        db,cursor=self.database('mvp_test_'+'a'*32)
        cursor.fetchone.return_value['owns_schema']=False
        with self.assertRaises(IngestionError):db.verify_schema()

    def test_each_statement_revalidates_and_rollback_is_still_possible(self):
        db,cursor=self.database()
        db.execute('SELECT * FROM mr_chunks').close()
        cursor.fetchall.return_value[0]['visible_oid']=999
        with self.assertRaises(IngestionError):db.execute('UPDATE mr_active SET kb_version=:v',{'v':'fixture'})
        db.execute('ROLLBACK')
        self.assertEqual(cursor.execute.call_args.args[0],'ROLLBACK')

    def test_initialization_rejects_partial_schema_before_ddl(self):
        db,cursor=self.database()
        cursor.fetchall.return_value[0]['expected_oid']=None
        with self.assertRaises(IngestionError):db.initialize()
        self.assertFalse(any(c.args[0].lstrip().startswith('CREATE ') for c in cursor.execute.call_args_list))

    def test_incomplete_metadata_fails_closed(self):
        db,cursor=self.database()
        cursor.fetchall.return_value=[]
        with self.assertRaises(IngestionError):db.verify_schema()
