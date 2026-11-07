# Round 01 acceptance summary — current result: NOT ACCEPTED

Updated 2026-11-07. This is the current acceptance decision, not a claim that all required work is complete.

Tested Fix: `f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57`.

Independent combined tests: **113 test methods; 107 PASS, 2 failing methods, 4 skipped**. The two failing methods produce 3 failure records because both file orders fail the local-batch case. Existing Fix suite alone: 105 PASS, 4 skipped. Offline real OCR samples 2/2 successful; real local BGE output 1024 dimensions. No recognition-quality percentage or remote deployment success inferred.

## Bug and feature accounting

- Confirmed bugs: 5 cumulative. Original 3 pass targeted regression; 2 remain FAIL. Repair rate: 60% (3/5). Docker closure is limited to the reported missing-resource defect, not an unexecuted build.
- Functional GAPs: 8. At least partial implementation added for 6; 2 not supplemented (deployment and pending generic-document scope).
- Feature acceptance: 2 PASS, 2 FAIL, 2 BLOCKED, 2 NOT_TESTED, under the explicit scopes in `05-missing-features.md`. Partial implementation does not count as full acceptance.

Open defects:

1. **DOC-003 / R01-005, P1:** a corrupt PDF in local mode prevents later valid files in the batch from being parsed.
2. **SEC-001 / R01-004, P2:** a case-variant ZIP member can replace the original artifact on Windows.

Both have content-free synthetic reproducers and unweakened failing assertions in `tests/test_round01_fix_acceptance.py`. The QA runner targets the detached Fix source, keeping tests and production edits separate.

## Remaining gates

Fix both failures and rerun the combined suite. Then independently validate approved isolated PostgreSQL writes/rollback/idempotency, actual remote provider contract/version and the required deployment scope. Task identity currently persists in SQLite; whether this fully satisfies the originally proposed PostgreSQL task-metadata requirement remains open. Generic/Excel/table KB semantics are still pending requirements confirmation. Browser use, actual Docker build, full-corpus OCR quality and real self-hosted Standard/GPU are NOT_TESTED.

No business source or Fix worktree edited, no schema migration, no production data write, no corpus upload, no dependency installation, no push or merge. Keep raw outputs and configuration ignored.

Next action: Fix reads the new committed `handoff-to-fix.md`, repairs R01-004/R01-005 in its own worktree, and returns a new exact Fix SHA plus updated `handoff-to-qa.md`. QA will continue independent regression before granting final acceptance.
