# Product-Agent Plan

## Purpose

This file is the source of truth for staged repository changes.

Phase 1 cleanup milestones (M1-M14) are complete and remain preserved below as historical record.

The active phase is Phase 2: architecture foundation. This phase introduces the run contract, metadata emission, service layer, provider abstraction, and one second-provider proof before any hybrid RAG work begins.

## Current repo facts
- The active runnable code lives under `scrapper/electronet_single_import/`.
- The repo also contains shared support assets, output CSVs, runtime work artifacts, helper tools, and docs.
- Current runtime documentation treats several support files as source-of-truth inputs and now reads them from `resources/` through the centralized path layer.
- `products/` and `work/` must remain stable during early cleanup.
- `work/{model}/...` is reserved for runtime artifacts.
- Legacy historical references exist and must be archived, not deleted casually.

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

Status: active

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
- M15 — define run contract (completed; import-safe run contract models added under `scrapper/electronet_single_import/services/` and not wired into runtime behavior)
- M16 — write structured run metadata alongside current files (completed; `prepare.run.json` and `render.run.json` are now emitted under `work/{model}/`)
- M17 — make CLI/workflow emit metadata (completed; standalone CLI now emits `full.run.json`, and workflow prepare/render now surface run status plus metadata path)
- M18 — add service layer models/errors/wrappers (completed; thin internal prepare/render wrappers and full-run composition now live under `scrapper/electronet_single_import/services/` without rerouting CLI/workflow behavior or adding new runtime metadata files)
- M19 — route CLI through the service layer (completed; standalone `cli.py` is now a thin adapter over the full-run service, workflow `prepare`/`render` entrypoints call the stage service wrappers, and a lower-layer full-run executor was extracted so services no longer depend on `cli.py`)
- M19a — remove remaining cross-layer imports after service routing (completed; shared input validation now lives in a neutral module, `cli.py` no longer imports non-execution helpers from `full_run.py`, and `workflow.py` no longer imports from `cli.py` without changing runtime behavior)
- M20 — define provider contract and registry (completed; standalone typed provider models, base contract, and registry now exist under `scrapper/electronet_single_import/providers/` without wiring runtime behavior or extracting current adapters)
- M21 — extract the current primary source into a provider adapter (completed; the Electronet primary source path now runs through a concrete provider adapter while preserving the existing runtime outputs and leaving other sources on their current execution branches)
- M22 — add provider selection and one second provider proof

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
- `scrapper/`
- `tools/`
- `resources/`

### Move later after path centralization
- none; M6 moved the approved shared support assets into `resources/`

### Shared support assets under `resources/`
- `resources/mappings/`: `MANUFACTURER_SOURCE_MAP.json`, `catalog_taxonomy.json`, `filter_map.json`, `name_rules.json`, `differentiator_priority_map.csv`, `taxonomy_mapping_template.csv`
- `resources/schemas/`: `electronet_schema_library.json`, `schema_index.csv`, `compact_response.schema.json`
- `resources/templates/`: `TEMPLATE_presentation.html`, `characteristics_templates.json`, `product_import_template.csv`
- `resources/prompts/`: `master_prompt+.txt`

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

New architecture work starts at M15 and must follow the active Phase 2 rules above. Cleanup history remains preserved for auditability and should not be rewritten unless a historical correction is needed.

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
