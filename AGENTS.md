# Shared safety and role rules

Read `docs/qa/round01/README.md` before work. Never push, discard user changes, delete corpus/model/database data, hard reset, clean untracked files, rewrite history, or force-remove branches/worktrees. Do not change the original worktree during round 01.

Determine your role from `git branch --show-current`: `qa/round1` is QA and `fix/round1` is Fix. QA edits only tests, test helpers, and QA-owned reports. Fix must remain read-only for business source until a committed reproducible QA handoff exists. Fix owns only its designated reports. Do not install/upgrade dependencies or change schemas/services during preparation. Keep confidential outputs ignored and never use external OCR APIs.

Use `MARKET_REGULATION_TEST_CORPUS` with `pathlib.Path` for read-only corpus traversal. Never log original corpus paths, filenames, or body text into tracked artifacts. Keep sample identifiers anonymous. Secrets, actual corpus paths, models, and environments are local configuration and must not be committed.
