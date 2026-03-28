# Product-Agent Engineering Log

## Current milestone
M19a completed. Next active milestone: M20 — define provider contract and registry.

## M19a — remove remaining cross-layer imports after service routing

Goal:
- remove the remaining cross-layer imports between `cli.py`, `workflow.py`, and `full_run.py` without changing commands, flags, validation behavior, artifact paths, metadata filenames, or exit semantics

Files created:
- `scrapper/electronet_single_import/input_validation.py`

Files edited:
- `scrapper/electronet_single_import/cli.py`
- `scrapper/electronet_single_import/full_run.py`
- `scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `scrapper/electronet_single_import/workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Changes:
- moved shared `FAIL_MESSAGE` and `validate_input(...)` into the neutral module `scrapper/electronet_single_import/input_validation.py`
- updated `cli.py` to import validation from the neutral module and removed its unused import of `_select_skroutz_image_backed_sections` from `full_run.py`
- updated `workflow.py` to import `FAIL_MESSAGE` and `validate_input(...)` from the neutral module instead of from `cli.py`
- updated `full_run.py` to import `FAIL_MESSAGE` from the neutral module so it remains an execution module rather than a shared constants bucket
- updated `test_skroutz_sections.py` to import `_select_skroutz_image_backed_sections` from its actual lower-layer owner, `full_run.py`
- kept `execute_full_run(...)` in `full_run.py` and left service-layer contracts unchanged

Cross-layer imports removed:
- `scrapper/electronet_single_import/cli.py` no longer imports `FAIL_MESSAGE` or `_select_skroutz_image_backed_sections` from `scrapper/electronet_single_import/full_run.py`
- `scrapper/electronet_single_import/workflow.py` no longer imports `FAIL_MESSAGE` or `validate_input(...)` from `scrapper/electronet_single_import/cli.py`

Commands run:
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content IMPLEMENT.md`
- `Get-Content scrapper/electronet_single_import/cli.py`
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/full_run.py`
- `Get-Content scrapper/electronet_single_import/services/run_service.py`
- `Get-Content scrapper/electronet_single_import/models.py`
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `rg -n "FAIL_MESSAGE|validate_input|_select_skroutz_image_backed_sections|execute_full_run|from \\.cli|from \\.full_run" scrapper/electronet_single_import -g "*.py"`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `Get-Content scrapper/electronet_single_import/tests/test_services.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_integration.py`
- `rg -n "from electronet_single_import\\.cli import _select_skroutz_image_backed_sections|from \\.full_run import FAIL_MESSAGE|from \\.cli import FAIL_MESSAGE, validate_input" scrapper/electronet_single_import/tests scrapper/electronet_single_import -g "*.py"`
- `rg -n "Current milestone|M19 —|M20|M19a" PLAN.md DOCUMENTATION.md`
- `Get-Content PLAN.md -TotalCount 80`
- `Get-Content DOCUMENTATION.md -TotalCount 120`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q electronet_single_import/tests/test_workflow.py electronet_single_import/tests/test_services.py electronet_single_import/tests/test_skroutz_integration.py electronet_single_import/tests/test_skroutz_sections.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_workflow.py electronet_single_import/tests/test_services.py electronet_single_import/tests/test_skroutz_integration.py electronet_single_import/tests/test_skroutz_sections.py` from `scrapper/` passed with `29 passed`
- `python -m pytest -q` from `scrapper/` returned `87 passed, 2 failed`
- the only accepted failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- `git status --short` showed only the expected M19a edits plus the new neutral helper module

Risks:
- the repo still carries the two pre-existing manufacturer enrichment failures
- `cli.py` still re-exports `validate_input(...)` by import for backward-compatible test and caller access, but the implementation now lives in the neutral module rather than in the CLI layer

Deferred:
- no service-layer files were changed because the boundary cleanup did not require contract adjustments
- no provider abstraction work was started; that remains M20

## M19 — route CLI through the service layer

Goal:
- refactor the CLI-facing entrypoints to call the M18 service layer instead of duplicating orchestration logic, while preserving command names, flags, exit semantics, artifact locations, metadata filenames, and provider behavior

Files edited:
- `scrapper/electronet_single_import/cli.py`
- `scrapper/electronet_single_import/full_run.py`
- `scrapper/electronet_single_import/services/run_service.py`
- `scrapper/electronet_single_import/tests/test_services.py`
- `scrapper/electronet_single_import/tests/test_workflow.py`
- `scrapper/electronet_single_import/workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Changes:
- extracted the pre-existing standalone full-run implementation into the lower-layer module `scrapper/electronet_single_import/full_run.py`
- changed `run_cli_input()` into a thin CLI adapter that builds `FullRunRequest` and calls `run_product()`
- restored `run_product()` to orchestrate below the CLI layer through `prepare_product()` and `render_product()` rather than calling anything in `cli.py`
- kept `FullRunRequest.out` so the CLI adapter can pass output-root intent into the service layer without inverting module dependencies
- routed `python -m electronet_single_import.workflow prepare` through `prepare_product()` and `python -m electronet_single_import.workflow render` through `render_product()`
- updated `prepare_workflow()` to use the extracted lower-layer executor instead of importing standalone CLI orchestration
- added focused tests that verify CLI-to-service routing and that the service layer composes stage services without importing `cli.py`

