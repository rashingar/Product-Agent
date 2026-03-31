# Product-Agent Plan

## Purpose

This file is the source of truth for staged repository changes.

Phase 1 cleanup milestones (M1-M14) are complete and remain preserved below as historical record.

Phase 2: architecture foundation is complete through M29. Phase 3 completed the split-LLM deterministic-presentation refactor through M34. Post-split execution seam cleanup and service/workflow error hardening are now complete through M36. Phase 4 remains pending.

## Current repo facts
- The active runnable code lives under `scraper/pipeline/`.
- The repo also contains shared support assets, output CSVs, runtime work artifacts, helper tools, and docs.
- Current runtime documentation treats several support files as source-of-truth inputs and now reads them from `resources/` through the centralized path layer.
- `products/` and `work/` must remain stable during early cleanup.
- `work/{model}/...` is reserved for runtime artifacts.
- Successful render publish now continues with a warning-only OpenCart image upload attempt through `tools/run_opencart_image_upload.sh`, using `CURRENT_JOB_PRODUCT_FILE` for the exact current-job published CSV path.
- Legacy historical references exist and must be archived, not deleted casually.
- Historical milestone evidence below may still mention `scrapper/` and `electronet_single_import` as pre-M23 names.

## Cleanup goals
1. Reduce root clutter safely.
2. Preserve current scraper behavior.
3. Introduce a central path layer before moving runtime support files.
4. Move non-runtime docs/checkpoints out of runtime directories.
5. Archive legacy files cleanly.
6. Categorize support assets under `resources/`.
7. Keep outputs and artifacts stable.
8. Avoid broad refactors during cleanup.

## Non-goals
- No RAG system in this cleanup plan.
- No FastAPI service introduction.
- No Postgres/pgvector migration.
- No broad business-logic rewrite.
- No pyproject migration unless explicitly scheduled later.

## Active phase

### Phase 2 — Architecture foundation

Status: completed

Goals:
1. Define a stable run contract for CLI, workflow, future API, and future job execution.
2. Emit structured metadata alongside current artifacts without changing current outputs.
3. Introduce a thin internal service layer around the current workflow.
4. Define and prove a provider abstraction with one second provider.
5. Preserve current runtime behavior while creating clean internal seams for later expansion.

Hard rule:
- Do not start hybrid RAG before:
  - M15-M19 are complete
  - M20-M22 are complete
  - at least one non-primary provider works behind the provider contract

