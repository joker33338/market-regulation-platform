# v0.1 repair handoff — latest gate FAIL, 2026-11-07

Latest independently tested local source: `4e5f4a79ae5bd9d97316916c854ce6504e447dcc`; remote fix/round1 verified separately at `f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57`. No business-source changes between them. QA test/helper commit: `e7c62e25aeace99625b5f13c164129f44a7456bb`.

Current full run: 113 methods, 107 PASS, 2 failing methods, 4 skips; 3 failure records from ZIP plus both local-batch orders. The requested run_fix_regressions.ps1 also executed; its extra API environment skips were covered in the full rerun. The two repairs below are still outstanding on 4e5f4a7. **Do not start v0.2.0.** Current-version machine data is in version-gate.json and round01/handoff.json; no next-version READY data was generated.

Coordinator source review shows a preparation layer without completed automatic write dispatch and with a reader tied to a next-version handoff path. Current bugfix JSON is schema-validated for coordinator receipt, not proof of automatic activation. **等待协调器接收。** No coordinator policy/state or Fix worktree was modified by QA.

The historical handoff below remains applicable; use 4e5f4a7 as the latest source and e7c62e2 as committed QA tooling. Read 06/07 for authoritative latest results.

Original baseline: `f2a5c925f0305a2e7df21f750b20bed63db40de3`.
First QA handoff: `13db6f7b18e8661b3c462f105d1f55c1a153bcea`.
Fix commit independently tested: `f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57` (business code through `6981ac8b78b2419c367e2c224979448a7010259e`).

New QA handoff SHA: resolve `git log -1 --format=%H qa/round1`; the actual resulting SHA is delivered in QA chat. Per shared contract, a report cannot embed its own eventual commit SHA.

Original DOC-001/R01-001, OCR-001/R01-002 and DOC-002/R01-003 reproducers PASS. Supplied Fix suite: 109 total, 105 PASS, 4 skipped. With independent new acceptance cases: **113 test methods, 107 PASS, 2 failing methods, 4 skipped**. Console reports 3 failure records because both file-order subtests fail within R01-005. Real offline OCR samples S00001/S00002 repeat successfully; BGE synthetic check returns 1024 dimensions. No remote corpus upload, real DB write, dependency install, default Compose startup or production-source edit by QA.

## Required next repairs

1. **DOC-003 / R01-005, P1:** local batch exception isolation. Broken first PDF prevents a later valid native PDF from being parsed; sibling remains created. Catch and record per-file failures, continue siblings, aggregate partial status and preserve progress/DB idempotency. New assertion must pass in both input orders.
2. **SEC-001 / R01-004, P2:** Windows archive reserved-path collision. ARTIFACT.BIN replaces artifact.bin's original ZIP bytes. Canonicalize reserved filenames before writes; reject collisions or otherwise guarantee immutable original bytes. Keep existing ZIP safety checks.

Exact functions, log summaries, sample IDs and acceptance conditions are in `03-bug-list.md`. Tests are `tests/test_round01_fix_acceptance.py`; helper `tests/run_round01_validation.py` can run these QA cases against an exact detached Fix checkout without merging business source into QA.

```text
python -B tests/run_round01_validation.py --source <isolated-fix-checkout> --include-source-tests
```

Use existing configured Python and optional API dependency path; TEMP/TMP must be writable. Clear MVP_TEST_PG_DSN, PARSING_TEST_PG_DSN and PARSING_RESULT_PG_DSN for synthetic runs. Windows asynchronous tests require functioning local event-loop sockets. Keep the two new failures red until fixed; do not weaken assertions. The two new passing controls cover DB-failure error visibility and retry with the same remote ID using a fake sink, not PostgreSQL.

## Feature and acceptance gates

`05-missing-features.md` now records per-GAP regression status: GAP-003/007 scoped PASS; GAP-002/005 FAIL; GAP-001/004 BLOCKED; GAP-006/008 NOT_TESTED. Fix implemented substantial code, but partial delivery is not full acceptance. Task metadata remains SQLite; confirm its relationship to the originally requested PostgreSQL metadata scope. Do not implicitly implement pending GAP-008 or MySQL/Redis integration.

`06-regression-report.md` and `07-final-summary.md` record current overall **NOT ACCEPTED**. Fix's earlier live official API/DB results were not independently reproduced by QA. No self-hosted Standard/GPU, actual Docker build or full corpus-quality PASS is granted.

Fix may repair these issues in its own worktree after reading this commit. Import only reviewed QA tests if useful; do not edit QA-owned reports/worktree. Existing safety rules remain: no push, no production data write, no corpus transmission, no implicit schema/service/dependency changes from this handoff.

Return new exact `fix/round1` SHA and updated `handoff-to-qa.md`. QA will verify in a separate validation worktree again. Initial baseline reports and official-contract references remain available in 01/02/04 reports; the latest findings and counts are this incremental handoff and 03/05/06/07.
