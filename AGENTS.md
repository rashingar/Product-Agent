# Product-Agent Instructions

This repository contains a repo-scoped Electronet and Skroutz product pipeline.

## Trigger

When the user sends a filled template in this exact shape:

```text
model:
url:
photos:
sections:
skroutz_status:
boxnow:
price:
```

treat it as a request to run the full pipeline.

## End-To-End Flow

1. Parse the template fields exactly as provided.
2. If `url` is an Electronet or Skroutz product URL, run:
   `python -m electronet_single_import.workflow prepare --model {model} --url "{url}" --photos {photos} --sections {sections} --skroutz-status {skroutz_status} --boxnow {boxnow} --price {price}`
   Run from `scrapper/`.
3. Read:
   - `work/{model}/llm_context.json`
   - `work/{model}/prompt.txt`
   - `work/{model}/scrape/{model}.source.json`
   - `work/{model}/scrape/{model}.report.json`
4. The assistant is the LLM stage in this workflow.
5. Using the reduced contract from `resources/prompts/master_prompt+.txt` and `resources/schemas/compact_response.schema.json`, author:
   - `work/{model}/llm_output.json`
6. The assistant must write only the LLM-owned fields:
   - `product.meta_description`
   - `product.meta_keywords`
   - `presentation.intro_html`
   - `presentation.cta_text`
   - `presentation.sections[].title`
   - `presentation.sections[].body_html`
7. Do not invent deterministic fields already owned by local code:
   - brand
   - mpn
   - manufacturer
   - name
   - meta_title
   - seo_keyword
   - category serialization
   - image paths
   - characteristics HTML
   - final CSV structure
8. After `llm_output.json` is written, run:
   `python -m electronet_single_import.workflow render --model {model}`
   Run from `scrapper/`.
9. Inspect:
   - `work/{model}/candidate/{model}.csv`
   - `work/{model}/candidate/{model}.validation.json`
   - `work/{model}/candidate/description.html`
   - `work/{model}/candidate/characteristics.html`
10. If validation fails, debug the pipeline and rerun until the output is complete and the failure cause is understood.

## Validation Expectations

- Treat `work/{model}/candidate/{model}.validation.json` as the final machine-readable health report.
- Treat `products/{model}.csv` as the final deliverable path for the user, not as a baseline for comparison.
- Prefer fixing pipeline issues over hand-editing generated output files.

## Completion Message

After the pipeline completes successfully, reply in chat with this fixed completion template first, then add any extra notes if needed:

- `Model`
- `Source URL`
- `Final CSV`
- `Validation`
- `Taxonomy`
- `Product SEO`
  - `name`
  - `meta_title`
  - `meta_description`
  - `seo_keyword`
  - `product_url`
- `Warnings`
- `Unresolved Source-Null Fields`
- `Category Filters`

Rules for the completion message:

- The `Category Filters` section must list only the category filters defined by `resources/mappings/filter_map.json` for the resolved taxonomy path.
- Do not dump the full characteristics table in place of category filters.
- Resolve each category filter value from the scraped source/spec data when possible.
- If a category filter exists in `resources/mappings/filter_map.json` but no source value exists, show it as `-`.
- The fixed completion template must always appear first in the final chat response for template-triggered pipeline runs.

## Source Scope

- This workflow is intended for Electronet and Skroutz product URLs.
- If the URL is neither an Electronet nor a Skroutz product URL, fail clearly instead of improvising a partial run.

## Working Rules

- Keep all runtime artifacts in `work/{model}/`.
- Keep source scraper artifacts in `work/{model}/scrape/`.
- Keep rendered outputs in `work/{model}/candidate/`.
- When the user asks for testing or debugging on a sample model, rerun the actual workflow instead of reasoning from stale files.
- If a bug appears on one product, fix it generically in the pipeline and verify against the active regression samples already present in `work/`.

## Execution docs policy

Use these files as follows:

### PLAN.md
Update `PLAN.md` only when one of these is true:
- a milestone status changed
- a planned step must be revised based on evidence
- a new dependency/order/risk changes the execution plan
- a milestone is split, merged, postponed, or removed

Do not rewrite `PLAN.md` wholesale.
Do not make cosmetic edits.
Treat `PLAN.md` as the milestone source of truth.

### IMPLEMENT.md
Update `IMPLEMENT.md` only when one of these is true:
- you discovered a recurring execution rule that should apply to future milestones
- validation procedure needs a permanent correction
- a repo-wide guardrail is missing and should become standing guidance
- a repeated failure suggests a durable process change

Do not update `IMPLEMENT.md` for one-off task notes.
Do not use it as a changelog.

### DOCUMENTATION.md
Update `DOCUMENTATION.md` on every milestone that changes files, directories, validation steps, or decisions.

Record:
- what was changed
- which files/directories were affected
- commands run
- validation results
- risks, blockers, or skipped items
- any follow-up needed for the next milestone

Treat `DOCUMENTATION.md` as the running engineering log.

### Priority rule
If a fact belongs to:
- execution plan/order -> `PLAN.md`
- durable operating rule -> `IMPLEMENT.md`
- milestone history/results -> `DOCUMENTATION.md`

If unsure, prefer updating `DOCUMENTATION.md` instead of changing `PLAN.md` or `IMPLEMENT.md`.

### Edit discipline
Do not create duplicate versions of these files.
Do not overwrite them wholesale.
Make targeted edits only.
