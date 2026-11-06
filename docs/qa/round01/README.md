# Round 01 collaboration contract

Both worktrees start at the same post-migration baseline. No remote pushes are authorized.

QA owns `01-test-baseline.md`, `02-test-cases.md`, `03-bug-list.md`, `handoff-to-fix.md`, `06-regression-report.md`, and `07-final-summary.md` in this directory. Fix owns `04-fix-plan.md`, `05-fix-report.md`, and `handoff-to-qa.md`. Do not edit the other role's reports.

Every bug needs a unique `R01-NNN` ID, sanitized reproducer, expected/actual behavior, severity, tested source commit, and regression test. Reports must not include corpus names, document contents, personal information, credentials, or absolute machine paths. Keep raw output in ignored local directories.

QA commits tests and its handoff on `qa/round1`. Fix reads that committed handoff using Git, records its SHA, and only then edits business source on `fix/round1`. Record the source commit under test inside reports; report the resulting handoff commit through Git (a report cannot embed its own eventual commit SHA).

Fix may read source and write its own analysis before handoff; it must not modify business source, dependencies, schemas, or running services before a reproducible QA handoff exists. Fix can import a QA-only test commit using a reviewed cherry-pick; never merge unrelated histories or use force operations. QA performs regression against a recorded Fix commit in its own worktree after an explicit integration step. Do not share an editing worktree.

The original corpus is read-only: use `pathlib.Path` and the process environment variable `MARKET_REGULATION_TEST_CORPUS`. Never rename, move, modify, copy into Git, or send corpus content to remote services. Use only local OCR and embedding models. Do not use production databases. Use temporary SQLite databases for smoke tests. Never run the default Compose project from a secondary worktree: it would target the original services.

Launch from each worktree using `scripts/start_agent_workspace.ps1 -Role QA` or `-Role Fix`. The launcher reads ignored shared local configuration through Git's common directory and sets process-only paths; it does not install dependencies or alter the global environment. It opens an independent Codex CLI session if available, otherwise leaves the terminal configured.

The local legacy README, selected migration notes, and local demo are intentionally excluded because they contain machine paths or case identifiers. Real documents, models, secrets, and output remain outside version control. The SQL schema is retained.
