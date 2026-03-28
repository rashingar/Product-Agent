# Product-Agent Cleanup Plan

## Purpose
This file is the source of truth for the staged cleanup and reorganization of the current Product-Agent repository.

## Current repo facts
- The active runnable code lives under `scrapper/electronet_single_import/`.
- The repo also contains shared support assets, output CSVs, runtime work artifacts, helper tools, and docs.
- Current runtime documentation says several support files are treated as source-of-truth inputs and are currently read from repo root.
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
- `requirements.txt` (until audited)
- `products/`
- `work/`
- `scrapper/`
- `tools/`

### Move later after path centralization
- `MANUFACTURER_SOURCE_MAP.json`
- `catalog_taxonomy.json`
- `filter_map.json`
- `name_rules.json`
- `differentiator_priority_map.csv`
- `taxonomy_mapping_template.csv`
- `electronet_schema_library.json`
- `schema_index.csv`
- `schemas/compact_response.schema.json`
- `TEMPLATE_presentation.html`
- `characteristics_templates.json`
- `product_import_template.csv`
- `master_prompt+.txt`

### Move now
- `docs/superpowers/specs/2026-03-22-pipeline-optimization-design.md`
- `work/IMPLEMENTATION_CHECKPOINT.md`

### Archive
- `RULES_legacy.md`
- `master_prompt_legacy.txt`

## Planned milestones
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
Create `docs/audits/repo_cleanup_audit.md` and classify all root files.

### M3 — Centralize support-file lookup
Add `scrapper/electronet_single_import/repo_paths.py` and route all support-file access through it.

### M4 — Move safe docs/checkpoint files
Move:
- `docs/superpowers/specs/2026-03-22-pipeline-optimization-design.md`
- `work/IMPLEMENTATION_CHECKPOINT.md`

### M5 — Archive legacy files
Move:
- `RULES_legacy.md`
- `master_prompt_legacy.txt`

### M6 — Move shared support assets into `resources/`
Move support files only after M3 is complete.

### M7 — Normalize documentation
Update:
- `README.md`
- `RULES.md`
- `AGENTS.md`
- `docs/runbooks/repo-layout.md`

### M8 — Audit dependency strategy
Inspect root vs scraper requirements before any dependency-file move.

### M9 — Final health pass
Create `docs/audits/post_cleanup_health_pass.md`.

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
