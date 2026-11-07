# v0.1 independent acceptance — FAIL

## Latest authoritative version gate — 2026-11-07

Unresolved P1 prevents current local integration PASS. Production deployment is not accepted; v0.2.0 is not authorized to start.

| Reference | Exact identity |
| --- | --- |
| Remote fix/round1 | `f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57`, independently read from GitHub branches API |
| Local fix/round1 tested | `4e5f4a79ae5bd9d97316916c854ce6504e447dcc` |
| QA test/helper commit | `e7c62e25aeace99625b5f13c164129f44a7456bb` |

Local and remote differ. Local 4e5f4a7 imported the preceding QA tests/reports; no qa_core, scripts, requirements-api.txt or Dockerfile changes exist against remote f7c4d75. Therefore Fix's 109-test report describes a historical suite. Read current handoff-to-qa.md, 05-fix-report.md and docs/mineru-integration/05-开发与测试记录.md from the exact local source; do not inherit their live service/DB PASS. Remote identity was checked through [the repository branches endpoint](https://api.github.com/repos/joker33338/market-regulation-platform/branches?per_page=100), without changing any remote ref.

A fresh detached QA validation worktree was created at 4e5f4a7; prior validation and original/Fix worktrees were preserved. Existing Python and optional API libraries were reused read-only; no install/upgrade or business-source edit. Real DSNs/credentials were cleared for synthetic runs. Local asynchronous sockets were permitted, while remote fixtures remain MockTransport.

| Current execution | Methods | PASS methods | Failing methods | Skips |
| --- | ---: | ---: | ---: | ---: |
| scripts/run_fix_regressions.ps1 -Python configured-interpreter | 113 | 101 | 2 | 10 |
| Complete QA rerun with existing API libraries available | 113 | 107 | 2 | 4 |

The supplied script resets PYTHONPATH to a source-local API environment absent in the fresh worktree. An attempted dependency junction was denied; no packages were installed or copied. Six FastAPI cases were additionally skipped by that script, then all six executed PASS in the complete rerun using the existing package path. The gate uses the latter run. Expected failures: zero. Console failures=3 represents two failing methods: both local-batch order subtests fail, plus the ZIP case. The helper deduplicates overlapping QA cases already imported by Fix and exports SHA-bound evidence.

Reproduction from QA with configured interpreter/dependencies and writable TEMP/TMP:

```text
python -B tests/run_round01_validation.py --source <isolated-checkout> --include-source-tests --result-json <ignored-evidence-json>
```

Original R01-001/002/003 targeted assertions PASS. Reference Mock cases 13 PASS, production implementation cases 16 PASS, official-adapter cases 2 PASS, and FastAPI cases 6 PASS. These include authentication/ownership, uploads/results, uncertain creation, interrupted upload, idempotency, resume, normalization, reviewed legal bridge and SQLite retrieval. No real remote service or database is implied.

**Current failures:** DOC-003/R01-005 P1 (corrupt-first stops valid sibling; valid-first task incorrectly failed instead of partial), and SEC-001/R01-004 P2 (ZIP ARTIFACT.BIN overwrites original artifact.bin on Windows). Both reproduced on 4e5f4a7; functions and synthetic reproducers remain in 03-bug-list.md. No duplicate bug IDs created.

### Four current skips, explicitly reviewed

| Test | Reason / disposition |
| --- | --- |
| MinerUReferenceContracts.test_production_adapter_acceptance | Historical unconditional baseline skip. Its absent-client message is stale; actual production client/config/API tests ran. Not evidence that the feature remains absent, and not product PASS. |
| ParsingPostgresTests.test_transactional_insert_idempotency_and_existing_rows_preserved | PARSING_TEST_PG_DSN not supplied; requires approved existing isolated document_review tables, intentionally retains a synthetic row. NOT RUN / environment BLOCKED. |
| ParsingPostgresTests.test_child_failure_rolls_back_parent_insert | Same DB prerequisite absent. NOT RUN / environment BLOCKED; fake-sink retry is not PostgreSQL transaction evidence. |
| PostgreSQLIntegration.test_isolated_schema_build_publish_query_rollback | MVP_TEST_PG_DSN not supplied. Creates/drops a generated schema and must never target the default business DB. NOT RUN / environment BLOCKED. |

The three DB cases are counted once as skips, not as additional test methods. No skip allowlist waiving them was invented. Current original local/parser/legal/SQLite suites PASS; local multi-file orchestration remains FAIL. No P0 confirmed; the unresolved P1 alone blocks advancement.

Actual DocumentParser, PaddleOCRService, PaddleStructureService, quality.py, OfficialMinerUClient, MinerUService, PostgresResultSink and reviewed legal adapter were inspected. Native routing, OCR confidence/provenance, Structure output and quality findings already exist and should be reused after approval. quality.py returns heuristic findings/review flags, not an implemented automatic local/cloud routing policy. No next-version feature development or planning handoff is started while the gate FAILS.

Machine data: version-gate.json is FAIL; round01/handoff.json requests a **v0.1 bugfix**, not a v0.2.0 feature. Reports cannot embed their own future transport commit SHA; Git supplies that after commit. Fresh logs/statistics remain ignored as local/round01/v01-full-regression.log and v01-execution.json; supplied script log stays in the validation worktree's ignored reports.

Coordinator source review found an independent preparation checkout: README/schema/tools describe fail-closed behavior, no completed write-dispatch adapter, and a reader hardcoded to the next-version handoff path. Current-version JSON is validated against its schema, but no --run/--resume, coordinator-state edit or automatic wakeup is performed. Current repair data stays under round01; no v0.2.0 READY file is created to bypass this gate. **等待协调器接收。**

