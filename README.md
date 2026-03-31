# Product-Agent

Repo-scoped Electronet and Skroutz product pipeline with shared support assets, runtime workspaces, and final CSV outputs.

## Repo Layout

- `resources/` holds shared support assets:
  - `resources/mappings/` for taxonomy, filter, naming, and manufacturer mapping data
  - `resources/schemas/` for schema libraries and response schemas
  - `resources/templates/` for CSV and HTML templates
  - `resources/prompts/` for prompt source files
- `scraper/` holds the runnable product pipeline and its tests
- `work/{model}/` is reserved for runtime artifacts only
- `products/` is the final deliverable/output area
- `docs/` holds active project documentation, audits, specs, checkpoints, and runbooks
- `archive/` holds historical or no-longer-active reference material

For the repo-specific layout rules, see `docs/runbooks/repo-layout.md`.

## Install

Create the environment from repo root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Current Scraper Workflow

Run the current prepare/render workflow from `scraper/`.

Prepare:

```bash
cd scraper
python -m pipeline.workflow prepare \
  --model 234385 \
  --url "https://www.electronet.gr/..." \
  --photos 5 \
  --sections 0 \
  --skroutz-status 1 \
  --boxnow 0 \
  --price 798
```

After `prepare`, inspect:
- `work/{model}/scrape/{model}.raw.html`
- `work/{model}/scrape/{model}.source.json`
- `work/{model}/scrape/{model}.normalized.json`
- `work/{model}/scrape/{model}.report.json`
- `work/{model}/llm/task_manifest.json`
- `work/{model}/llm/intro_text.context.json`
- `work/{model}/llm/intro_text.prompt.txt`
- `work/{model}/llm/seo_meta.context.json`
- `work/{model}/llm/seo_meta.prompt.txt`

Prepare is scrape-only in the steady-state workflow:
- it writes scrape artifacts under `work/{model}/scrape/`
- it writes split-task handoff artifacts under `work/{model}/llm/`
- it does not write candidate CSVs, validation reports, description HTML, characteristics HTML, or publish outputs

The LLM stage now writes:
- `work/{model}/llm/intro_text.output.txt`
- `work/{model}/llm/seo_meta.output.json`

Rules:
- `intro_text` is plain Greek text only, one paragraph, 120-180 words, with no HTML, bullets, or CTA language.
- `seo_meta.output.json` contains only `product.meta_description` and `product.meta_keywords`.
- `product.meta_keywords` is structured JSON, not CSV text.
- Presentation section titles/body copy are not LLM outputs.

Then run:

```bash
python -m pipeline.workflow render --model 234385
```

After `render`, inspect:
- `work/{model}/candidate/{model}.csv`
- `work/{model}/candidate/{model}.normalized.json`
- `work/{model}/candidate/{model}.validation.json`
- `work/{model}/candidate/description.html`
- `work/{model}/candidate/characteristics.html`
- `products/{model}.csv` when validation passes
- `work/{model}/publish.run.json` when the post-render publish phase runs
- `work/{model}/upload.opencart.json` when the publish phase reaches image upload
- `work/{model}/import.opencart.json` when the publish phase reaches CSV import

On successful validation, `render` publishes `products/{model}.csv`, completes the render phase, and then starts a separate publish phase through `tools/run_opencart_pipeline.sh`. The publish wrapper runs image upload first and CSV import second, using `CURRENT_JOB_PRODUCT_FILE` for the exact current-job published CSV path. Render success remains render-only; publish status, stage, message, and report paths are reported separately.

## Deterministic Description Rendering

Render assembles the final `description` HTML in code from:
- LLM `intro_text`
- deterministic CTA data
- cleaned deterministic presentation source sections

Behavior:
- wrappers, classes, styles, CTA layout, and image wiring are code-owned
- source section titles are preserved when present
- source wording is preserved after sanitation; render does not rewrite or summarize section copy
- no section-copy LLM generation is part of the steady-state workflow

Section policy:
- if presentation source sections are missing entirely and sections were requested, render fails
- if usable section count is `0` and sections were requested, render fails
- if sections are weak or exactly one requested section is missing, render warns and continues with fewer sections

SEO policy:
- `meta_description` comes from `seo_meta.output.json`
- `meta_keywords` comes from `seo_meta.output.json`
- render normalizes meta keywords in code so brand/model are always present and duplicate singular/plural variants are collapsed

## Runtime Outputs

The scraper writes runtime artifacts under `work/{model}/`, including:
- scrape-stage JSON, HTML, and downloaded source assets under `work/{model}/scrape/`
- task-specific LLM handoff files under `work/{model}/llm/`
- candidate CSV, normalized candidate JSON, validation outputs, and rendered HTML only under `work/{model}/candidate/`
- downloaded gallery and Besco images when present under the scrape stage

Final deliverable CSVs remain under `products/`.

## Tests

Run the test suite from `scraper/`:

```powershell
cd scraper
python -m pytest -q
```

## Notes

- Shared support files are read from `resources/`.
- The old local `scripts/` entrypoints are no longer the active workflow.
- If you want the old script-driven workflow back as runnable code, it would need to be restored explicitly from git rather than inferred from the current layout.
