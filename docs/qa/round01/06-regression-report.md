# Round 01 independent regression

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
