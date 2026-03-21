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
5. Using the reduced contract from `master_prompt+.txt` and `schemas/compact_response.schema.json`, author:
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
- If `products/{model}.csv` exists, compare against it field by field.
- Call out:
  - `match`
  - `different_but_valid`
  - `missing`
  - `encoding_issue`
- Prefer fixing pipeline issues over hand-editing generated output files.

## Source Scope

- This workflow is intended for Electronet and Skroutz product URLs.
- If the URL is neither an Electronet nor a Skroutz product URL, fail clearly instead of improvising a partial run.

## Working Rules

- Keep all runtime artifacts in `work/{model}/`.
- Keep source scraper artifacts in `work/{model}/scrape/`.
- Keep rendered outputs in `work/{model}/candidate/`.
- When the user asks for testing or debugging on a sample model, rerun the actual workflow instead of reasoning from stale files.
- If a bug appears on one product, fix it generically in the pipeline and verify against the active regression samples already present in `work/`.