Commands run:
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content scrapper/electronet_single_import/cli.py`
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-ChildItem scrapper/electronet_single_import/services -Recurse -File | Select-Object -ExpandProperty FullName`
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `Get-Content scrapper/electronet_single_import/services/prepare_service.py`
- `Get-Content scrapper/electronet_single_import/services/render_service.py`
- `Get-Content scrapper/electronet_single_import/services/run_service.py`
- `Get-Content scrapper/electronet_single_import/services/models.py`
- `rg -n "run_cli_input\\(|prepare_workflow\\(|render_workflow\\(|prepare_product\\(|render_product\\(|run_product\\(" scrapper/electronet_single_import -g "*.py"`
- `Get-Content scrapper/electronet_single_import/services/__init__.py`
- `Get-Content scrapper/electronet_single_import/services/errors.py`
- `Get-Content scrapper/electronet_single_import/tests/test_services.py`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `rg -n "def test_.*main|cli\\.main\\(|workflow\\.main\\(" scrapper/electronet_single_import/tests -g "*.py"`
- `git status --short`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q electronet_single_import/tests/test_services.py electronet_single_import/tests/test_workflow.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_services.py electronet_single_import/tests/test_workflow.py` from `scrapper/` passed with `17 passed`
- `python -m pytest -q` from `scrapper/` returned `87 passed, 2 failed`
- the only accepted failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- no new unexpected failures were introduced by M19

Risks:
- the repo still carries the two pre-existing manufacturer enrichment failures
- standalone CLI metadata emission still remains a CLI concern because the service layer intentionally does not emit `full.run.json`

Deferred:
- no provider-contract work was started; that remains M20
- no dependency files, provider logic, README files, `AGENTS.md`, `RULES.md`, or `IMPLEMENT.md` were changed

## M18 — add service layer models/errors/wrappers

Goal:
- add a thin internal service layer around the existing prepare/render workflow stages using the M15 contract and M16/M17 stage metadata, without rerouting CLI entrypoints, changing workflow semantics, or introducing new runtime artifact or metadata filenames

Files created:
- `scrapper/electronet_single_import/services/errors.py`
- `scrapper/electronet_single_import/services/prepare_service.py`
- `scrapper/electronet_single_import/services/render_service.py`
- `scrapper/electronet_single_import/services/run_service.py`
- `scrapper/electronet_single_import/tests/test_services.py`

Files edited:
- `scrapper/electronet_single_import/services/__init__.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Service entrypoints added:
- `prepare_product(request: PrepareRequest) -> ServiceResult`
- `render_product(request: RenderRequest) -> ServiceResult`
- `run_product(request: FullRunRequest) -> ServiceResult`

Changes:
- added a small internal `ServiceError` wrapper with stable `code`, `message`, and optional `cause`
- added `prepare_product()` as a thin wrapper over `workflow.prepare_workflow()` that converts the M15 request into `CLIInput`, reuses the existing prepare-stage metadata file, and returns a `ServiceResult` with scrape/prompt artifact paths
- added `render_product()` as a thin wrapper over `workflow.render_workflow()` that reuses the existing render-stage metadata file and returns a `ServiceResult` with candidate and validation artifact paths
- added `run_product()` as an internal composition layer over `prepare_product()` then `render_product()` and kept full-run aggregation inside `ServiceResult.details`
- did not emit `full.run.json` from the new service layer
- did not modify `cli.py`
- did not modify `workflow.py`
- kept runtime behavior unchanged by leaving CLI entrypoints, workflow semantics, output locations, provider logic, and metadata filenames untouched

Commands run:
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/services/__init__.py`
- `Get-Content scrapper/electronet_single_import/services/models.py`
- `Get-Content scrapper/electronet_single_import/services/metadata.py`
- `Get-Content scrapper/electronet_single_import/models.py`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `rg -n "class CLIInput|@dataclass\\(.*CLIInput|CLIInput\\(" scrapper/electronet_single_import/models.py scrapper/electronet_single_import -g "*.py"`
- `rg --files scrapper/electronet_single_import/tests`
- `rg -n "class .*Error|ServiceError|error_code|run_status" scrapper/electronet_single_import -g "*.py"`
- `Get-Content PLAN.md -TotalCount 90`
- `Get-Content DOCUMENTATION.md -TotalCount 120`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q electronet_single_import/tests/test_services.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_services.py` from `scrapper/` passed with `6 passed`
- `python -m pytest -q` from `scrapper/` returned `84 passed, 2 failed`
- the only known failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- no new unexpected test failures were introduced by M18

Risks:
- the full suite still has the two pre-existing manufacturer enrichment failures
- the service layer currently returns aggregated full-run metadata paths through `ServiceResult.details`, not a dedicated full-run metadata artifact, by design for M18

Deferred:
- routing CLI entrypoints through the service layer remains deferred to M19
- no new runtime metadata file is emitted for `run_product()` in M18
- no workflow or CLI refactor beyond the additive service wrapper layer was performed in M18

## M17 — make CLI/workflow emit metadata

Goal:
- make the current CLI and workflow surfaces emit a structured run status and metadata file path without changing command names, flags, exit codes, workflow semantics, or existing artifact locations

Files edited:
- `scrapper/electronet_single_import/cli.py`
- `scrapper/electronet_single_import/services/metadata.py`
- `scrapper/electronet_single_import/workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Changes:
- promoted the metadata write helper into `scrapper/electronet_single_import/services/metadata.py` so both CLI and workflow can reuse the same run-status and metadata serialization path
- kept `prepare_workflow()` and `render_workflow()` additive-only by returning `run_status` alongside the existing result fields
- updated `python -m electronet_single_import.workflow prepare` to print the completed run status and the emitted `prepare.run.json` path after the existing scrape/prompt artifact lines
- updated `python -m electronet_single_import.workflow render` to print the completed run status and the emitted `render.run.json` path after the existing candidate/validation lines
- added best-effort standalone CLI metadata emission as `full.run.json` in the current CLI output model directory and surfaced its run status plus metadata path in the CLI output
- kept existing CLI flags, command names, exit-code behavior, workflow artifact locations, provider behavior, and validation semantics unchanged

Commands run:
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content scrapper/electronet_single_import/cli.py`
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/services/models.py`
- `Get-Content scrapper/electronet_single_import/services/metadata.py`
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `rg -n "metadata_path|RunStatus|prepare_workflow\\(|render_workflow\\(|Validation ok|LLM context:|Candidate CSV:" scrapper/electronet_single_import/tests scrapper/electronet_single_import`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `rg -n "M17|emit metadata|run status|metadata path" PLAN.md DOCUMENTATION.md scrapper/electronet_single_import -g "*.md" -g "*.py"`
- `rg -n "electronet_single_import\\.cli|python -m electronet_single_import\\.cli|--out" README.md scrapper/README.md scrapper/electronet_single_import/tests -g "*.md" -g "*.py"`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_workflow.py` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_workflow.py` from `scrapper/` passed with `8 passed`
- `python -m pytest -q` from `scrapper/` returned `78 passed, 2 failed`
- unchanged accepted failing tests:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- `git status --short` showed only the expected M17 edits

Risks:
- no new test failures were introduced by M17
- standalone CLI metadata now adds one new sidecar file, `full.run.json`, under the existing CLI output model directory; existing artifacts and paths remain unchanged

Deferred:
- no CLI UX redesign beyond the additive status and metadata-path lines
- service-layer wrappers and CLI routing through that layer remain deferred to M18-M19
- no test-file changes were made in M17; coverage for the new surface lines still relies on compile, existing workflow tests, and the unchanged full-suite baseline

## M16 — write structured run metadata alongside current files

Goal:
- emit structured metadata sidecar files for the current prepare and render workflow stages without changing existing artifact contents or runtime semantics

Files created:
- `scrapper/electronet_single_import/services/metadata.py`

Files edited:
- `scrapper/electronet_single_import/workflow.py`
- `scrapper/electronet_single_import/tests/test_workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Metadata files emitted by stage:
- `work/{model}/prepare.run.json`
- `work/{model}/render.run.json`

