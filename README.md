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
- `work/{model}/llm_context.json`
- `work/{model}/prompt.txt`
- `work/{model}/scrape/{model}.source.json`
- `work/{model}/scrape/{model}.report.json`

Then run:

```bash
python -m pipeline.workflow render --model 234385
```

After `render`, inspect:
- `work/{model}/candidate/{model}.csv`
- `work/{model}/candidate/{model}.validation.json`
- `work/{model}/candidate/description.html`
- `work/{model}/candidate/characteristics.html`

## Runtime Outputs

The scraper writes runtime artifacts under `work/{model}/`, including:
- scrape-stage JSON and HTML artifacts
- prompt and LLM handoff files
- candidate CSV and validation outputs
- downloaded gallery and Besco images when present

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
