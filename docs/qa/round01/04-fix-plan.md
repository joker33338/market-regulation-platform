# Round 01 Fix plan

QA source: `f2a5c925f0305a2e7df21f750b20bed63db40de3`.
Reviewed QA commit: `13db6f7b18e8661b3c462f105d1f55c1a153bcea`.
Imported QA commit / repair baseline: `2e344c5`.

The QA commit adds only anonymous reports, synthetic tests and read-only helpers;
no corpus files, credentials or business modifications were included. The working
tree was clean, and git cherry confirmed the commit was not already imported.

Reproduction: `python -B -m unittest tests.test_round01_regressions tests.test_round01_integrity`:
5 tests, 4 assertion failures, matching DOC-001, OCR-001 and DOC-002.

Order: DOC-002 / R01-003 / GAP-007 (P1), OCR-001 / R01-002 and DOC-001 / R01-001 (P2),
then GAP-001–005 / MINERU-FEAT-001–005 (P1): isolated Tasks client, bounded lifecycle
and repository, authenticated API, safe artifacts and reviewed legal adapter.
GAP-006 / MINERU-FEAT-006 (P2): separate pinned GPU deployment and validation plan.

Preserve CLI, local OCR and KB release transactions. No production DDL or service
startup. Task repository validation uses separate SQLite; PostgreSQL changes remain
an explicit design/delivery boundary until an isolated database is supplied.
GAP-008 (general document/table ingestion) is pending scope confirmation.
Mock completion is not remote, GPU, or PostgreSQL acceptance.

## Confirmed scope update during implementation

The user supplied an official API credential, requested direct official calls without
server deployment, and prioritized upload through database inspection. The public
official v4 protocol is implemented as a separate Provider, not confused with
self-hosted 4.1 Tasks. The supplied local PostgreSQL test connection already has
document_review tables; reuse requires no DDL. The user authorized isolated API
dependencies and the PostgreSQL driver. Live validation uses generated synthetic
PDFs only. Final code is `6981ac8`; actual outcomes are in 05-fix-report.md.
