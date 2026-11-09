# v0.1 follow-up repair — 2026-11-07, awaiting QA acceptance

QA transport: `bb257b1ab81019d82121932a71c773e858ec09b8`,
`e7c62e25aeace99625b5f13c164129f44a7456bb`,
`db977dded430161ccf9beefccfddb48df4ff416b`.
Latest imported baseline: `83f4ea7`. Repair commit: `0cfb4f2f12d5fd87a57c0a2cacdc92a4cf54d2a4`.
QA-owned version-gate.json remains FAIL; Fix does not grant itself PASS.

Reused the existing red execution: 4 QA methods, 2 failing methods / 3 failure records,
matching corrupt-first, valid-first and Windows reserved-artifact cases. No old assertion weakened.

| Bug | Root cause / minimal repair | Verification |
| --- | --- | --- |
| DOC-003 / R01-005 P1 | MinerUService._local had only task-wide error handling. Isolate parser/integrity/DB failure per file; persist each outcome; aggregate partial accurately. Save the exact pre-DB normalized result so retry skips successful siblings and preserves DB digest/record identity. | Both QA file orders pass; failure visibility, exact-result DB retry and interrupted-worker recovery pass. |
| SEC-001 / R01-004 P2 | Reserved ZIP names were compared case-sensitively on Windows. Canonicalize names before validating reserved roots; use exclusively created temporary files to avoid archive-member/temp-name collisions. | QA original-package assertion and case/path variants pass; malicious packages leave existing raw bytes unchanged; ordinary members and raw ZIP remain byte-exact. |

Changed files/functions: mineru_service.py::run/_local/resume;
mineru_artifacts.py::unpack/store_artifacts;
scripts/run_fix_regressions.ps1 (reuse explicit or existing API packages; clear result-DB DSN);
tests/test_round01_repair_edges.py (five focused boundary cases).

Actual execution, using the existing interpreter/API packages and writable ignored TEMP/TMP:

```text
python -B -m unittest tests.test_round01_fix_acceptance tests.test_round01_repair_edges -v
# 9 PASS
./scripts/run_fix_regressions.ps1 -ApiPackages <existing-api-site-packages>
# one complete regression after all code changes: 118 total, 114 PASS, 4 skipped, 0 failures
git diff --check
# PASS
```

The four skips remain the old QA reference placeholder and three opt-in database cases;
all FastAPI cases executed. No new live DB, remote API, model/performance test, dependency
installation, environment/worktree creation, service restart or Push in this repair batch.
Tests were run before the repair commit; its code is the tested code without further business edits.

Return this code SHA to Agent A through handoff-to-qa.md. Remaining risks/gates:
QA must independently repeat the new reproducers and assess DB/real-provider prerequisites.
v0.2.0 has no PASS/READY handoff, so no dual-engine development branch or code was started.
The requested requirements consolidation stays after dual-engine implementation, not in this repair.
No working coordinator dispatch was available; this is a Git handoff, not an automatic-wakeup claim.

## Prior first usable version (historical)

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
