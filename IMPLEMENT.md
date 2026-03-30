# Product-Agent Implementation Rules

## Source of truth

`PLAN.md` is the source of truth for milestone order, active phase scope, and milestone completion state.

`DOCUMENTATION.md` is the execution log for what changed, what was validated, and what was deferred.

## Active implementation policy
1. Work on exactly one milestone per commit.
2. Do not mix phases.
3. Preserve current outputs and runtime behavior unless the milestone explicitly changes an internal seam.
4. Do not perform opportunistic refactors.
5. Do not redesign CLI UX unless the milestone explicitly calls for it.
6. Do not introduce hybrid RAG, API, queue, or database concerns before the relevant planned milestone.
7. Prefer explicit seams and typed contracts over broad rewrites.
8. If a seam is not cleanly extractable, document the seam and stop instead of improvising a larger refactor.
9. Update docs continuously.

## Execution docs policy
For milestone commits:
1. Update `DOCUMENTATION.md` on every milestone.
2. Update `PLAN.md` only to mark milestone status and note the newly completed capability.
3. Do not edit `AGENTS.md` or `RULES.md` during normal milestones unless runtime operating behavior or accepted runtime inputs actually change.
4. Do not edit `README.md` unless user-facing setup or runtime usage actually changes.
5. Preserve prior milestone history; append or minimally update instead of rewriting historical records.
6. When active runtime paths or package names change, update current-state guidance to the new names and preserve older milestone/audit references only as labeled history.

## Binding repo constraints
- Follow `AGENTS.md` and `RULES.md`.
- Treat current runtime support assets as sensitive until path resolution is centralized.
- Treat `products/` as final deliverable storage.
- Treat `work/{model}/...` as runtime artifact storage.
- Keep committed fixtures and regression samples under `scraper/pipeline/tests/fixtures/...`; treat `work/` and `scraper/work/` as runtime/debug only.
- Do not place planning docs inside model runtime folders.
- Do not reintroduce the old script-driven workflow implicitly.

## Allowed changes in cleanup
- create docs and archive directories
- move non-runtime docs
- archive legacy files
- add `repo_paths.py`
- update file references after explicit moves
- improve documentation accuracy

## Forbidden changes during cleanup
- no business-logic redesign
- no hidden dependency migration
- no framework introduction
- no RAG implementation
- no database introduction
- no API layer introduction
- no changing output semantics without explicit milestone approval

## Phase gate for hybrid RAG

Hybrid RAG is out of scope until:
- M15-M19 are complete
- M20-M22 are complete
- at least one non-primary provider works behind the provider contract

## Required pre-edit step
Before editing:
1. restate the exact files expected to change
2. explain why those files are in scope
3. state whether runtime behavior should remain unchanged

## Required post-edit output
After editing:
1. summarize changes
2. list changed files
3. list moved files
4. list updated references
5. report validation results
6. report skipped items
7. update `DOCUMENTATION.md`

## Validation checklist
For every milestone:
1. run formatting if configured
2. run tests if available
3. run scraper smoke validation if pathing changed
4. verify moved files have no stale references
5. verify docs reference the new paths
6. record commands and outcomes in `DOCUMENTATION.md`

## Special rule for support-file moves
Before moving any current source-of-truth support file:
1. add or update `scraper/pipeline/repo_paths.py`
2. route all discovered callsites through it
3. only then move the files
4. rerun validation immediately

## Special rule for dependencies
Do not change `requirements.txt` without an explicit audit result in `docs/audits/dependency_audit.md`.