Changes:
- added metadata serialization and writing helpers in `scrapper/electronet_single_import/services/metadata.py`
- used the M15 run contract models as the metadata source shape
- wrote prepare metadata after prompt artifacts are emitted and render metadata after candidate artifacts are emitted
- added best-effort failed-run metadata emission when prepare or render raise after the model work directory is known
- kept existing workflow artifact filenames, locations, and CLI output formatting unchanged
- updated `PLAN.md` to mark M16 complete and note metadata emission

Commands run:
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/cli.py`
- `Get-Content scrapper/electronet_single_import/services/models.py`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `python -m pytest -q electronet_single_import/tests/test_workflow.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `python -m compileall scrapper/electronet_single_import`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_workflow.py` from `scrapper/` passed
- `python -m pytest -q` from `scrapper/` returned `78 passed, 2 failed`
- unchanged failing tests:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- `git status --short` confirmed the expected M16 file changes

Risks:
- no new M16 failures were introduced; the only remaining failures are the pre-existing manufacturer enrichment tests
- the full-suite pass count increased from `76` to `78` because M16 added two focused workflow metadata tests while keeping the same two known failing tests

Deferred:
- CLI-facing metadata output changes remain deferred to M17
- service-layer wrappers and routing remain deferred to later milestones
- no metadata is emitted for failures that occur before a model work directory can be determined
  - this preserves current runtime behavior while keeping metadata writing best-effort

## M15 — define run contract

Goal:
- add import-safe run contract models for future service, metadata, CLI, and API seams without changing current runtime behavior

Files created:
- `scrapper/electronet_single_import/services/__init__.py`
- `scrapper/electronet_single_import/services/models.py`

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`

Models added:
- `RunType`
- `RunStatus`
- `PrepareRequest`
- `RenderRequest`
- `FullRunRequest`
- `RunArtifacts`
- `RunMetadata`
- `ServiceResult`

