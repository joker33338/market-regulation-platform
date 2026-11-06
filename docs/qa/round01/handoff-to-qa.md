# Fix → QA: first usable upload-to-PostgreSQL version

Branch: fix/round1.
QA source: `13db6f7b18e8661b3c462f105d1f55c1a153bcea`.
Final code commit: `6981ac8b78b2419c367e2c224979448a7010259e` (includes core implementation `4767e71`).
Bug commit: `7b1a173`. Obtain the final handoff commit with `git log -1 --format=%H fix/round1`.
Use a separate validation worktree; do not modify the Fix worktree or original worktree.

The user changed this round's priority to direct official API usage and an upload → parse → database workflow;
ECS deployment is deferred. Self-hosted 4.1 Tasks remains independently supported by Mock, not live-accepted.
Official model vlm is not an assertion of Standard or a pinned cloud worker version.

Run `scripts/run_fix_regressions.ps1` with configured local interpreter and independent API dependencies.
Current result: 109 total, 105 PASS, 4 skipped, zero failures. API dependencies are optional to original CLI.
`tests.test_parsing_postgres` requires PARSING_TEST_PG_DSN pointing to approved existing review tables;
it performs no DDL and intentionally retains a synthetic success row. Separately executed 2/2 PASS.
Do not use the original MVP PG integration against a non-isolated schema.

Actual application API:
- POST /api/parse/files (raw bytes, file_name query)
- POST /api/parse/tasks (JSON file_ids, Idempotency-Key)
- GET /api/parse/tasks/{id}, /results, /errors
- POST /api/parse/tasks/{id}/resume, /cancel
- GET /api/parse/tasks/{id}/files/{file_id}/artifact

All API routes require application Bearer auth with task ownership checks; GET / only serves static upload UI.
The application Key is distinct from the official MinerU Key. Credentials remain ignored local configuration.
Launch with `scripts/start_parsing_app.ps1`; the pilot runtime is loopback-only and single-process.
Official smoke commands must only use approved synthetic data, not corpus content.

Database inspection uses existing document_review.documents/pages/blocks/tables/cells, without schema changes.
The successful HTTP smoke saved nonempty raw_text, Markdown and source metadata; 1 page and 1 block verified.
The exact synthetic task/parse IDs are in ignored reports and the Fix chat, not dependent on external credentials in Git.

Priority retest: R01-001/002/003; real page upload and role isolation; ID reuse and conflict; uncertain creation;
restart after remote IDs saved; interrupted PUT; expired download; ZIP traversal/corruption/resources;
partial success and failed database retry; PostgreSQL rollback and no duplicate records; original CLI and local parser regression.

Not complete: full-corpus recognition quality, actual self-hosted Standard, GPU/Docker deployment,
distributed task queue and GAP-008 general/Excel/table KB semantics. Preserve legal review gate and no automatic publish.
QA owns acceptance and its regression/final reports; do not mark these pending items as PASS based on Mock.
