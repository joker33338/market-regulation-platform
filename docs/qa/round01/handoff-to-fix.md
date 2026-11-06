# Formal QA → Fix handoff

Baseline source SHA: `f2a5c925f0305a2e7df21f750b20bed63db40de3`; verified shared by QA and Fix before test changes.

QA handoff commit SHA: obtain the resulting commit with `git log -1 --format=%H qa/round1`; this file intentionally cannot embed its own eventual SHA (shared README rule). The exact resulting SHA is delivered in the QA chat.

Execution: original tests 63 PASS / 0 FAIL / 1 skipped; final tests 77 PASS / 4 FAIL / 2 skipped (83 total). New MinerU reference suite 13 PASS / 1 skipped product gate. Real local OCR 2/2 successful sampled pages; real local BGE 1024-dimensional output PASS. Corpus inventory 135 files, 43 PDF pages, zero exact duplicates/empty files, header verification completed. Full OCR/quality/remote MinerU acceptance not claimed.

Repair order:

1. DOC-002 / R01-003 P1 (GAP-007): Docker COPY resource missing; failing build-context preflight, actual Docker build not run. Then OCR-001 / R01-002 P2: Unicode cv2 grid read; one failing synthetic regression with decoded-pixel positive control.
2. DOC-001 / R01-001 P2: empty/whitespace success status; two failing synthetic regressions.
3. New P1 MINERU-FEAT-001 through 005: implement client, configuration/lifecycle, routes/authorization, persistence and safe downloads against verified Tasks contract. P2 FEAT-006: GPU deployment/static and remote validation. These are new feature gates, not confirmed old regressions.

Reproducers and acceptance are in `03-bug-list.md`. Run all tests with writable TEMP/TMP and explicit local interpreter. Four new failures are intentional baseline red tests; do not weaken them. Run contracts against real client once available; current reference-driver PASS is not implementation acceptance. Full fixture gaps and official links are in `04-mineru-contract-tests.md`. Incremental completeness audit is `05-missing-features.md`: GAP-001–006 are explicit new requirements, GAP-007 confirmed packaging defect, GAP-008 needs requirements confirmation. Do not automatically implement GAP-008 or MySQL/Redis integration.

Fix may enter business-source repair/development only after reading this committed handoff. Import only reviewed QA tests if needed; never change QA worktree or reports. No dependency install, service/schema changes or default Compose startup is authorized by this handoff alone; follow existing user scope and safety contract. Do not write production DB or transmit corpus to remote service. Mock data is synthetic; corpus paths/filenames/text remain local and ignored.

Deliver `fix/round1`, exact Fix SHA, and `handoff-to-qa.md`, including version pin, migration impact, actual routes and runnable commands. QA will use a separate validation worktree at that SHA, run old/new tests plus isolated PostgreSQL/API checks, and produce `06-regression-report.md`/`07-final-summary.md`. No final acceptance before that delivery; no remote GPU success claim based on Mock.