Changes:
- created the new `scrapper/electronet_single_import/services/` package as import-safe package setup only
- added contract-only dataclass and enum definitions in `scrapper/electronet_single_import/services/models.py`
- included the planned `metadata_path` artifact field so M16 can emit metadata without reshaping the contract
- kept metadata-facing warnings and error fields on `RunMetadata`
- kept `ServiceResult` lean with only `run`, `artifacts`, and `details`
- updated `PLAN.md` to mark M15 complete and note that the run contract exists but is not wired into runtime behavior

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q` from `scrapper/` did not match the requested baseline and finished at `69 passed, 9 failed`
- failing tests:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
  - `test_skroutz_parser_and_deterministic_fields_cover_supported_families`
  - `test_prepare_and_render_workflow_with_skroutz_fixtures`
  - `test_143481_html_fixture_resolves_9_sections_in_stable_order`
  - `test_placeholder_urls_are_rejected_for_resolved_section_images`
  - `test_143481_rendered_description_preserves_locked_wrappers`
  - `test_taxonomy_regression_fixture_resolves_expected_categories`
  - `test_representative_taxonomy_html_fixtures_cover_supported_skroutz_combos`
- `git status --short` confirmed only the expected milestone files changed, alongside the pre-existing untracked `.claude/worktrees/`

Risks:
- the current repo test baseline does not match the milestone's expected `75 passed, 2 failed` result
- seven additional Skroutz fixture-path failures are present in `test_skroutz_integration.py`, `test_skroutz_sections.py`, and `test_skroutz_taxonomy.py`, all failing with `FileNotFoundError` against hardcoded absolute fixture paths outside the current workspace
- the two existing manufacturer enrichment failures remain in `test_manufacturer_enrichment.py`

Deferred:
- metadata emission and file writing remain deferred to M16
- runtime wiring for CLI and workflow remains deferred to later milestones
- serializers, validators, helper methods, and service wrappers remain intentionally out of scope for M15

## Pre-M15 control-doc refresh

Goal:
- align repository control documents with the post-cleanup architecture phase
- remove cleanup-only ambiguity before M15-M22
- separate milestone governance from runtime execution guidance

Files edited:
- `PLAN.md`
- `IMPLEMENT.md`
- `DOCUMENTATION.md`
- `AGENTS.md`
- `RULES.md`

Changes:
- promoted `PLAN.md` from cleanup-only framing to full active roadmap framing
- added the Phase 2 architecture milestones M15-M22
- added explicit hybrid-RAG gating
- updated `IMPLEMENT.md` to govern milestone execution for the new phase
- updated `AGENTS.md` and `RULES.md` so runtime input scope matches the actual code-supported source scope
- marked M15 as the next active milestone

Validation:
- docs-only review
- no runtime files changed
- no dependency files changed

Risks:
- none for runtime behavior; this commit changes guidance only

Deferred:
- `README.md` refresh
- any user-facing architecture overview
- milestone-specific implementation entries starting at M15

## Historical reference note
- Completed milestone entries, audit summaries, and command logs below preserve prior-state file paths intentionally.
- When older sections mention paths such as `docs/superpowers/specs/...`, `work/IMPLEMENTATION_CHECKPOINT.md`, root support-asset filenames, `RULES_legacy.md`, `master_prompt_legacy.txt`, or `scrapper/requirements.txt`, read them as historical pre-M4, pre-M5, pre-M6, or pre-M10 references unless the section explicitly states current guidance.

## Repo invariants
- Active runnable code lives under `scrapper/electronet_single_import/`.
- `products/` remains the final CSV/output area.
- `work/{model}/...` remains the runtime artifact area.
- Legacy files must be archived, not deleted casually.
- Shared support assets now live under `resources/` and remain centrally resolved through `scrapper/electronet_single_import/repo_paths.py`.

## Milestone log

### M1 — Control files and cleanup directories
Status: completed
Goal:
- add approved scaffolding directories and log the milestone without changing runtime behavior

Changes:
- created `docs/audits/`, `docs/runbooks/`, `docs/checkpoints/`, `docs/specs/`, `archive/legacy/`, `resources/mappings/`, `resources/prompts/`, `resources/schemas/`, and `resources/templates/`
- added `.gitkeep` in each created target directory because it would otherwise remain empty and would not appear in Git status
- updated `PLAN.md` to mark M1 complete and record that the control docs already existed before execution
- updated `DOCUMENTATION.md` with milestone results, commands, validation, risks, and follow-up

Validation:
- pre-creation filesystem check confirmed all nine approved target directories were absent
- post-creation filesystem check confirmed all nine approved target directories exist, each contains `.gitkeep`, and no extra contents were added
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- `PLAN.md`, `IMPLEMENT.md`, and `DOCUMENTATION.md` already existed before M1; this milestone did not recreate them
- `IMPLEMENT.md` was intentionally not edited because no new recurring execution rule was discovered
- scraper smoke validation was intentionally skipped because pathing and runtime behavior were unchanged
- current repo-root support assets remain in place as source-of-truth files
- empty directories alone would not appear in Git status without `.gitkeep`

### M2 — Repo cleanup audit
Status: completed
Goal:
- classify root files and cleanup candidates

Changes:
- created `docs/audits/repo_cleanup_audit.md`
- classified every current root-level file into `keep in root`, `move later after path centralization`, `archive as legacy`, or `uncertain`
- explicitly classified `schemas/compact_response.schema.json` as `move later after path centralization`
- explicitly classified `docs/specs/2026-03-22-pipeline-optimization-design.md` and `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md` as safe `move now` candidates
- documented evidence for non-obvious classifications from runtime path callsites and current repo docs
- updated `PLAN.md` to mark M2 complete

Validation:
- root inventory and candidate existence checks completed
- `rg` evidence sweep completed for every explicitly named file or candidate
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no requested classification was downgraded to `uncertain` due to contradictory live evidence in this pass
- `requirements.txt` remains `uncertain` and is intentionally postponed to the dependency audit milestone
- scraper smoke validation was intentionally skipped because pathing and runtime behavior were unchanged
- no files were moved or deleted in this milestone

### M3 — Path centralization
Status: completed
Goal:
- add `repo_paths.py` and remove scattered support-file path assumptions

Changes:
- created `scrapper/electronet_single_import/repo_paths.py`
- replaced these approved direct support-asset path constructions in `scrapper/electronet_single_import/utils.py`: `PRODUCT_TEMPLATE_PATH`, `PRESENTATION_TEMPLATE_PATH`, `CATALOG_TAXONOMY_PATH`, `SCHEMA_LIBRARY_PATH`, `CHARACTERISTICS_TEMPLATES_PATH`, `FILTER_MAP_PATH`, `NAME_RULES_PATH`, `DIFFERENTIATOR_PRIORITY_MAP_PATH`, `MASTER_PROMPT_PATH`, `COMPACT_RESPONSE_SCHEMA_PATH`, and `MANUFACTURER_SOURCE_MAP_PATH`
- kept the existing path constant names available from `utils.py` so downstream modules did not need churn
- updated `scrapper/electronet_single_import/tests/test_utils_support_paths.py` to validate centralized path resolution from `repo_paths.py`
- updated `PLAN.md` to mark M3 complete without changing the asset locations

Validation:
- pre-edit `rg` confirmed the approved direct support-asset callsites were in `scrapper/electronet_single_import/utils.py`
- post-edit `rg` confirmed the approved support-asset filename literals are now owned by `scrapper/electronet_single_import/repo_paths.py`
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/` passed
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- unresolved out-of-scope direct path assumptions remain in `scrapper/electronet_single_import/workflow.py` for `work/` and `products/`
- hardcoded absolute repo paths remain in some tests and were intentionally left out of scope for this milestone
- scraper smoke validation was intentionally skipped because pytest plus code inspection was sufficient for this path-only change
- no support assets were moved or renamed

### M4 — Safe docs/checkpoint moves
Status: completed
Goal:
- move the two approved non-runtime documentation and planning files out of their old locations without changing runtime behavior

Changes:
- moved the pipeline optimization design doc into `docs/specs/2026-03-22-pipeline-optimization-design.md`
- moved the implementation checkpoint into `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md`
- updated path references in `PLAN.md`, `DOCUMENTATION.md`, and `docs/audits/repo_cleanup_audit.md`

Validation:
- pre-move checks confirmed both source files existed and both destination files were absent
- post-move checks confirmed the old source files no longer exist and the new destination files do exist
- `rg` for the old paths returned no remaining references after the updates
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code was edited
- no support assets were moved
- scraper smoke validation was intentionally skipped because no runtime pathing or behavior changed
- empty directories were intentionally left in place because they may still be part of the intended docs/work scaffolding
- the remaining old-path mentions are intentionally preserved in the command log as historical execution records

### M5 — Legacy archive move
Status: completed
Goal:
- archive the two approved historical reference files without changing runtime behavior

