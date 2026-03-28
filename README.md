# Product-Agent

This repository now contains two distinct workflow layers that share the same support data.

## 1. Product-Agent Repo Workflow

The repo root now holds grouped shared support assets under `resources/` plus the outputs used by the broader Product-Agent process:

- `resources/mappings/`
- `resources/schemas/`
- `resources/templates/`
- `resources/prompts/`
- `RULES.md`
- `products/`
- `work/`

This is the repo-level workflow context: taxonomy, schema, prompt, template, and output assets stay centralized at repo root, with shared support files grouped under `resources/`.

Note: the old local `scripts/` entrypoints were removed, so this root workflow is no longer driven by `scripts/build_context.py` or `scripts/render_product.py`.

## 2. Electronet Scraper Workflow

The runnable single-product Electronet scraper now lives in `scrapper/`.

Use that workflow when you want the scraper/parser/CSV pipeline itself:

- package code: `scrapper/electronet_single_import/`
- tests: `scrapper/electronet_single_import/tests/`
- usage and output details: `scrapper/README.md`

Run tests from there:

```powershell
cd scrapper
python -m pytest -q
```

## How They Relate

The scraper is scoped inside this repo and reads shared support files from `resources/`.

In practice:
- repo root = shared Product-Agent assets and outputs
- `scrapper/` = the Electronet scraping/import implementation

If you want the old script-driven Product-Agent workflow back as runnable code, it would need to be restored explicitly from git rather than inferred from the current layout.
