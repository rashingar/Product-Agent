# Product-Agent Runtime Rules

This file documents the default low-token workflow.

## Default Flow

1. Run `scripts/build_context.py` with the product input.
2. Send `work/{model}/prompt.txt` to the model.
3. Save the JSON reply to `work/{model}/llm_output.json`.
4. Run `scripts/render_product.py --model {model}`.

## Input Contract

Accepted input fields:
- `model`
- `url`
- `photos`
- `sections`
- `skroutz_status`
- `boxnow`
- `price`

Rules:
- `model` must be a confirmed 6-digit code.
- `url` is required.
- `photos` defaults to `1`.
- `sections` defaults to `0`.
- `skroutz_status` and `boxnow` must be `0` or `1`.
- `price` defaults to `0`.

If `model` is missing or not exactly 6 digits, fail with:
`Generation failed, provide 6-digit model`

## Source Of Truth

Use these local files as runtime sources:
- `catalog_taxonomy.json`: category resolution and CTA URLs
- `filter_map.json`: allowed filter groups per subcategory
- `product_import_template.csv`: exact CSV headers and order
- `TEMPLATE_presentation.html`: presentation HTML structure reference
- `schemas/compact_response.schema.json`: expected compact model response shape

## Local Responsibilities

The local scripts, not the model, are responsible for:
- category serialization
- image path generation
- CTA URL insertion
- technical specs HTML rendering
- final CSV writing
- final chat formatting
- filter rendering in chat

## Model Responsibilities

The model should return JSON only for:
- brand
- mpn
- manufacturer
- product name
- SEO URL
- meta title
- meta description
- meta keywords
- intro HTML fragment
- section titles and body HTML fragments

## Chat Output

Chat output shows only:
- `0) Φίλτρα`

All other sections are internal-only and are rendered into the CSV artifacts when needed.

## Outputs

After rendering, the workflow should produce:
- `products/{model}.csv`
- `work/{model}/chat_output.txt`
- `work/{model}/description.html`
- `work/{model}/characteristics.html`

## Legacy Workflow

The full legacy prompt and rules are preserved here:
- `master_prompt_legacy.txt`
- `RULES_legacy.md`

Use the legacy files only when the compact workflow is insufficient for a difficult fallback case.