Changes:
- moved `RULES_legacy.md` to `archive/legacy/RULES_legacy.md`
- moved `master_prompt_legacy.txt` to `archive/legacy/master_prompt_legacy.txt`
- removed `archive/legacy/.gitkeep` because the archive directory now contains real files
- updated path references in `PLAN.md`, `DOCUMENTATION.md`, `RULES.md`, `docs/audits/repo_cleanup_audit.md`, and `archive/legacy/master_prompt_legacy.txt`

Validation:
- pre-move checks confirmed both source files existed and both archive destinations were absent
- post-move checks confirmed the old source files no longer exist and the new archive paths do exist
- `rg` for the old paths returned no remaining references outside intentional historical command-log mentions
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code was edited
- no active support assets were moved
- scraper smoke validation was intentionally skipped because no runtime pathing or behavior changed
- no additional files were archived in this milestone

### M6 — Support asset relocation into `resources/`
Status: completed

### M7 — Documentation normalization
Status: completed

### M8 — Dependency audit
Status: completed

### M9 — Final health pass
Status: completed

## M6 detail
Goal:
- move the approved shared support assets into `resources/` without changing runtime behavior

Changes:
- moved `MANUFACTURER_SOURCE_MAP.json`, `catalog_taxonomy.json`, `filter_map.json`, `name_rules.json`, `differentiator_priority_map.csv`, and `taxonomy_mapping_template.csv` into `resources/mappings/`
- moved `electronet_schema_library.json`, `schema_index.csv`, and `compact_response.schema.json` into `resources/schemas/`
- moved `TEMPLATE_presentation.html`, `characteristics_templates.json`, and `product_import_template.csv` into `resources/templates/`
- moved `master_prompt+.txt` into `resources/prompts/`
- updated `scrapper/electronet_single_import/repo_paths.py` so the centralized support-asset constants resolve from `resources/`
- updated `scrapper/electronet_single_import/tests/test_utils_support_paths.py` to validate the `resources/` layout
- updated active path references in `README.md`, `RULES.md`, `AGENTS.md`, `scrapper/README.md`, `docs/audits/repo_cleanup_audit.md`, and `PLAN.md`
- removed `.gitkeep` from `resources/mappings/`, `resources/schemas/`, `resources/templates/`, and `resources/prompts/` after those directories became non-empty
- removed the old `schemas/` directory after `compact_response.schema.json` moved and the directory became empty

Validation:
- pre-move checks confirmed every approved source existed and every approved destination was absent
- post-move checks confirmed the old source paths no longer contain the moved files and the new `resources/` paths do contain them
- `rg` for the old asset paths confirmed active references were updated, with old basenames preserved only in historical records where intentionally retained
- `rg` for the new `resources/` paths confirmed runtime and active guidance ownership moved to `resources/`
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/` passed
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code outside `scrapper/electronet_single_import/repo_paths.py` was changed
- downstream runtime imports remained stable because existing constant names were preserved
- scraper smoke validation was intentionally skipped because the targeted path test, full pytest run, and code inspection were sufficient for this relocation-only milestone
- archived legacy files and historical command-log entries still contain old basenames intentionally and were not rewritten as part of M6

## M7 detail
Goal:
- normalize repo layout documentation after the M6 `resources/` move without changing runtime behavior

Changes:
- updated `README.md` to describe the post-M6 repo layout and current directory responsibilities
- created `docs/runbooks/repo-layout.md` as the practical repo-specific layout guide
- updated `PLAN.md` to mark M7 completed after the documentation normalization pass
- corrected documentation drift in active layout guidance without changing `AGENTS.md`, `RULES.md`, `IMPLEMENT.md`, or runtime code

Validation:
- `rg` over repo docs confirmed active layout guidance now points to `resources/` for shared support assets
- `rg` over repo docs confirmed `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md` and `docs/specs/2026-03-22-pipeline-optimization-design.md` are the current post-M4 locations in active guidance, with old-path mentions retained only in historical command logs
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- `AGENTS.md`, `RULES.md`, and runtime Python files were intentionally left unchanged because no broken active layout reference was found in them during M7
- scraper smoke validation was intentionally skipped because this was a docs-only milestone

## M8 detail
Goal:
- audit dependency ownership for `requirements.txt` and `scrapper/requirements.txt` without changing dependency files or runtime behavior

Changes:
- created `docs/audits/dependency_audit.md`
- recorded a side-by-side comparison of the two dependency files
- documented current live usage evidence from install instructions, control docs, and import scans
- updated `PLAN.md` to mark M8 completed with an audit-only result

Validation:
- file inspection completed for `requirements.txt` and `scrapper/requirements.txt`
- `rg` captured current references to dependency files and install commands across repo docs
- live import scans confirmed scraper/runtime imports for `httpx`, `playwright`, `beautifulsoup4`, `pypdf`, `PIL`, and `pillow_avif`, while no live `requests` import was found
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- the audit concludes that `scrapper/requirements.txt` is the only currently documented install target, but not yet the only file that appears required by live evidence
- dependency ownership remains audit-only and no dependency file was modified
- scraper smoke validation was intentionally skipped because this milestone did not change runtime behavior

## M9 detail
Goal:
- record a final post-cleanup repo health pass without changing runtime behavior

Changes:
- created `docs/audits/post_cleanup_health_pass.md`
- recorded the final repo-health summary, confirmed remaining issues, safe follow-up items, risky postponed items, and the recommended next action
- updated `PLAN.md` to mark M9 completed with an audit-only result

Validation:
- targeted `rg` searches confirmed no active guidance drift for the approved M4, M5, and M6 path changes
- targeted searches confirmed the main remaining issues are deferred items: dependency ownership, redundant `.gitkeep` files in non-empty `docs/` directories, `workflow.py` output-root assumptions, and hardcoded absolute repo paths in some tests
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no files were moved or deleted in M9
- no dependency files were changed
- no runtime code was edited
- scraper smoke validation was intentionally skipped because this was an audit-only milestone

## M10 detail
Goal:
- consolidate dependency ownership to one canonical repo-root `requirements.txt` without changing runtime behavior

Changes:
- updated repo-root `requirements.txt` to the verified canonical dependency union:
  - kept the scraper pins for `httpx`, `beautifulsoup4`, `lxml`, `playwright`, `pytest`, and `pypdf`
  - retained `pillow` and `pillow-avif-plugin` because live scraper imports still require them
  - removed `requests` because no live import evidence remained and clean-environment verification succeeded without it
- removed `scrapper/requirements.txt` after clean-environment verification succeeded
- updated `scrapper/README.md` so dependency installation now points to the canonical repo-root `requirements.txt`
- updated `PLAN.md` to mark M10 completed

Validation:
- captured the pre-edit dependency overlap between root and scraper files
- created a clean temporary virtual environment outside the repo
- installed dependencies from repo-root `requirements.txt` only
- import checks passed for `httpx`, `playwright`, `bs4`, `pypdf`, `PIL`, and `pillow_avif`
- full `python -m pytest -q` from `scrapper/` under the clean environment remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`
- active install guidance no longer depends on `scrapper/requirements.txt`

