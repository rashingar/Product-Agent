# Product-Agent Runtime Input Rules

This file defines runtime input validation rules for the template-triggered workflow.

It is not the architecture roadmap and should not be used to constrain planned provider expansion beyond current runtime support.

## Trigger

Accepted input template:

```text
model:
url:
photos:
sections:
skroutz_status:
boxnow:
price:
```

Rules:
- `model` must be a confirmed 6-digit code.
- `url` must be a currently supported product URL recognized by the runtime source-detection layer.
- `photos` defaults to `1`.
- `sections` defaults to `0`.
- `skroutz_status` and `boxnow` boolean rule, defaults to `0`.
- `price` defaults to `0`.

If `model` is missing or not exactly 6 digits, fail with:
`Generation failed, provide 6-digit model`

Supported runtime URL scope is determined by the code-supported source-detection layer, not by a hardcoded single-source assumption in this file.

## Default Flow

1. Run `python -m electronet_single_import.workflow prepare ...` from `scrapper/`.
2. Read `work/{model}/llm_context.json` and `work/{model}/prompt.txt`.
3. Produce `work/{model}/llm_output.json` using the reduced response contract.
4. Run `python -m electronet_single_import.workflow render --model {model}` from `scrapper/`.
5. Inspect `work/{model}/candidate/{model}.validation.json`.

## Source Of Truth

Use these local files as runtime sources:
- `resources/mappings/catalog_taxonomy.json`
- `resources/schemas/electronet_schema_library.json`
- `resources/mappings/filter_map.json`
- `resources/templates/product_import_template.csv`
- `resources/templates/TEMPLATE_presentation.html`
- `resources/prompts/master_prompt+.txt`
- `resources/schemas/compact_response.schema.json`

## Local Responsibilities

Local code owns:
- category serialization
- image path generation
- CTA URL insertion
- technical specs HTML rendering
- final description wrapper HTML
- final CSV writing
- deterministic brand / mpn / manufacturer / name
- deterministic meta title
- deterministic SEO URL
- validation and baseline comparison

## LLM Responsibilities

The LLM stage returns JSON only for:
- `product.meta_description`
- `product.meta_keywords`
- `presentation.intro_html`
- `presentation.cta_text`
- `presentation.sections[].title`
- `presentation.sections[].body_html`

## Outputs

Prepare stage writes:
- `work/{model}/scrape/{model}.raw.html`
- `work/{model}/scrape/{model}.source.json`
- `work/{model}/scrape/{model}.normalized.json`
- `work/{model}/scrape/{model}.report.json`
- `work/{model}/llm_context.json`
- `work/{model}/prompt.txt`

Render stage writes:
- `work/{model}/candidate/{model}.csv`
- `work/{model}/candidate/{model}.normalized.json`
- `work/{model}/candidate/{model}.validation.json`
- `work/{model}/candidate/description.html`
- `work/{model}/candidate/characteristics.html`

## Validation

- `work/{model}/candidate/{model}.validation.json` is the final machine-readable health report.
- If `products/{model}.csv` exists, compare candidate output against it field by field.
- Prefer fixing pipeline behavior instead of patching generated files by hand.

## Legacy Workflow

The old script-driven flow is preserved only as historical reference:
- `archive/legacy/master_prompt_legacy.txt`
- `archive/legacy/RULES_legacy.md`
