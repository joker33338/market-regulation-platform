"""前端补齐接口的合成隔离测试，不访问正式服务。"""
import json
from unittest.mock import patch
import unittest

from tests import test_frontend_api as fixtures


class MissingAPITests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.FrontendAPITests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.client=self.f.client

    def test_task_events_are_real_transitions_and_owner_scoped(self):
        _,task=self.f.upload_task()
        path='/api/parse/tasks/'+task['task_id']+'/logs'
        result=self.client.get(path,headers=self.f.auth)
        self.assertEqual(result.status_code,200,result.text)
        self.assertTrue(result.json()['available'])
        original=result.json()['total']
        value=self.f.service.repository.get(task['task_id'],'alice')
        self.f.service.repository.save(value)
        self.assertEqual(self.client.get(path,headers=self.f.auth).json()['total'],original)
        value['status']='failed';self.f.service.repository.save(value)
        rows=self.client.get(path,headers=self.f.auth).json()
        self.assertEqual(rows['total'],original+1)
        self.assertEqual(rows['list'][0]['status'],'failed')
        self.assertEqual(self.client.get(path,headers=self.f.other).status_code,404)
        self.assertEqual(self.client.get(path).status_code,401)
        self.assertNotIn(str(self.f.root),json.dumps(rows))

    def test_historical_task_does_not_invent_stage_logs(self):
        _,task=self.f.upload_task()
        value=self.f.service.repository.get(task['task_id'],'alice')
        value.pop('stage_events',None)
        with self.f.service.repository.connect() as connection:
            connection.execute('UPDATE parse_tasks SET payload=? WHERE id=?',(json.dumps(value),task['task_id']))
        result=self.client.get('/api/parse/tasks/'+task['task_id']+'/logs',headers=self.f.auth).json()
        self.assertEqual(result['list'],[])
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'],'historical_events_not_recorded')

    def test_request_logs_redact_and_isolate_principals(self):
        self.client.get('/api/documents?keyword=synthetic-private-query',headers=self.f.auth)
        self.client.get('/api/documents/not-found',headers=self.f.auth)
        self.client.get('/api/documents',headers=self.f.other)
        result=self.client.get('/api/system/api-logs',headers=self.f.auth)
        self.assertEqual(result.status_code,200,result.text)
        rows=result.json()['list']
        self.assertTrue(any(row['route']=='/api/documents/{file_id}' and row['status_code']==404 for row in rows))
        text=result.text
        self.assertNotIn('synthetic-private-query',text)
        self.assertNotIn('a'*32,text)
        self.assertNotIn(str(self.f.root),text)
        self.assertTrue(all(row['principal_id']=='legacy:alice' for row in rows))
        errors=self.client.get('/api/system/error-logs',headers=self.f.auth).json()['list']
        self.assertTrue(errors)
        self.assertTrue(all(row['status_code']>=400 for row in errors))
        self.assertEqual(self.client.get('/api/system/api-logs?date_from=2026-01-01T00:00:00',headers=self.f.auth).status_code,422)

    def test_logging_failure_does_not_change_business_receipt(self):
        with patch.object(self.f.app.state.operational_journal,'append',side_effect=OSError('sensitive')):
            self.assertEqual(self.client.get('/api/documents',headers=self.f.auth).status_code,200)
        response=self.client.get('/api/system/api-logs',headers=self.f.auth)
        self.assertEqual(response.status_code,503)
        self.assertNotIn('sensitive',response.text)

    def test_unconfirmed_actor_is_not_falsely_attributed_and_admin_can_inspect(self):
        self.assertEqual(self.client.get('/api/documents').status_code,401)
        own=self.client.get('/api/system/error-logs',headers=self.f.auth).json()
        self.assertEqual(own['list'],[])
        self.f.app.state.auth_registry.replace({'a'*32:dict(principal_id='admin-observer',owner_id='alice',
            roles=['ADMIN'],review_owner_scopes=[],credential_status='active')})
        result=self.client.get('/api/system/error-logs',headers=self.f.auth)
        self.assertEqual(result.status_code,200,result.text)
        event=next(row for row in result.json()['list'] if row['route']=='/api/documents' and row['status_code']==401)
        self.assertIsNone(event['principal_id']);self.assertFalse(event['actor_confirmed'])