Notes:
- runtime behavior remained unchanged because no runtime code was modified
- remaining `scrapper/requirements.txt` mentions are preserved in audit/history docs as prior-state evidence
- the temporary verification environment was created outside the repo and removed after validation

## M11 detail
Goal:
- consolidate README ownership to one canonical repo-root `README.md` without changing runtime behavior

Changes:
- updated repo-root `README.md` so it now includes the current project summary, repo layout, canonical install from root `requirements.txt`, current scraper workflow commands, runtime artifact locations, output locations, and test instructions
- reduced `scrapper/README.md` to a minimal pointer to the repo-root `README.md`
- updated `PLAN.md` to mark M11 completed

Validation:
- inspected both README files and merged the still-useful scraper setup and workflow content into root `README.md`
- `rg` confirmed there is no active conflicting setup guidance between the root README and the reduced `scrapper/README.md`
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- `scrapper/README.md` was reduced to a pointer instead of being removed so existing historical or cross-doc references do not break
- no runtime code, dependency files, or project structure changed
- scraper smoke validation was intentionally skipped because this was a docs-only milestone

## M12 detail
Goal:
- remove stale old-file and old-path references from active guidance only without changing runtime behavior

Changes:
- inspected the active guidance set for stale references to pre-M4, M5, M6, and M10 file paths
- confirmed that the remaining old-file references are confined to historical milestone logs, audits, specs, and archive material
- reduced `scrapper/README.md` further so it acts only as a concise pointer to the canonical repo-root `README.md`
- updated `PLAN.md` to mark M12 completed with an active-guidance-only normalization result

Validation:
- `rg` across active guidance confirmed no stale old-file references remain in current guidance, aside from clearly historical mentions in control-doc history sections
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code, dependency files, or project structure changed
- current guidance redundancy was reduced only where it was safe to do so, without rewriting historical material
- scraper smoke validation was intentionally skipped because this was a docs-only milestone

## M13 detail
Goal:
- normalize historical old-file and old-path references in audits, specs, logs, and archive material while preserving provenance

Changes:
- added short historical-context notes to the affected audit, spec, and archived legacy files so pre-move paths are now explicitly labeled as prior-state references
- clarified in this engineering log that old file paths in completed milestone sections and command logs are intentional historical references rather than current guidance
- updated `PLAN.md` to mark M13 completed with provenance-preserving historical normalization

Validation:
- `rg` across `docs/audits/`, `docs/specs/`, `archive/legacy/`, and `DOCUMENTATION.md` confirmed the known old paths now remain either explicitly labeled as historical or already sit inside clearly historical records
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code, dependency files, or project structure changed
- provenance was preserved by adding clarification notes instead of rewriting the underlying historical outcomes
- scraper smoke validation was intentionally skipped because this was a docs-only milestone

## M14 detail
Goal:
- reduce proven runtime-code redundancy and improve concision without changing behavior

Changes:
- switched the confirmed support-asset path consumers from `utils.py` compatibility re-exports to direct imports from `scrapper/electronet_single_import/repo_paths.py`
- removed the dead `RULES_PATH` constant from `scrapper/electronet_single_import/utils.py`
- removed the one-callsite `build_model_output_dir()` wrapper and inlined its exact current behavior in `scrapper/electronet_single_import/cli.py`
- simplified `scrapper/electronet_single_import/utils.py` so it now keeps only actual utility helpers rather than mixed utility and path-ownership responsibilities
- made a small concision cleanup in `scrapper/electronet_single_import/deterministic_fields.py` by collapsing duplicate typing imports while touching the file for the path-import change

Validation:
- confirmed before editing that `RULES_PATH` had no callsites, `build_model_output_dir()` had exactly one caller in `scrapper/electronet_single_import/cli.py`, and the path-constant compatibility seam was limited to the edited runtime modules
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/` passed
- `python -m pytest -q electronet_single_import/tests/test_workflow.py electronet_single_import/tests/test_csv_writer.py electronet_single_import/tests/test_validator.py electronet_single_import/tests/test_taxonomy.py electronet_single_import/tests/test_schema_matcher.py` from `scrapper/` passed
- `python -m pytest -q electronet_single_import/tests/test_characteristics_pipeline.py electronet_single_import/tests/test_deterministic_fields.py electronet_single_import/tests/test_deterministic_fields_ice_cream_maker.py electronet_single_import/tests/test_manufacturer_enrichment_tefal.py` from `scrapper/` passed
- full `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- runtime behavior remained unchanged because this pass only reduced a dead constant, a one-callsite wrapper, and the `utils.py` path-compatibility seam
- no tests needed edits because the path values and behavior under test stayed the same
- higher-risk cleanup remains deferred, including `workflow.py` output-root refactors, hardcoded absolute repo paths in some tests, and broader utility API reshaping