Phase 2 milestones:
- M15 — define run contract (completed; import-safe run contract models added under `scraper/pipeline/services/` and not wired into runtime behavior)
- M16 — write structured run metadata alongside current files (completed; `prepare.run.json` and `render.run.json` are now emitted under `work/{model}/`)
- M17 — make CLI/workflow emit metadata (completed; standalone CLI now emits `full.run.json`, and workflow prepare/render now surface run status plus metadata path)
- M18 — add service layer models/errors/wrappers (completed; thin internal prepare/render wrappers and full-run composition now live under `scraper/pipeline/services/` without rerouting CLI/workflow behavior or adding new runtime metadata files)
- M19 — route CLI through the service layer (completed; standalone `cli.py` is now a thin adapter over the full-run service, workflow `prepare`/`render` entrypoints call the stage service wrappers, and a lower-layer full-run executor was extracted so services no longer depend on `cli.py`)
- M19a — remove remaining cross-layer imports after service routing (completed; shared input validation now lives in a neutral module, `cli.py` no longer imports non-execution helpers from `full_run.py`, and `workflow.py` no longer imports from `cli.py` without changing runtime behavior)
- M20 — define provider contract and registry (completed; standalone typed provider models, base contract, and registry now exist under `scraper/pipeline/providers/` without wiring runtime behavior or extracting current adapters)
- M21 — extract the current primary source into a provider adapter (completed; the Electronet primary source path now runs through a concrete provider adapter while preserving the existing runtime outputs and leaving other sources on their current execution branches)
- M22 — add provider selection and one second provider proof (completed; `full_run.py` now has a minimal private provider-selection seam, Electronet remains the only production-selected provider, and a fixture-backed `SkroutzProvider` is proven through test-injected routing without changing default Skroutz runtime behavior)
- M23 — rename the active runtime package and directory layout (completed; the runtime now lives under `scraper/pipeline`, active invocation runs from `scraper/` via `python -m pipeline.workflow ...` and `python -m pipeline.cli ...`, and runtime behavior remains unchanged)
- M24 — stabilize the post-workdir test baseline (completed; touched workflow and Skroutz tests now read committed golden CSV baselines from `scraper/pipeline/tests/fixtures/golden_outputs/skroutz/` and assert the live render contract where candidate bundles can exist while publish is skipped on failed validation)
- M25 — route Skroutz through the provider seam in production (completed; supported Skroutz product URLs now select `SkroutzProvider` through `_resolve_provider_for_source(...)`, the provider supports live fetch plus fixture overrides, and prepare/render artifact shapes plus validation semantics remain unchanged)
- M26 — migrate supported manufacturer flows behind provider adapters (completed; the current supported manufacturer runtime flow now selects `ManufacturerTefalProvider` through `_resolve_provider_for_source(...)`, the provider preserves the existing HTTPX-then-Playwright fetch order plus optional fixtures, and prepare/render contracts remain unchanged while manufacturer enrichment regressions are resolved)
- M27 — retire legacy runtime source branches and close the migration phase (completed; `execute_full_run(...)` now fails fast when a supported source lacks a provider instead of falling back to legacy fetch/parser branches, the remaining dead pre-migration source-routing duplication in `full_run.py` was removed, and runtime tests now lock provider-based execution as the single active internal seam for supported sources)
- M28 — make services the true owner of prepare/render orchestration (completed; the real prepare/render orchestration now lives under `scraper/pipeline/services/prepare_execution.py` and `scraper/pipeline/services/render_execution.py`, `prepare_service.py` and `render_service.py` call those service-owned executors directly without importing `workflow.py`, and `workflow.py` remains a thin CLI/adapter layer with unchanged runtime behavior)
- M29 — make `run_service` the true owner of full-run orchestration (completed; the real full-run composition now lives under `scraper/pipeline/services/run_execution.py`, `run_service.py` calls that service-owned executor directly, and CLI/workflow adapter behavior plus runtime outputs remain unchanged)

### Phase 3 — Split-LLM `intro_text` and deterministic presentation refactor

Status: completed

Goals:
1. Replace the current single-prompt LLM handoff with two task-specific LLM tasks: `intro_text` and `seo_meta`.
2. Remove presentation section title/body generation from the LLM contract.
3. Build deterministic presentation sections from `presentation_source_sections` while preserving source titles when present and only cleaning/sanitizing wording.
4. Render the final description HTML in code from LLM `intro_text`, deterministic CTA data, and cleaned deterministic source sections while keeping wrappers, classes, and styles code-owned.
5. Add a render-side compatibility phase during the transition and then remove it in final cleanup.
6. Enforce the planned section failure policy and SEO keyword normalization rules in code.

Hard rules:
- Do not move HTML wrappers, CTA blocks, image wiring, or section layout ownership back to the LLM.
- Do not silently continue when `presentation_source_sections` are absent entirely; that case must hard fail.
- Do not remove the compatibility path until regression coverage proves the split-output path is stable.

