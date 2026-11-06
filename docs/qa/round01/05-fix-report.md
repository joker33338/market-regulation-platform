# Round 01 Fix report — usable upload-to-database version

QA commit: `13db6f7b18e8661b3c462f105d1f55c1a153bcea`.
Source baseline: `f2a5c925f0305a2e7df21f750b20bed63db40de3`.
Imported test baseline: `2e344c5`.
Bug fix commit: `7b1a173`.
Implementation commit: `4767e71952a2cb8f2b4277e6f0694ddb515b67e9`.
Final code / workbench status commit: `6981ac8b78b2419c367e2c224979448a7010259e`.
The resulting documentation/handoff SHA is supplied by Git and the Fix chat, not embedded in itself.

User steering: directly call official API first, pause server deployment; prioritize file upload through database inspection.
The user supplied and authorized a local PostgreSQL test connection. Existing document_review tables were inspected read-only
and reused without migrations or history changes. User explicitly authorized isolated API dependency installation.

| IDs | Cause / implementation | Tests and actual status |
| --- | --- | --- |
| DOC-001 / R01-001 | native text always defaulted to success; DocumentParser.parse now marks empty/whitespace needs_review | both QA reproducers PASS; old blank PDF behavior preserved; 7b1a173 |
| OCR-001 / R01-002 | cv2 Windows filename reader failed on Unicode; has_grid reads pathlib bytes then imdecode | QA grid positive control and actual Unicode path PASS; 7b1a173 |
| DOC-002 / R01-003 / GAP-007 | tracked Docker scenarios resource absent; added synthetic non-legal sample consumed by existing smoke | build-context preflight PASS; actual Docker build NOT_TESTED; 7b1a173 |
| GAP-001 / MINERU-FEAT-001 | no client; MinerUClient provides self-hosted Tasks and OfficialMinerUClient separately provides public v4 | production implementation Mock contracts PASS; official synthetic PDF real call PASS; self-hosted live NOT_TESTED |
| GAP-002 / MINERU-FEAT-002 | no lifecycle/config; MinerUConfig, TaskRepository, MinerUService persist identities, bound work, prevent uncertain create retries | resume, cancel, integrity, queue/idempotency and partial-result tests PASS |
| GAP-003 / MINERU-FEAT-003 | no HTTP application; create_app adds authenticated upload/status/result/artifact/resume/cancel and local upload page | API owner isolation/validation/page tests PASS; actual HTTP upload to official/PG PASS |
| GAP-004 / MINERU-FEAT-004 | KB tables lacked remote associations; durable local task store plus transactional PostgresResultSink to existing review tables | PostgreSQL idempotency and rollback PASS; task IDs remain SQLite, distributed/PG task queue not delivered |
| GAP-005 / MINERU-FEAT-005 | no safe remote artifacts/normalization; strict origin/ZIP checks, separate official output adapter, retained raw and normalized results, reviewed legal adapter | archive/fault/normalization/table-blocking and reviewed SQLite retrieval PASS; official result in PostgreSQL confirmed |
| GAP-006 / MINERU-FEAT-006 | GPU deployment absent | DEFERRED by user's latest instruction; no ECS/GPU claim |
| GAP-008 | generic documents/Excel/table knowledge ingestion | PENDING scope; no implicit general Chunker or automatic KB publication |

Changed functions/modules: document_router.has_grid/DocumentParser.parse; mineru_config.MinerUConfig;
mineru_client.MinerUClient; mineru_official.OfficialMinerUClient; mineru_repository.TaskRepository;
mineru_service.MinerUService; mineru_artifacts.unpack/store_artifacts/normalize_artifacts/reviewed_legal_document;
mineru_api.create_app; storage.parsing_results.PostgresResultSink.save; upload HTML and related scripts/tests.
See implementation commit for exact file inventory.

Executed commands/results:

```text
python -B -m unittest tests.test_round01_regressions tests.test_round01_integrity
# initial: 5 tests, 4 expected failures
./scripts/run_fix_regressions.ps1
# final: 109 tests, 105 PASS, 4 skipped, 0 failures
python -B -m unittest tests.test_parsing_postgres tests.test_mineru_implementation tests.test_mineru_api tests.test_mineru_official -v
# with explicit approved test DSN: 24 PASS, before the later page-only test
python -B scripts/verify_upload_database.py
# real local HTTP -> official v4 -> PostgreSQL: PASS; synthetic one-page PDF only
node --check reports/parsing-ui.js
# PASS
git diff --check
# PASS
```

Full regression skips are the original PG schema test, QA's old reference product gate and two explicitly opt-in PG tests.
The two PG tests ran separately successfully; QA's reference driver is not used as proof of production code acceptance.
No original tests were deleted/weakened. No production DDL, pushes, model downloads, corpus uploads or data deletion occurred.

Remaining risks: single ASGI process only; raw file/storage retention needs operating policy;
official cancellation cannot stop the remote server; unknown structured output remains review-only;
no full-corpus quality, GPU, self-hosted live Standard, Docker build or browser visual acceptance claimed.
All Bug/GAP implementations need QA review against the recorded code SHA. Detailed design/runbook is in docs/mineru-integration/.
