# Product-Agent Implementation Rules

## Source of truth
`PLAN.md` is the source of truth for milestone order and scope.

## Required operating behavior for Codex
1. Work on exactly one milestone per commit.
2. Do not expand scope.
3. Preserve behavior unless the milestone explicitly changes structure.
4. Do not perform opportunistic refactors.
5. Do not delete uncertain files.
6. Prefer archive over deletion.
7. Prefer path centralization before file movement.
8. Update docs continuously.

## Binding repo constraints
- Follow `AGENTS.md` and `RULES.md`.
- Treat current runtime support assets as sensitive until path resolution is centralized.
- Treat `products/` as final deliverable storage.
- Treat `work/{model}/...` as runtime artifact storage.
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
1. add or update `scrapper/electronet_single_import/repo_paths.py`
2. route all discovered callsites through it
3. only then move the files
4. rerun validation immediately

## Special rule for dependencies
Do not change `requirements.txt` or `scrapper/requirements.txt` without an explicit audit result in `docs/audits/dependency_audit.md`.