Phase 3 milestones:
- M30 — split the LLM contract and prepare artifacts (completed; `prepare` now writes task-specific artifacts under `work/{model}/llm/` for `intro_text` and `seo_meta`, emits `task_manifest.json` as the primary handoff index, constrains `intro_text` to plain-text one-paragraph output, and defines `seo_meta` as `meta_description` plus structured `meta_keywords`)
- M31 — add render compatibility for split outputs and legacy combined output (completed; the branch transition proved `render` against both split outputs and the temporary combined fallback before final cleanup removed the legacy path)
- M32 — build deterministic presentation sections and section-quality policy (completed; `presentation_source_sections` are now classified as `usable`, `weak`, or `missing`; missing source sections hard fail; weak sections or exactly one missing requested section warn and continue with fewer sections; source wording is preserved apart from cleaning/sanitization; and source titles are retained when present)
- M33 — render final description HTML and SEO normalization in code (completed; description HTML is now assembled in code from plain-text `intro_text`, deterministic CTA data, and cleaned deterministic source sections; wrappers/classes/styles remain code-owned; keyword normalization in code enforces brand/model presence while collapsing duplicates and singular/plural variants; and section-image mapping stays tied to original source order when weak sections are skipped)
- M34 — final cleanup of legacy combined artifacts and docs (completed; the legacy single-prompt artifact contract was removed from steady-state prepare/render expectations, `render` no longer depends on combined `llm_output.json`, obsolete combined prompt/schema assets were retired, and user-facing/runtime docs now describe the final split-task contract)

### Post-split execution seam cleanup

Status: completed

Goals:
1. Finish the prepare/render execution seam after the split-LLM refactor.
2. Make `prepare` truly scrape-only plus LLM-handoff-only.
3. Keep `render` as the sole owner of candidate CSV generation, validation artifacts, description HTML, characteristics HTML, and publish copy.
4. Remove the remaining active-path dependence on `execute_full_run(...)` for prepare-stage behavior.
5. Reduce or retire `full_run.py` from the active prepare path without broadening scope into provider bootstrap, service error taxonomy, or CI.

Hard rules:
- Do not reintroduce combined LLM artifacts or change the split-task `intro_text` / `seo_meta` contract.
- Do not let `prepare` write candidate or publish artifacts in steady state.
- Do not broaden this cleanup into provider bootstrap, service error taxonomy, or CI work.

Post-split milestone:
- M35 — clean up the prepare/render execution seam (completed; `scraper/pipeline/prepare_stage.py` is now the scrape-only execution core, `scraper/pipeline/services/prepare_execution.py` writes scrape plus split-task handoff artifacts without routing through `execute_full_run(...)`, `prepare` no longer writes a scrape-stage CSV, `render` remains the sole owner of candidate and publish outputs, and `scraper/pipeline/full_run.py` is reduced to a thin compatibility wrapper for explicit direct callers)

Implementation substeps:
1. Extract or introduce a scrape-only execution seam that returns the parsed, taxonomy, normalized, and report data needed by `prepare` without writing candidate-stage outputs.
2. Re-route `scraper/pipeline/services/prepare_execution.py` to that scrape-only seam and remove its active-path dependency on `execute_full_run(...)`.
3. Remove scrape-stage CSV generation and any other candidate/publish side effects from the active prepare path while preserving scrape artifacts under `work/{model}/scrape/` and task handoff artifacts under `work/{model}/llm/`.
4. Keep `scraper/pipeline/services/render_execution.py` as the sole owner of candidate CSV generation, validation reports, `description.html`, `characteristics.html`, and publish-copy to `products/`.
5. Narrow `scraper/pipeline/full_run.py` to explicit full-run composition only, or retire it from the active prepare path entirely, without changing supported-provider behavior.

Acceptance criteria:
1. `python -m pipeline.workflow prepare ...` writes only scrape artifacts and LLM handoff artifacts under `work/{model}/`; it does not write `work/{model}/scrape/{model}.csv`, candidate artifacts, or publish outputs.
2. `scraper/pipeline/services/prepare_execution.py` no longer imports or depends on `execute_full_run(...)` for active prepare behavior.
3. `python -m pipeline.workflow render --model {model}` remains the sole owner of `work/{model}/candidate/{model}.csv`, `work/{model}/candidate/{model}.validation.json`, `work/{model}/candidate/description.html`, `work/{model}/candidate/characteristics.html`, and `products/{model}.csv`.
4. Split-task `intro_text` / `seo_meta` inputs and outputs, supported-provider behavior, and render validation semantics remain unchanged.
5. `scraper/pipeline/full_run.py` is either reduced to an explicit full-run wrapper over prepare plus render or otherwise removed from the active prepare path, with no new scope added in provider bootstrap, service error taxonomy, or CI.

