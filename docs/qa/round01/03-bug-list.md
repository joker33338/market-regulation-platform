# Confirmed defects and new requirements

All execution evidence below is against `f2a5c925f0305a2e7df21f750b20bed63db40de3`. IDs DOC/OCR follow the latest request; R01 aliases preserve the shared round contract. One P1 packaging defect and two P2 parsing defects confirmed; no P0 confirmed.

## DOC-001 / R01-001 — P2 — empty text reports success

- Samples: synthetic E001 (zero bytes), E002 (whitespace); no corpus contents.
- Module/function: `qa_core/document_parsing/document_router.py::DocumentParser.parse`, native TXT/MD branch and status aggregation.
- Reproduce: `python -B -m unittest tests.test_round01_regressions.Round01Regressions.test_R01_001_empty_text_must_not_report_success tests.test_round01_regressions.Round01Regressions.test_R01_001_whitespace_text_must_not_report_success -v`.
- Expected: empty payload cannot claim successful content extraction; return explicit failed/review status or controlled rejection.
- Actual/log: both tests FAIL, `AssertionError: 'success' == 'success'`; empty page defaults to success and document inherits it.
- Confirmed root cause: native text branch creates a success PageResult without meaningful-text validation. Status aggregation only counts failed pages.
- Suggested fix: validate normalized meaningful content, preserve legitimate blank-page behavior for mixed documents, and distinguish empty extraction in quality/status.
- Acceptance: both regression assertions pass with intentional non-success behavior; valid native text and blank-page existing tests still pass.

## OCR-001 / R01-002 — P2 — Unicode image path bypasses table routing

- Sample: synthetic G001, 600×600 black grid; Unicode directory. Real S00001/S00002 emitted related read warnings in first attempt, but no claim that they contain tables.
- Module/function: `qa_core/document_parsing/document_router.py::has_grid`; image/PDF auto-routing callers.
- Reproduce: `python -B -m unittest tests.test_round01_regressions.Round01Regressions.test_R01_002_grid_detection_supports_unicode_path -v`.
- Expected: the generated grid is recognized independent of directory language.
- Actual/log: cv2 read warning, `AssertionError: False is not true`; decoded-image positive control passes using identical pixels.
- Confirmed root cause on this Windows/OpenCV environment: `cv2.imread(str(image_path))` returns None for Unicode path; helper silently returns False, losing the structure-routing hint.
- Suggested fix: read bytes with pathlib and use cv2.imdecode; preserve invalid-image handling and resource limits.
- Acceptance: regression passes including positive control; plain image and table routing tests stay green. Real tables still require quality validation.

## DOC-002 / R01-003 — P1 — missing Docker build resource

- Sample: synthetic build-context preflight B001, no corpus involved.
- Module: `Dockerfile` COPY scenarios; related `scripts/smoke_local_model.py::main` resource reference.
- Reproduce: `python -B -m unittest tests.test_round01_integrity.Round01Integrity.test_DOC_002_docker_copy_sources_exist -v`.
- Expected: every local COPY source exists in isolated checkout. Actual: missing `scenarios`; assertion reports `['scenarios'] != []`.
- Confirmed cause: Dockerfile retains resource directory reference not present in tracked baseline. This is static executable preflight evidence; Docker build itself NOT_TESTED.
- Suggestion: provide safe synthetic resources or remove obsolete packaging/demo references consistently; never use corpus data.
- Acceptance: preflight PASS, supported smoke scripts have their required inputs, isolated Docker build succeeds. Full details GAP-007 in `05-missing-features.md`.

## New MinerU feature gaps (not regressions)

Read-only source search found no MinerU client, FastAPI routes or parsing-task schema in baseline. Reproduce with source search over `qa_core`, `query.py` and `scripts`; contract production-adapter test is skipped. Each item therefore has BLOCKED product acceptance and runnable reference coverage where applicable.

| ID / priority / module | Expected / actual; suggested implementation and acceptance |
| --- | --- |
| MINERU-FEAT-001 P1 client | Expected Tasks client; absent. Implement against pinned deployed 4.1.x OpenAPI; replace skipped production-adapter test with same MockTransport scenarios against real client. No legacy Jobs fallback. |
| MINERU-FEAT-002 P1 task lifecycle/config | Expected mock/remote configuration, bounded polling/resume and no uncertain POST retries; absent. Test remote missing URL error and zero external traffic in mock mode. Reference driver covers bounded polling/resume; application config remains BLOCKED. |
| MINERU-FEAT-003 P1 FastAPI/auth | Expected upload/status/results with ownership checks; no routes. Fix chooses actual route design; add integration tests against it, including cross-user denial and stable request identity. Do not invent existing endpoints. |
| MINERU-FEAT-004 P1 persistence | Expected task/file/source/hash/result associations and recoverable failure states; existing KB tables lack remote task metadata. Review reuse/migration impact before adding schema; validate isolated PostgreSQL rollback, idempotency, retries and successful partial results. No DB writes yet. |
| MINERU-FEAT-005 P1 download safety | Expected per-file results with safe archive handling and origin-aware authentication; absent. Reference tests cover redirect key stripping, corrupt/incomplete ZIP and path traversal. Real client must enforce bounded downloads/extraction and artifact association. |
| MINERU-FEAT-006 P2 Aliyun deployment | Expected pinned 4.1 patch/image, GPU selection, healthcheck, private binding, persistent cache, injected credentials and compatibility script; current CPU Dockerfile/Compose lack MinerU. Static review followed by real ECS Standard inference required; A10 24GB capacity requires measured concurrency/peak VRAM, not an assumed guarantee. |

