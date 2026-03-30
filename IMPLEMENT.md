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

## Branch execution checklist — split-LLM `intro_text` and deterministic presentation
Commit order for this branch:
1. docs-only scope commit updating `PLAN.md`, `DOCUMENTATION.md`, and `IMPLEMENT.md`
2. split the single LLM handoff into task-specific `intro_text` and `seo_meta` prepare artifacts and contracts
3. add the render compatibility phase so split task outputs are preferred while the branch transitions off the combined workflow
4. move presentation section ownership to deterministic code paths with `usable` / `weak` / `missing` quality classification and the planned fail/warn rules
5. render final description HTML in code from `intro_text`, deterministic CTA data, and cleaned deterministic presentation sections, and normalize SEO keywords in code
6. perform final cleanup by removing the legacy combined-output path and then updating remaining runtime docs, including `README.md`

Targeted test files likely to change:
- `scraper/pipeline/tests/test_llm_contract.py`
- `scraper/pipeline/tests/test_workflow.py`
- `scraper/pipeline/tests/test_services.py`
- `scraper/pipeline/tests/test_skroutz_integration.py`
- `scraper/pipeline/tests/test_skroutz_sections.py`
- `scraper/pipeline/tests/test_validator.py`

Expected runtime artifact changes:
- steady-state task-specific inputs:
  - `work/{model}/llm/task_manifest.json`
  - `work/{model}/llm/intro_text.context.json`
  - `work/{model}/llm/intro_text.prompt.txt`
  - `work/{model}/llm/seo_meta.context.json`
  - `work/{model}/llm/seo_meta.prompt.txt`
- steady-state task-specific outputs:
  - `work/{model}/llm/intro_text.output.txt`
  - `work/{model}/llm/seo_meta.output.json`
- removed legacy combined artifacts from the active workflow:
  - `work/{model}/llm_context.json`
  - `work/{model}/prompt.txt`
  - `work/{model}/llm_output.json`
- steady-state render behavior:
  - `render` reads `intro_text.output.txt` and `seo_meta.output.json` directly
  - description HTML is assembled in code from `intro_text`, deterministic CTA data, and deterministic cleaned source sections
  - section-copy generation is not part of the LLM contract

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