### Service/workflow error taxonomy hardening

Status: completed

Goals:
1. Replace exception-type-name service errors with stable semantic service codes.
2. Keep low-level exception mapping at the service boundary without introducing a large exception hierarchy.
3. Make workflow exit behavior explicit and stable across prepare/render failure modes.
4. Store stable semantic error codes in run metadata instead of raw exception type names.

Hard rules:
- Keep user-facing CLI/workflow error messages readable.
- Do not broaden this work into provider bootstrap, CI, or a larger exception hierarchy redesign.
- Keep fetch/normalize behavior inside providers unchanged.

Milestone:
- M36 — add stable service error taxonomy and workflow exit mapping (completed; `scraper/pipeline/services/errors.py` now defines stable semantic error codes plus a boundary mapper, prepare/render/full-run services wrap low-level failures into those codes, workflow exit behavior is driven by an explicit code-to-exit matrix, and prepare/render metadata now persist stable semantic `error_code` values including validation failures)

### Phase 4 — Hybrid RAG foundation

Status: pending

Entry handoff:
1. Complete M36 before starting any hybrid RAG work.
2. Keep provider-based execution under `scraper/pipeline/` as the single internal seam for supported sources.
3. Preserve current CLI/workflow commands, accepted inputs, artifact paths, and validation semantics while future retrieval work layers above that seam.
4. Preserve the completed split-task steady-state contract while starting retrieval-layer work; do not reintroduce combined LLM artifacts.
5. Do not reintroduce source-specific routing below the provider boundary.

## Root policy
### Keep in root
- `.claude/`
- `.gitignore`
- `AGENTS.md`
- `RULES.md`
- `README.md`
- `PLAN.md`
- `IMPLEMENT.md`
- `DOCUMENTATION.md`
- `requirements.txt`
- `products/`
- `work/`
- `scraper/`
- `tools/`
- `resources/`

### Move later after path centralization
- none; M6 moved the approved shared support assets into `resources/`

### Shared support assets under `resources/`
- `resources/mappings/`: `MANUFACTURER_SOURCE_MAP.json`, `catalog_taxonomy.json`, `filter_map.json`, `name_rules.json`, `differentiator_priority_map.csv`, `taxonomy_mapping_template.csv`
- `resources/schemas/`: `electronet_schema_library.json`, `schema_index.csv`
- `resources/templates/`: `TEMPLATE_presentation.html`, `characteristics_templates.json`, `product_import_template.csv`
- `resources/prompts/`: `intro_text_prompt.txt`, `seo_meta_prompt.txt`

### Move now
- none; M4 completed the two previously approved safe documentation/planning moves

### Archive
- none; M5 archived the two approved legacy files under `archive/legacy/`

## Planned milestones
## Phase 1 — Cleanup history
### M1 — Create control files and cleanup directories
Status: completed
Evidence:
- `PLAN.md`, `IMPLEMENT.md`, and `DOCUMENTATION.md` already existed before M1 execution, so this milestone was limited to approved scaffolding directories and control-doc logging.

Created:
- `docs/audits/`
- `docs/runbooks/`
- `docs/checkpoints/`
- `docs/specs/`
- `archive/legacy/`
- `resources/mappings/`
- `resources/prompts/`
- `resources/schemas/`
- `resources/templates/`

### M2 — Audit current layout
Status: completed
Evidence:
- Created `docs/audits/repo_cleanup_audit.md` with one-row-per-root-file classifications and explicit non-root cleanup candidates.
- Left `requirements.txt` as `uncertain` pending the later dependency audit because live evidence does not yet prove repo-root ownership.

### M3 — Centralize support-file lookup
Status: completed
Evidence:
- Added `scrapper/electronet_single_import/repo_paths.py` to centralize approved support-asset locations without moving any assets.
- Routed the existing support-asset path hub in `scrapper/electronet_single_import/utils.py` through the new module while preserving downstream imports.