## Architecture risks and environment blockers

- `compose.yaml` assigns MVP_TEST_PG_DSN to the same DB as PG_DSN. Risk: variable name is not isolation evidence. No live write executed and no damage alleged. Require separate approved test database before acceptance.
- Current legal ingestion expects article structure (`service.py`, `legal_structure.py`); general-document Markdown adaptation requires explicit tests, not flattening tables or silently guessing parent structure.
- No pytest/FastAPI installed; no dependency changes authorized during preparation. Reference contracts run with existing unittest/httpx. Isolated PostgreSQL DSN and deployed MinerU endpoint absent.
- No live server/version-specific API assertions can be confirmed until Fix pins exact 4.1.x patch and records deployed OpenAPI/version.

## Independent Fix regression — updated 2026-11-07

Tested Fix commit: `f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57` (business code through `6981ac8b78b2419c367e2c224979448a7010259e`). Separate validation worktree; no changes to Fix or original worktree. Original DOC-001/R01-001, OCR-001/R01-002 and DOC-002/R01-003 regression assertions now PASS. DOC-002 PASS covers the build-context preflight; an actual Docker build remains NOT_TESTED.

### SEC-001 / R01-004 — P2 — ZIP case variant replaces the original artifact on Windows

- Sample ID: synthetic Z001, four-entry ZIP. No corpus file or external service involved.
- Failing module/functions: `qa_core/document_parsing/mineru_artifacts.py::unpack`, `store_artifacts`; downstream artifact download in `mineru_api.py::artifact`.
- Reproduce from QA branch with the configured interpreter and optional API dependencies:

  `python -B tests/run_round01_validation.py --source <isolated-fix-checkout>`

  Failing case: `Round01FixAcceptance.test_R01_004_case_variant_archive_cannot_replace_original_artifact` in `tests/test_round01_fix_acceptance.py`.
- Expected: reject case variants of reserved output names, or preserve the exact original download as `artifact.bin`.
- Actual: archive entry `ARTIFACT.BIN` is accepted. Saved `artifact.bin` contains the entry's synthetic replacement bytes rather than the downloaded ZIP. The byte equality assertion FAILS on Windows.
- Confirmed root cause: reserved-name comparison is case-sensitive, but extraction writes to a case-insensitive filesystem. `store_artifacts` first saves the ZIP as `artifact.bin`, then overwrites the same target via the archive member's case variant. Member-to-member casefold checks do not cover the reserved original-artifact file.
- Suggested fix: apply a consistent canonical-name policy to reserved paths before any write; ensure temporary and generated filenames cannot collide with accepted entries. Preserve original bytes atomically.
- Acceptance: this QA case PASS on Windows; existing traversal/duplicate/member-limit/CRC checks and ordinary download cases remain PASS. No claim of arbitrary path escape or production exploitation.

### DOC-003 / R01-005 — P1 — corrupt local file stops later valid files in a batch

- Sample IDs: synthetic L001 (broken PDF container with PDF header), L002 (valid single-page native PDF generated locally). No OCR, remote service or database required.
- Failing module/function: `qa_core/document_parsing/mineru_service.py::MinerUService._local`, exception handling in `run`.
- Reproduce using the same QA runner; failing case is `Round01FixAcceptance.test_R01_005_local_batch_bad_pdf_does_not_block_valid_sibling`.
- Expected: corrupt input has a per-file failure; valid sibling is parsed and its result retained; task reports partial success.
- Actual/log: corrupt-first order exits `_local`, leaving the valid sibling `created` with no result (`'created' != 'completed'`). Valid-first order preserves that sibling's result but incorrectly reports task `failed` instead of `partial`. Both subcases FAIL.
- Confirmed root cause: `_local` lacks a per-file exception boundary and durable per-file progress; `run` handles the exception for the whole task. Existing `DocumentParser.parse_batch` isolation is not used here.
- Suggested fix: isolate errors per file, persist sanitized error and progress, continue siblings, aggregate final status from actual per-file results. Review retry behavior so successful results/DB records are not duplicated.
- Acceptance: both input orders preserve the valid sibling and return partial; the bad file has a visible sanitized error; successful local-only tasks still work. Existing remote partial-result and DB retry fixtures remain PASS.

### Verified controls, not new bugs

`test_local_database_failure_remains_visible_on_error_api` PASS: a simulated DB failure is persisted and exposed by the shared status/errors serializer. `test_failed_database_result_can_resume_without_new_remote_task` PASS: simulated transient DB failure recovers without creating a new remote task. These tests use a fake sink, not a real PostgreSQL server.

Current totals: 5 confirmed bugs, 3 fixed on the tested commit, 2 still FAIL; cumulative repair rate 60%. The initial source findings above remain historical baseline evidence. See `06-regression-report.md` for independent execution limits.
