# MinerU 4.1 contract QA

Reviewed 2026-11-06: [Tasks](https://opendatalab.github.io/MinerU/zh/usage/tasks/), [HTTP API](https://opendatalab.github.io/MinerU/zh/usage/http_api/), [4.1 migration](https://opendatalab.github.io/MinerU/zh/reference/migration_4_1/). These are moving docs, not evidence of a deployed patch. Fix must pin exact patch/image and compare its OpenAPI before integration acceptance.

Verified: JSON POST `/v1/tasks` returns 202; input uses `files[].file_name/bytes` and optional sha256sum. Server allocates file IDs in input order. Upload uses returned URL/headers with PUT, not a separate complete call. Query encodes task ID and retains proxy prefix; results are per-file URLs. Parent partial is supported, file partial is not. Health/tiers paths are `/v1/health` and `/v1/tiers`. Bearer credentials belong only on same-origin API calls. Legacy Upload/Jobs endpoints were removed. Native Office inputs use Flash; PDF/image Standard availability must be checked against deployment. Official docs specify no automatic create retries and bounded query/transfer waits. See linked sources for complete fields and output formats.

`tests/mineru_contract_harness.py` is a QA-only reference driver, not application implementation. It accepts only httpx.MockTransport and never contacts ECS. `tests/test_mineru_contract.py` executes 13 tests (with additional subcases), one explicit skipped production gate. Run:

```text
python -B -m unittest tests.test_mineru_contract -v
```

Covered reference scenarios: multifile create/upload/partial result; server-cache/no-upload; 400/401/429/500 and uncertain creation timeout without POST retries; invalid/oversize response propagation; PUT failures/expiry and interrupted upload followed by status query; all seven parent states; configurable polling interval, limit and task-ID resume; successful ZIP, expired download, interrupted download, corrupt ZIP, missing Markdown, traversal/absolute/drive paths; origin/redirect credential separation; health/tiers paths and URL encoding; no real transport in mock driver.

Limitations: this does not validate the absent production client, server-side manifest validation, server cache, real expiry clock, config switching, API authorization or real content quality. Fixture responses test error propagation only. Upload retry orchestration is scripted by the scenario; automatic bounded retry behavior remains an application gate. Full expected artifacts for every selected output format, hash/length checks, ZIP expansion limits, symlink rejection and resume after signed-URL refresh must be tested against the real implementation. Remote configuration missing-URL behavior is BLOCKED until config exists. pytest absent; installing it deferred per preparation rules. Tests use unittest classes compatible with future pytest collection.

No model downloaded and no real document used in HTTP fixtures. Real MinerU Standard/Aliyun GPU acceptance remains NOT_TESTED. Current Dockerfile/Compose are CPU application infrastructure, not a MinerU deployment. Review Fix's GPU Docker additions separately.