## Commands run
- `rg -n "M15|Current milestone|Phase 2 milestones|M14 detail|Next active milestone" PLAN.md DOCUMENTATION.md`
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content IMPLEMENT.md`
- `git status --short`
- `Get-Content PLAN.md | Select-Object -First 90`
- `Get-Content PLAN.md | Select-Object -Skip 180`
- `Get-Content DOCUMENTATION.md | Select-Object -First 60`
- `Get-Content DOCUMENTATION.md | Select-Object -Skip 350`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q` from `scrapper/`
- pre-creation filesystem check for `docs/audits/`, `docs/runbooks/`, `docs/checkpoints/`, `docs/specs/`, `archive/legacy/`, `resources/mappings/`, `resources/prompts/`, `resources/schemas/`, and `resources/templates/`
- directory creation for the same approved target paths only when absent
- post-creation filesystem check for approved target paths, `.gitkeep` presence, and empty-directory state
- `python -m pytest -q` from `scrapper/`
- `git status --short`
- `Get-ChildItem -Force -File` at repo root
- `Get-ChildItem docs/audits`
- `Get-ChildItem docs/superpowers/specs,work`
- `rg` sweep for each explicitly named file or candidate to capture runtime code references, docs or planning references, or absence of references
- `Get-Content scrapper/electronet_single_import/utils.py`
- `Get-Content RULES.md`
- `Get-Content AGENTS.md`
- `Get-Content README.md`
- `Get-Content scrapper/README.md`
- pre-edit `rg` over `scrapper/electronet_single_import/` for approved support-asset filenames
- `Get-Content scrapper/electronet_single_import/tests/test_utils_support_paths.py`
- `Get-Content scrapper/electronet_single_import/repo_paths.py`
- post-edit `rg` over `scrapper/electronet_single_import/*.py` for approved support-asset filenames
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/`
- source/destination existence checks for the two approved M4 moves
- `Move-Item` for `docs/superpowers/specs/2026-03-22-pipeline-optimization-design.md` to `docs/specs/2026-03-22-pipeline-optimization-design.md`
- `Move-Item` for `work/IMPLEMENTATION_CHECKPOINT.md` to `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md`
- `rg` for old and new M4 paths before and after the move
- source/destination existence checks for `RULES_legacy.md` and `master_prompt_legacy.txt`
- `Move-Item` for `RULES_legacy.md` to `archive/legacy/RULES_legacy.md`
- `Move-Item` for `master_prompt_legacy.txt` to `archive/legacy/master_prompt_legacy.txt`
- `Remove-Item` for `archive/legacy/.gitkeep` after the archive directory became non-empty
- `rg` for old and new M5 legacy paths before and after the move
- pre-move source and destination existence checks for every approved M6 support asset
- `rg` for old and new M6 support-asset paths before and after the move
- `Move-Item` for the approved M6 support assets into `resources/mappings/`, `resources/schemas/`, `resources/templates/`, and `resources/prompts/`
- `Remove-Item` for `.gitkeep` in `resources/mappings/`, `resources/schemas/`, `resources/templates/`, and `resources/prompts/` after those directories became non-empty
- `Remove-Item` for the old `schemas/` directory after it became empty
- `Get-Content README.md`
- existence check for `docs/runbooks/repo-layout.md`
- `rg` over repo docs for pre-M6 support-asset paths and post-M4 moved doc paths
- `Get-Content requirements.txt`
- `Get-Content scrapper/requirements.txt`
- `rg` over repo docs for dependency-file references and install/setup commands
- live import scans for packages declared in either dependency file
- root directory inventory
- recursive search for remaining `.gitkeep` files
- targeted `rg` for pre-M4, M5, and M6 paths and known deferred runtime/path issues
- dependency overlap comparison between root and scraper requirement files
- clean temporary virtual environment creation outside the repo
- dependency install from canonical repo-root `requirements.txt`
- clean-environment import validation for `httpx`, `playwright`, `bs4`, `pypdf`, `PIL`, and `pillow_avif`
- full `python -m pytest -q` from `scrapper/` under the clean environment
- `rg` for `scrapper/requirements.txt` after consolidation
- temporary verification-environment removal
- README inspection for root and scraper README ownership
- `rg` for `scrapper/README.md` references after README consolidation
- targeted `rg` for stale old-file references across current guidance docs
- targeted `rg` for stale old-file references across `docs/audits/`, `docs/specs/`, `archive/legacy/`, and `DOCUMENTATION.md`
- `Get-ChildItem -Recurse -File scrapper/electronet_single_import`
- `rg` over `scrapper/electronet_single_import/` for `REPO_ROOT`, path constants, `build_model_output_dir`, `RULES_PATH`, and utility callsites
- `Get-Content` inspection for `scrapper/electronet_single_import/utils.py`, `repo_paths.py`, `cli.py`, `workflow.py`, `csv_writer.py`, `validator.py`, `taxonomy.py`, `schema_matcher.py`, `manufacturer_enrichment.py`, `characteristics_pipeline.py`, and `deterministic_fields.py`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_workflow.py electronet_single_import/tests/test_csv_writer.py electronet_single_import/tests/test_validator.py electronet_single_import/tests/test_taxonomy.py electronet_single_import/tests/test_schema_matcher.py` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_characteristics_pipeline.py electronet_single_import/tests/test_deterministic_fields.py electronet_single_import/tests/test_deterministic_fields_ice_cream_maker.py electronet_single_import/tests/test_manufacturer_enrichment_tefal.py` from `scrapper/`

## Open risks
- direct path assumptions may exist in multiple scraper modules
- docs may drift during file moves if not updated in the same commit
- baseline pytest failures remain in `electronet_single_import/tests/test_manufacturer_enrichment.py`
- `schema_index.csv` and `taxonomy_mapping_template.csv` have weaker direct runtime evidence than the hardcoded support assets
- `workflow.py` still contains out-of-scope `REPO_ROOT` output-root assumptions for `work/` and `products/`
- some tests still use hardcoded absolute repo paths and were intentionally deferred
- historical docs and archived legacy files intentionally retain some old support-asset basenames as prior-state evidence
- redundant `.gitkeep` files remain in non-empty `docs/audits/`, `docs/checkpoints/`, `docs/runbooks/`, and `docs/specs/` directories
- broader runtime utility/API reshaping beyond the current path-ownership seam remains intentionally deferred to avoid behavior risk

## Next approved action
No cleanup follow-up is scheduled by default. If approved, open a narrowly scoped follow-up for deferred path assumptions, test path cleanup, or redundant `.gitkeep` removal.

## 2026-03-28 - Skroutz mixed-section pipeline fix and live run for model 123456

## What changed
- fixed Skroutz section selection in `scrapper/electronet_single_import/cli.py` so prepare selects the first requested image-backed rich-description sections instead of blindly slicing the first parsed sections when text-only `one-column` blocks appear mid-stream
- added a regression test in `scrapper/electronet_single_import/tests/test_skroutz_sections.py` covering the mixed image/text section ordering case
- ran the live Product-Agent pipeline for model `123456` against the provided Skroutz product URL and authored `work/123456/llm_output.json` using the reduced LLM contract

## Files and directories affected
- `scrapper/electronet_single_import/cli.py`
- `scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `work/123456/`
- `products/123456.csv`