### M4 — Move safe docs/checkpoint files
Status: completed
Evidence:
- Moved the pipeline optimization design doc into `docs/specs/2026-03-22-pipeline-optimization-design.md`.
- Moved the implementation checkpoint into `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md`.

### M5 — Archive legacy files
Status: completed
Evidence:
- Moved `RULES_legacy.md` to `archive/legacy/RULES_legacy.md`.
- Moved `master_prompt_legacy.txt` to `archive/legacy/master_prompt_legacy.txt`.

### M6 — Move shared support assets into `resources/`
Status: completed
Evidence:
- Moved the approved shared support assets into `resources/mappings/`, `resources/schemas/`, `resources/templates/`, and `resources/prompts/`.
- Updated `scrapper/electronet_single_import/repo_paths.py` so centralized runtime path resolution now targets the new `resources/` locations without changing loader semantics.

### M7 — Normalize documentation
Status: completed
Evidence:
- Updated `README.md` to describe the post-M6 `resources/`, `docs/`, `archive/`, `work/`, and `products/` layout accurately.
- Created `docs/runbooks/repo-layout.md` as the repo-specific layout guide for future operators and Codex runs.

### M8 — Audit dependency strategy
Status: completed
Evidence:
- Recorded `docs/audits/dependency_audit.md` with a side-by-side comparison of `requirements.txt` and `scrapper/requirements.txt`.
- Kept dependency ownership audit-only in M8 and deferred any merge, move, or modernization work pending explicit follow-up approval.

### M9 — Final health pass
Status: completed
Evidence:
- Recorded `docs/audits/post_cleanup_health_pass.md` with the final repo-health summary, remaining issues, safe follow-up items, risky postponed items, and the recommended next action.
- Kept M9 audit-only with no file moves, dependency changes, or runtime-code changes.

### M10 — Consolidate canonical root requirements
Status: completed
Evidence:
- Promoted repo-root `requirements.txt` to the canonical dependency file using the verified live-needed union of root and scraper dependencies.
- Removed `scrapper/requirements.txt` only after clean-environment install, import checks, and full pytest validation succeeded against the canonical root file.

### M11 - Consolidate canonical root README
Status: completed
Evidence:
- Merged the still-useful scraper setup and workflow guidance into the repo-root `README.md`.
- Reduced `scrapper/README.md` to a minimal pointer so the root README is the single canonical README entrypoint.

### M12 - Purge stale references from active guidance
Status: completed
Evidence:
- Verified that stale old-file references now remain only in historical milestone logs, audits, specs, and archive material rather than active current guidance.
- Reduced `scrapper/README.md` further so it acts only as a concise pointer to the canonical repo-root `README.md`.

### M13 - Normalize historical references with provenance preserved
Status: completed
Evidence:
- Added short historical-context notes to the affected audits, spec, archived legacy files, and `DOCUMENTATION.md` so pre-move paths are explicitly labeled as prior-state references.
- Preserved the underlying milestone outcomes and archived text rather than rewriting history into current guidance.

### M14 - Runtime-code redundancy reduction and concision pass
Status: completed
Evidence:
- Moved the confirmed support-asset path consumers to direct imports from `scrapper/electronet_single_import/repo_paths.py`, removing the remaining `utils.py` compatibility-reexport seam.
- Removed the dead `RULES_PATH` constant and the one-callsite `build_model_output_dir()` wrapper without changing the known pytest baseline.

## Phase transition note

Cleanup is complete through M14.

New implementation work starts at M30 and now continues through the completed post-split M36 error-hardening milestone before Phase 4. Cleanup history remains preserved for auditability and should not be rewritten unless a historical correction is needed.

## Validation rules
After each milestone:
1. run repo-appropriate tests
2. run scraper smoke checks if path behavior changed
3. confirm no source-of-truth asset path is broken
4. update `DOCUMENTATION.md`

## Stop conditions
Stop and document before proceeding if:
- runtime paths break
- tests fail unexpectedly
- a source-of-truth file has unclear ownership
- dependency-file purpose is uncertain
