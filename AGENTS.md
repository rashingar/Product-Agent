# Product-Agent Runtime Instructions

This file governs runtime and operator-facing execution behavior for the current product pipeline.

Milestone sequencing, implementation policy, and architecture rollout belong to `PLAN.md` and `IMPLEMENT.md`, not this file.

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
2. If `url` is a currently supported product URL recognized by the runtime source-detection layer, run:
   `python -m pipeline.workflow prepare --model {model} --url "{url}" --photos {photos} --sections {sections} --skroutz-status {skroutz_status} --boxnow {boxnow} --price {price}`
   Run from `scraper/`.
3. Read:
   - `work/{model}/llm/task_manifest.json`
   - `work/{model}/llm/intro_text.context.json`
   - `work/{model}/llm/intro_text.prompt.txt`
   - `work/{model}/llm/seo_meta.context.json`
   - `work/{model}/llm/seo_meta.prompt.txt`
   - `work/{model}/scrape/{model}.source.json`
   - `work/{model}/scrape/{model}.report.json`
4. The assistant is the LLM stage in this workflow.
5. Author these task outputs:
   - `work/{model}/llm/intro_text.output.txt`
   - `work/{model}/llm/seo_meta.output.json`
6. The assistant must write only the LLM-owned fields:
   - `intro_text`
   - `product.meta_description`
   - `product.meta_keywords`
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
   - CTA block text/layout
   - presentation section titles
   - presentation section body copy
   - description HTML wrappers/classes/styles
   - final CSV structure
8. Output rules:
   - `intro_text.output.txt` must contain plain Greek text only
   - exactly one paragraph
   - 100-180 words
   - no HTML
   - no bullets
   - no CTA language
   - `seo_meta.output.json` must contain only:
     - `product.meta_description`
     - `product.meta_keywords`
   - `product.meta_keywords` must be a JSON array, not CSV text
9. Deterministic render ownership:
   - presentation sections are rendered from cleaned deterministic source sections
   - source wording is preserved after sanitation
   - source titles are kept when present
   - no section-copy generation belongs to the LLM
10. After both task outputs are written, run:
   `python -m pipeline.workflow render --model {model}`
   Run from `scraper/`.
11. After a successful render publish to `products/{model}.csv`, the runtime must start the repo-native OpenCart publish phase by invoking:
   `tools/run_opencart_pipeline.sh`
   Run from repo root with `CURRENT_JOB_PRODUCT_FILE` set to the exact `products/{model}.csv` path created in the current job.
12. Inspect:
   - `work/{model}/candidate/{model}.csv`
   - `work/{model}/candidate/{model}.validation.json`
   - `work/{model}/candidate/description.html`
   - `work/{model}/candidate/characteristics.html`
   - `work/{model}/publish.run.json`
   - `work/{model}/upload.opencart.json`
   - `work/{model}/import.opencart.json`
13. If validation fails, debug the pipeline and rerun until the output is complete and the failure cause is understood.
14. If the OpenCart publish phase warns or fails after render succeeds, keep the successful render outputs, report the publish status/stage/message clearly, and debug the publish phase separately.

## Validation Expectations

- Treat `work/{model}/candidate/{model}.validation.json` as the final machine-readable health report.
- Treat `products/{model}.csv` as the final deliverable path for the user, not as a baseline for comparison.
- Treat `work/{model}/publish.run.json` as the publish-phase status report.
- Treat `work/{model}/upload.opencart.json` and `work/{model}/import.opencart.json` as the stage reports when the post-render publish phase runs.
- Do not invalidate a successful render result because the post-render publish phase warned or failed.
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

- The current runtime accepts product URLs supported by the repository's source-detection layer.
- At the time of this control-doc refresh, that includes:
  - Electronet product URLs
  - Skroutz product URLs
  - supported manufacturer product URLs already implemented in the codebase
- Do not invent unsupported provider behavior.
- Future provider expansion must follow the milestones in `PLAN.md`.

## Working Rules

- Keep all runtime artifacts in `work/{model}/`.
- Keep source scraper artifacts in `work/{model}/scrape/`.
- Keep task-specific LLM artifacts in `work/{model}/llm/`.
- Keep rendered outputs in `work/{model}/candidate/`.
- When the user asks for testing or debugging on a sample model, rerun the actual workflow instead of reasoning from stale files.
- If a bug appears on one product, fix it generically in the pipeline and verify against the committed regression samples under `scraper/pipeline/tests/fixtures/...`.

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

## Scope boundary
This file defines how to operate the current runtime.

It does not define milestone order, future provider rollout order, service-layer design, or RAG sequencing.