The remainder records the prior f7c4d75 regression as historical evidence. In particular, earlier real local OCR/BGE successes below are not newly executed real-model tests in this latest gate run; their business-source files are unchanged. Real cloud/Standard, full-corpus quality, live PostgreSQL, actual Docker build, browser visual and Aliyun GPU remain unverified by this QA gate.

## Prior independent regression at f7c4d75 (retained history)

Report updated: 2026-11-07 (Asia/Shanghai).

- Original source baseline: `f2a5c925f0305a2e7df21f750b20bed63db40de3`.
- First QA handoff: `13db6f7b18e8661b3c462f105d1f55c1a153bcea`.
- Tested Fix handoff: `f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57`.
- Business code in that handoff: `6981ac8b78b2419c367e2c224979448a7010259e`, including `4767e71952a2cb8f2b4277e6f0694ddb515b67e9` and `7b1a173`.

## Isolation and execution

QA created a detached validation worktree at the exact Fix handoff under its ignored local area. Original and Fix worktrees were not edited. Validation worktree remains clean. QA additions are two test/helper files on `qa/round1`; no business implementation was modified. The original four test modules have no diff from the initial QA handoff.

Used existing Python 3.12 interpreter and read-only access to Fix's already-installed optional API dependencies. QA did not install or upgrade dependencies. Synthetic tests cleared DB connection variables; HTTP fixtures use MockTransport. No real corpus bytes were sent to remote services. PostgreSQL writes and schema changes were not performed.

The restricted environment initially stalled at Windows `socketpair` while creating the asynchronous event loop. A bounded 30-second diagnostic confirmed the wait occurs before application startup. The first attempt was interrupted, then tests were run with permission for local event-loop sockets. The controlled re-run completed; the environment stall is not counted as a product bug.

Reproduction (configured interpreter; writable TEMP/TMP; optional API dependency path available):

```text
# In the detached Fix worktree; all real DB DSNs cleared:
python -B -m unittest discover -s tests -v

# From QA, targeting the detached Fix worktree:
python -B tests/run_round01_validation.py --source <isolated-fix-checkout> --include-source-tests
```

The QA runner imports business code from the selected source and loads QA acceptance cases separately. Do not run the QA branch's old baseline source and call it Fix regression.

## Results

| Execution | Test methods | PASS methods | FAIL methods | Skipped methods |
| --- | ---: | ---: | ---: | ---: |
| Supplied Fix suite, independently rerun | 109 | 105 | 0 | 4 |
| Four additional QA acceptance cases | 4 | 2 | 2 | 0 |
| Combined single run | 113 | 107 | 2 | 4 |

Four skips: original PostgreSQL integration, two opt-in parsing PostgreSQL tests, and the old QA reference-driver product placeholder. Actual production-client Mock tests ran successfully; the historical placeholder is not proof of missing production code and was not used to grant acceptance.

The latest unittest console summary is `FAILED (failures=3, skipped=4)`: the two orders in the local-batch case each fail a subtest, plus the ZIP case fails once. There are two failing test methods and three failure records. The table counts test methods, not subtest failure records; it does not hide an additional bug.

| Bug | Result | Independent evidence |
| --- | --- | --- |
| DOC-001 / R01-001 | PASS | Both empty/whitespace regression cases now return non-success. |
| OCR-001 / R01-002 | PASS | Unicode grid detection and decoded-image positive control pass. |
| DOC-002 / R01-003 | PASS | Docker COPY source preflight passes; actual build NOT_TESTED. |
| SEC-001 / R01-004 | FAIL | ZIP member ARTIFACT.BIN overwrites original artifact.bin on Windows. |
| DOC-003 / R01-005 | FAIL | Broken first local PDF stops processing; valid sibling stays created. |

The two additional passing controls verify local DB-failure error serialization and successful retry with the original remote ID using a fake sink. They do not prove PostgreSQL transaction behavior.

Existing production-client fixtures cover self-hosted Tasks request contract, uncertain creation, source integrity, interrupted upload, bounded polling/resume, partial success, ZIP limits/traversal, real normalization and reviewed SQLite retrieval. Official public v4 has a separate adapter and separate Mock fixtures. These APIs are not treated as equivalent, and a fixture version string does not verify a deployed worker version.

## Real local models and corpus regression

Using the exact detached Fix source, repeated the two bounded, read-only local OCR samples: S00001 JPG success (174 normalized characters), S00002 PDF page 1 success (137 characters). Offline model files were reused with an explicit ASCII cache; original corpus unchanged. Result counts match the initial smoke, but no new accuracy or table-completeness claim is made.

Real local BGE check: one synthetic input, one output vector, dimension 1024 — PASS. No local MinerU models were downloaded.

Ignored evidence: `local/round01/combined-regression.log`, `qa-fix-regression-unrestricted.log`, `additional-acceptance.log`, `fixed-ocr.log`, `fixed-bge.log`; local model summaries in the validation area's ignored outputs. Do not commit raw logs or machine paths.

## Feature and environment gates

GAP matrix is in `05-missing-features.md`: GAP-003 and GAP-007 PASS within stated scope; GAP-002 and GAP-005 FAIL; GAP-001 and GAP-004 BLOCKED; GAP-006 and GAP-008 NOT_TESTED.

Fix reports earlier authorized live official API/PostgreSQL runs. QA has not independently reproduced those runs and does not inherit their PASS. The current user scope requires clearly isolated test DB writes, so no connection was used merely because it appeared in another worktree's local configuration. Self-hosted Standard, real official endpoint, DB idempotency/rollback, browser visual use, Docker build and Aliyun GPU remain unverified by this QA run.

Conclusion: original three reported defects pass targeted regression. Overall acceptance FAIL because two new defects remain, with separate environment and scope gates still open. Incremental handoff gives Fix their reproducible tests; no merge or push performed.
