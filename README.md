# Product-Agent

This repo now supports a lower-token workflow by default.

The old workflow asked the model to read a very large prompt, restate HTML and CSV rules in prose, and generate deterministic fields that local code can build faster and cheaper.

The new workflow moves deterministic work into local scripts and keeps the model focused on the small set of fields that actually benefit from generation.

## New workflow

1. Build compact context from the input and, when possible, scrape the exact Electronet page.
2. Send the generated prompt to the model.
3. Save the model JSON response locally.
4. Render CSV, HTML blocks, and chat output with the local renderer.

## Commands

### 1. Build context and prompt

```powershell
python scripts/build_context.py `
  --model 233541 `
  --url "https://www.electronet.gr/oikiakes-syskeyes/psygeia-katapsyktes/psygeia-ntoylapes/psygeio-ntoylapa-lg-gsgv80pyll-asimi-e" `
  --photos 6 `
  --sections 5 `
  --skroutz-status 1 `
  --boxnow 0 `
  --price 2099
```

This writes:
- `work/{model}/context.json`
- `work/{model}/llm_context.json`
- `work/{model}/prompt.txt`

### 2. Send the prompt to the model

Use `work/{model}/prompt.txt` as the prompt.

The model should return JSON only, matching:
- `schemas/compact_response.schema.json`

Save that JSON to:
- `work/{model}/llm_output.json`

### 3. Render final artifacts

```powershell
python scripts/render_product.py --model 233541
```

This writes:
- `products/{model}.csv`
- `work/{model}/chat_output.txt`
- `work/{model}/description.html`
- `work/{model}/characteristics.html`

## What moved out of the prompt

The renderer now handles:
- CSV header order
- CSV defaults
- category serialization
- image path generation
- technical specs HTML rendering
- final chat formatting

The context builder now handles:
- exact Electronet title extraction
- Electronet breadcrumb extraction
- category resolution against `catalog_taxonomy.json`
- allowed filter-group lookup from `filter_map.json`
- technical specs extraction from Electronet
- presentation-source block extraction from Electronet
- compact fact selection for the model

## Token savings

The biggest savings come from three changes:

1. The model no longer sees the full CSV and HTML rendering spec on every run.
2. The model no longer needs to output the technical specs table or the final CSV body.
3. The chat output is rendered locally and only shows `0) Φίλτρα`.

In practice, the model now only needs to generate:
- brand and MPN confirmation
- product name
- SEO URL
- meta title
- meta description
- meta keywords
- intro HTML fragment
- section titles and section body HTML fragments

## Scope

The automated extraction path is strongest for exact Electronet product pages.

If the source is not an exact Electronet product page:
- the new renderer and context pipeline can still be used
- but the context may be partial
- for difficult fallback cases, keep using `master_prompt_legacy.txt` and `RULES_legacy.md`
