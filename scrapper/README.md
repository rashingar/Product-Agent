# Electronet Single Product Import Scraper

Production-oriented Python 3.11 scraper for **one Electronet product URL at a time**.

It performs four explicit stages:

1. **FETCH** – `httpx` first, `Playwright` only as fallback.
2. **EXTRACT** – parse exact source content from the Electronet product page.
3. **NORMALIZE** – convert raw source content into stable internal structures.
4. **MAP TO IMPORT ROW** – build the exact OpenCart/eTranoulis CSV row in runtime template-header order.

## What it writes

For each successful run it writes a dedicated folder named after the confirmed model:

- `{out}/{model}/{model}.raw.html`
- `{out}/{model}/{model}.source.json`
- `{out}/{model}/{model}.normalized.json`
- `{out}/{model}/{model}.report.json`
- `{out}/{model}/{model}.csv`
- `{out}/{model}/gallery/{model}-1.jpg`
- `{out}/{model}/gallery/{model}-2.jpg` ... up to the downloaded gallery count
- `{out}/{model}/bescos/besco1.jpg` ... when presentation-section images exist
- `{out}/{model}/bescos/besco2.jpg` ... up to the downloaded Besco section count

Gallery image basenames follow the business rule `{model}-[index]`. Besco section images follow `besco[index]`.

## Strict boundary: scraper vs transformation

This program is a scraper and structural transformer.

It **does**:
- extract visible source data
- preserve original Greek text
- build deterministic characteristics HTML from extracted specs
- resolve taxonomy from support files
- match nearest schema from support files
- build a CSV row in the exact runtime template order
- download extracted gallery images into `{model}/gallery` using business filenames
- download presentation-section images into `{model}/bescos` when those assets exist in source

It **does not**:
- invent missing product facts
- invent technical specifications
- invent meta title / meta description / keywords
- invent marketing claims
- fabricate presentation sections when source presentation is insufficient

When truthful source presentation cannot be built safely, `description` is left empty and the report includes `description_not_built_from_source`.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## CLI

```bash
python -m electronet_single_import.cli \
  --model 234385 \
  --url "https://www.electronet.gr/oikiakes-syskeyes/plyntiria-stegnotiria/plyntiria-royhon-emprosthias-fortosis/plyntirio-royhon-samsung-bespoke-ai-wf90f09c4su4-skoyro-asimi" \
  --photos 5 \
  --sections 0 \
  --skroutz-status 1 \
  --boxnow 0 \
  --price 798 \
  --out out_dir
```

## Input rules

- `model` is mandatory and must be exactly 6 digits.
- `url` is mandatory and must point to a single Electronet product page.
- `photos` defaults to `1`.
- `sections` defaults to `0`.
- `skroutz_status` defaults to `0`.
- `boxnow` defaults to `0`.
- `price` defaults to `0`.

If the model is missing, malformed, or cannot be confirmed against the source page, the program exits with:

```text
Generation failed, provide 6-digit model
```

## Description behavior

### Mode 1 – source-backed presentation exists
If the page contains sufficient presentation content, the program:
- preserves the source claims
- preserves section order
- maps them into the locked `TEMPLATE_presentation.html` wrapper structure
- uses the required `bescoN` target image pattern, preserving the downloaded file extension when needed

### Mode 2 – presentation unavailable or insufficient
If presentation content is too weak to build a truthful block:
- `description = ""`
- CSV still writes successfully
- report warning includes `description_not_built_from_source`

## Gallery download behavior

The scraper extracts gallery image URLs from the Electronet page and then downloads them into the `gallery` folder inside the model output directory.

Rules:
- download order follows extracted gallery order
- filenames become `{model}-1.jpg`, `{model}-2.jpg`, etc. when the source is JPEG
- non-JPEG files keep the same basename but may retain a different extension, and the report records a warning
- when `--photos` is greater than the extracted gallery count, the report records a warning and CSV additional images are capped to the downloaded count

## Besco image download behavior

When `--sections` is greater than `0`, the scraper also inspects the extracted presentation blocks for source images and downloads those assets into the `bescos` folder inside the model output directory.

Rules:
- Besco filenames become `besco1.jpg`, `besco2.jpg`, etc. when the source is JPEG
- non-JPEG files keep the same basename but may retain a different extension, and the report records a warning
- Besco numbering follows the selected presentation-section order so the generated description can reference the matching downloaded files

## Taxonomy resolution

`catalog_taxonomy.json` is the primary source of truth.

Resolution signals:
- breadcrumbs
- URL path tokens
- product title clues
- section / spec label clues
- filter-map tie-breaks only

If parent or leaf cannot be resolved confidently, CSV `category` is left empty.

## Schema matching

`electronet_schema_library.json` is used to:
- compare section-title overlap
- compare spec-label overlap
- detect likely incomplete spec extraction
- produce warnings on weak matches

A weak schema match does **not** stop CSV generation.

## Output CSV behavior

Header order is read at runtime from:

- the repo-root `product_import_template.csv`

The template header order always wins.

## Safe selector extension

When adding selectors:
- prefer additive selectors over replacing existing ones
- keep visible HTML as primary source
- use JSON-LD only as secondary source
- do not move fallback heuristics into the fetch layer
- do not hardcode template header order

## Known limitations

- Electronet HTML may vary by category and campaign widgets.
- Gallery extraction is heuristic when the page does not expose a clean product-gallery container.
- `Playwright` is fallback-only and is only triggered when critical fields remain missing.
- CTA URL depends on confident taxonomy resolution.
- `seo_keyword` is only emitted when name/model slugging is unambiguous.
