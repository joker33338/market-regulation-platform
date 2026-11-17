"""审核后候选构建使用现有服务；合成来源与临时SQLite，禁止自动发布。"""
import unittest

from tests import test_ingestion_api as fixtures


class WorkbenchIngestionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.IngestionAPITests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.ledger.state = lambda *args: {"status": "approved" if self.f.ledger.approved else "unreviewed", "version": 1, "current_revision": self.f.ledger.revision}
        self.file_id = self.f.row["source_location"]["source_file_id"]

    def prepare(self):
        response = self.f.client.post(f"/api/workbench/documents/{self.file_id}/prepare",
            json={"title": "合成法规", "document_type": "law",
                  "expected_sha256": self.f.row["document_id"], "source_parse_id": "synthetic-parse"},
            headers={**self.f.f.auth, "Idempotency-Key": "synthetic-prepare"})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    def test_approved_document_builds_in_background_without_publishing(self):
        job = self.prepare()
        self.f.f.app.state.workbench_ingestion.tick()
        result = self.f.client.get(f"/api/workbench/jobs/{job['job_id']}", headers=self.f.f.auth)
        self.assertEqual(result.json()["status"], "awaiting_publish", result.text)
        self.assertIsNone(self.f.active())

    def test_unapproved_document_waits_without_building(self):
        self.f.ledger.approved = False
        job = self.prepare()
        self.f.f.app.state.workbench_ingestion.tick()
        result = self.f.client.get(f"/api/workbench/jobs/{job['job_id']}", headers=self.f.f.auth)
        self.assertEqual(result.json()["status"], "awaiting_review")
        self.assertIsNone(self.f.active())

    def test_revoked_admin_role_cannot_be_reused_by_background_job(self):
        job = self.prepare()
        self.f.f.app.state.auth_registry.replace({"a"*32: dict(principal_id="synthetic-admin",owner_id="alice",
            roles=["USER"],review_owner_scopes=[],credential_status="active")})
        self.f.f.app.state.workbench_ingestion.tick()
        result = self.f.client.get(f"/api/workbench/jobs/{job['job_id']}", headers=self.f.f.auth)
        self.assertEqual(result.json()["status"], "awaiting_admin")
        self.assertIsNone(self.f.active())

    def test_stale_file_sha_is_rejected_before_creating_job(self):
        response = self.f.client.post(f"/api/workbench/documents/{self.file_id}/prepare",
            json={"title":"合成法规","document_type":"law","expected_sha256":"0"*64},
            headers={**self.f.f.auth,"Idempotency-Key":"stale"})
        self.assertEqual(response.status_code,409)

    def test_explicit_publication_still_rechecks_active_version(self):
        job = self.prepare()
        self.f.f.app.state.workbench_ingestion.tick()
        response = self.f.client.post(f"/api/workbench/jobs/{job['job_id']}/publish",
            json={"expected_active_version":"wrong-version"},headers={**self.f.f.auth,"Idempotency-Key":"wrong-release"})
        self.assertEqual(response.status_code,409)
        self.assertIsNone(self.f.active())
        response = self.f.client.post(f"/api/workbench/jobs/{job['job_id']}/publish",
            json={"expected_active_version":None},headers={**self.f.f.auth,"Idempotency-Key":"confirmed-release"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["status"],"published")
        self.assertIsNotNone(self.f.active())

    def test_waiting_front_item_cannot_starve_new_queued_item(self):
        from qa_core.api.workbench_ingestion import KnowledgeJobs
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            store=KnowledgeJobs(None,None,Path(directory))
            with store.locked():
                for operation,status,next_check in [('0'*64,'awaiting_review',10),('f'*64,'queued',0)]:
                    store.save({'operation_id':operation,'job_id':operation,'status':status,
                                'next_check_at':next_check,'created_at':'2026-11-17'})
            self.assertEqual(store.claim()['job_id'],'f'*64)
            self.assertEqual(store.claim()['job_id'],'0'*64)

    def scoped_prepare(self,start,end,key):
        from qa_core.api.source_segments import text_digest
        return self.f.client.post('/api/workbench/documents/'+self.file_id+'/prepare',json={
            'title':'合成分篇','document_type':'law','expected_sha256':self.f.row['document_id'],
            'source_parse_id':'synthetic-parse','source_range':{'start':start,'end':end,'expected_text_sha256':text_digest(self.f.row['raw_text'])}},
            headers={**self.f.f.auth,'Idempotency-Key':key})

    def test_overlapping_confirmed_parts_are_rejected_without_changing_first_job(self):
        first=self.scoped_prepare(0,5,'first-range')
        self.assertEqual(first.status_code,202,first.text)
        second=self.scoped_prepare(3,8,'overlap-range')
        self.assertEqual(second.status_code,409,second.text)
        self.assertEqual(second.json()['error']['code'],'source_scope_overlap')
        original=self.f.client.get('/api/workbench/jobs/'+first.json()['job_id'],headers=self.f.f.auth).json()
        self.assertEqual(original['status'],'queued')

    def test_published_scope_cannot_be_silently_replaced_by_new_split(self):
        job=self.prepare();store=self.f.f.app.state.workbench_ingestion
        with store.locked():
            value=store.read(job['job_id']);value['status']='published';store.save(value)
        response=self.scoped_prepare(0,5,'new-split')
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(response.json()['error']['code'],'published_source_change_requires_replacement')
        self.assertEqual(self.f.client.get('/api/workbench/jobs/'+job['job_id'],headers=self.f.f.auth).json()['status'],'published')

    def test_newer_pg_import_blocks_job_bound_to_old_parse_without_sqlite_history(self):
        job=self.prepare()
        self.f.f.reader.review.latest_parse_id=lambda owner,file_id:'newer-parse'
        self.f.f.app.state.workbench_ingestion.tick()
        current=self.f.client.get('/api/workbench/jobs/'+job['job_id'],headers=self.f.f.auth).json()
        self.assertEqual(current['status'],'needs_attention')
        self.assertEqual(current['error_code'],'review_source_changed')
        self.assertIsNone(self.f.active())