## Commands run
- `Get-ChildItem -Force`
- `git status --short`
- `rg --files AGENTS.md PLAN.md IMPLEMENT.md DOCUMENTATION.md`
- `python -m electronet_single_import.workflow prepare --model 123456 --url "https://www.skroutz.gr/s/60276903/tcl-smart-tileorasi-115-4k-uhd-mini-led-c7k-hdr-2025-115c7k.html" --photos 7 --sections 7 --skroutz-status 1 --boxnow 0 --price 9999` from `scrapper/`
- `rg -n "Skroutz section image could not be resolved|section image could not be resolved|section_image|section image" scrapper`
- `Get-Content` inspection for `scrapper/electronet_single_import/cli.py`, `fetcher.py`, `skroutz_sections.py`, `workflow.py`, `html_builders.py`, `work/123456/llm_context.json`, `work/123456/prompt.txt`, `work/123456/scrape/123456.source.json`, `work/123456/scrape/123456.report.json`, `resources/prompts/master_prompt+.txt`, `resources/schemas/compact_response.schema.json`, `resources/mappings/filter_map.json`, and `products/123456.csv`
- `python -m pytest scrapper/electronet_single_import/tests/test_skroutz_sections.py -q`
- `python -m pytest scrapper/electronet_single_import/tests/test_skroutz_integration.py -q`
- `python -m electronet_single_import.workflow render --model 123456` from `scrapper/`

## Validation results
- initial live `prepare` failed with `Skroutz section image could not be resolved for section 6`
- focused tests passed after the fix:
  - `scrapper/electronet_single_import/tests/test_skroutz_sections.py`: 5 passed
  - `scrapper/electronet_single_import/tests/test_skroutz_integration.py`: 7 passed
- first live `render` failed validation with `llm_intro_word_count_invalid`
- adjusted `work/123456/llm_output.json` intro length to satisfy the reduced contract
- final live `render` passed with `Validation ok: True`
- final validation warnings remained:
  - `characteristics_template_used:schema:sha1:954c8413f2da941e78f3ddce65df522654336c8c`
  - `characteristics_template_unresolved_fields:12`

## Risks, blockers, or skipped items
- the live product still relies on the characteristics template for some unresolved spec fields; this is reported but not a blocking validation failure
- no durable process-rule update was required in `IMPLEMENT.md`
- no milestone-plan change was required in `PLAN.md`

## 2026-03-28 - Portable test fixture path centralization

## What changed
- created `scrapper/electronet_single_import/tests/conftest.py` as the canonical test-layer path source of truth
- added shared pytest fixtures for `tests_root`, `fixtures_root`, `skroutz_fixtures_root`, and `products_root`
- removed machine-specific absolute path assumptions from the affected Skroutz tests and switched them to the shared fixtures
- kept the change test-only; no runtime module outside `scrapper/electronet_single_import/tests/` was edited

## Files edited
- `scrapper/electronet_single_import/tests/conftest.py`
- `scrapper/electronet_single_import/tests/test_skroutz_integration.py`
- `scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `scrapper/electronet_single_import/tests/test_skroutz_taxonomy.py`
- `DOCUMENTATION.md`

## Normalized path assumptions
- `test_skroutz_integration.py`
  - replaced hard-coded absolute `REPO_ROOT`
  - replaced per-file `FIXTURES_ROOT` and `PRODUCTS_ROOT`
  - switched fetcher and baseline-copy helpers to accept shared fixture paths
- `test_skroutz_sections.py`
  - replaced hard-coded absolute `REPO_ROOT`
  - replaced per-file `FIXTURES_ROOT` and `PRODUCTS_ROOT`
  - switched fixture fetcher helper and baseline CSV reads to shared fixture paths
- `test_skroutz_taxonomy.py`
  - replaced hard-coded absolute `REPO_ROOT`
  - replaced derived `REGRESSION_FIXTURE` and `TAXONOMY_CASES_ROOT`
  - switched taxonomy fixture reads to shared fixture paths

## Commands run
- `rg --files scrapper/electronet_single_import/tests`
- `Get-Content scrapper/conftest.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_integration.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_taxonomy.py`
- `rg -n "Users\\\\|VS_Projects|Product-Agent|__file__|parents\\[|parent.parent|fixtures|FIXTURES_ROOT|PRODUCTS_ROOT|REPO_ROOT" scrapper/electronet_single_import/tests`
- `python -m pytest -q electronet_single_import/tests/test_skroutz_integration.py` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_skroutz_sections.py` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_skroutz_taxonomy.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `python -m compileall scrapper/electronet_single_import`
- `git status --short`

## Validation results
- targeted tests after the path fix:
  - `electronet_single_import/tests/test_skroutz_integration.py`: `7 passed`
  - `electronet_single_import/tests/test_skroutz_sections.py`: `5 passed`
  - `electronet_single_import/tests/test_skroutz_taxonomy.py`: `5 passed`
- full suite after the path fix:
  - `76 passed, 2 failed`
  - remaining failures:
    - `test_enrichment_framework_supports_pdf_candidates`
    - `test_enrichment_framework_supports_html_candidates`
- `python -m compileall scrapper/electronet_single_import` succeeded
- `git status --short` showed only the expected test-layer edits and `DOCUMENTATION.md`

## Risks, blockers, or skipped items
- no runtime behavior risk is expected because the change is confined to test path resolution
- no `PLAN.md` update was needed because this is a test-baseline stabilization task rather than a milestone-order change
