# v0.1 version gate — FAIL; v0.2.0 not released for development

Latest independent check, 2026-11-07:

- Local Fix tested: `4e5f4a79ae5bd9d97316916c854ce6504e447dcc`.
- Remote fix/round1 verified separately: `f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57`.
- QA test/helper commit: `e7c62e25aeace99625b5f13c164129f44a7456bb`.
- Full run: 113 methods, 107 PASS, 2 failing methods (3 failure records), 4 skips. All six FastAPI cases ran PASS in the full dependency-enabled rerun. The requested official regression script also ran, with six additional API environment skips explained in 06.
- Original R01-001/002/003 PASS. **DOC-003/R01-005 P1 and SEC-001/R01-004 P2 remain FAIL.** Three live DB tests remain environment-blocked/skipped; the fourth skip is a historical placeholder, not an actual absent-client finding.

Local 4e5f4a7 only imports QA changes; it does not repair the two issues. version-gate.json records FAIL and prohibits next-version advancement. round01/handoff.json is for current-version bug repair only. **No v0.2.0 requirements/plan/READY/development handoff is generated.** This decision is distinct from production deployment, which is NOT_TESTED.

The existing Orchestrator is a preparation layer with automatic write dispatch blocked; its reader currently expects a next-version handoff path. QA does not change that policy/path or claim an agent was awakened. **等待协调器接收。** Fix must return a new exact repair SHA and updated handoff-to-qa.md before QA can reconsider advancement.

The preceding bug/feature accounting remains: 5 bugs, 3 repaired, 2 unresolved (60%); 8 GAPs, 6 with at least partial code and 2 unsupplemented, under the scoped statuses in 05. Existing OCR/Structure/quality/client/DB/KB capabilities have been reviewed to avoid requesting their redevelopment after the gate passes.

## Prior acceptance detail (historical f7c4d75 run)

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
