from __future__ import annotations

import json
from typing import Any

from .html_builders import extract_presentation_blocks
from .mapping import serialize_meta_keywords
from .models import CLIInput, ParsedProduct, SchemaMatchResult, TaxonomyResolution
from .normalize import normalize_whitespace


def build_llm_context(
    cli: CLIInput,
    parsed: ParsedProduct,
    taxonomy: TaxonomyResolution,
    schema_match: SchemaMatchResult,
    deterministic_product: dict[str, Any],
) -> dict[str, Any]:
    source = parsed.source
    presentation_sections = extract_presentation_blocks(
        presentation_source_html=source.presentation_source_html,
        presentation_source_text=source.presentation_source_text,
        base_url=source.canonical_url or source.url,
    )[: max(int(cli.sections), 0)]
    return {
        "input": {
            "model": cli.model,
            "url": cli.url,
            "price": str(cli.price),
            "photos": cli.photos,
            "sections": cli.sections,
            "skroutz_status": cli.skroutz_status,
            "boxnow": cli.boxnow,
        },
        "source": {
            "canonical_url": source.canonical_url,
            "title": source.name,
            "hero_summary": source.hero_summary,
            "breadcrumbs": source.breadcrumbs,
            "price_text": source.price_text,
            "key_specs": [item.to_dict() for item in source.key_specs],
            "product_code": source.product_code,
            "brand": source.brand,
            "mpn": source.mpn,
        },
        "taxonomy": taxonomy.to_dict(),
        "schema_match": schema_match.to_dict(),
        "deterministic_product": deterministic_product,
        "presentation_source_sections": presentation_sections,
        "writer_rules": {
            "language": "Greek",
            "sections_required": max(int(cli.sections), 0),
            "llm_owned_fields": [
                "presentation.intro_html",
                "presentation.cta_text",
                "presentation.sections[].title",
                "presentation.sections[].body_html",
                "product.meta_description",
                "product.meta_keywords",
            ],
            "meta_description_rule": "Exactly one sentence in Greek.",
            "cta_rule": "Use Greek CTA text only.",
        },
    }


def render_prompt(template_text: str, context: dict[str, Any]) -> str:
    return template_text.replace("{{LLM_CONTEXT_JSON}}", json.dumps(context, ensure_ascii=False, indent=2))


def validate_llm_output(payload: dict[str, Any], sections_required: int) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {}, ["llm_output_not_object"]

    expected_root = {"product", "presentation"}
    if set(payload) != expected_root:
        errors.append("llm_output_root_shape_invalid")

    product = payload.get("product")
    presentation = payload.get("presentation")
    if not isinstance(product, dict):
        errors.append("llm_product_invalid")
        product = {}
    if not isinstance(presentation, dict):
        errors.append("llm_presentation_invalid")
        presentation = {}

    if set(product) != {"meta_description", "meta_keywords"}:
        errors.append("llm_product_shape_invalid")
    meta_description = product.get("meta_description", "")
    meta_keywords = product.get("meta_keywords", [])
    if not isinstance(meta_description, str):
        errors.append("llm_meta_description_invalid")
    if not isinstance(meta_keywords, list) or any(not isinstance(item, str) for item in meta_keywords):
        errors.append("llm_meta_keywords_invalid")

    if set(presentation) != {"intro_html", "cta_text", "sections"}:
        errors.append("llm_presentation_shape_invalid")
    intro_html = presentation.get("intro_html", "")
    cta_text = presentation.get("cta_text", "")
    sections = presentation.get("sections", [])
    if not isinstance(intro_html, str):
        errors.append("llm_intro_html_invalid")
    if not isinstance(cta_text, str):
        errors.append("llm_cta_text_invalid")
    if not isinstance(sections, list):
        errors.append("llm_sections_invalid")
        sections = []
    else:
        for idx, section in enumerate(sections, start=1):
            if not isinstance(section, dict) or set(section) != {"title", "body_html"}:
                errors.append(f"llm_section_shape_invalid:{idx}")
                continue
            if not isinstance(section.get("title"), str) or not isinstance(section.get("body_html"), str):
                errors.append(f"llm_section_value_invalid:{idx}")
    if sections_required >= 0 and len(sections) != sections_required:
        errors.append("llm_sections_count_invalid")

    normalized = {
        "product": {
            "meta_description": normalize_whitespace(meta_description),
            "meta_keywords": [normalize_whitespace(item) for item in meta_keywords if normalize_whitespace(item)],
            "meta_keyword_csv": serialize_meta_keywords(meta_keywords),
        },
        "presentation": {
            "intro_html": intro_html.strip() if isinstance(intro_html, str) else "",
            "cta_text": normalize_whitespace(cta_text),
            "sections": [
                {
                    "title": normalize_whitespace(section.get("title", "")),
                    "body_html": str(section.get("body_html", "")).strip(),
                }
                for section in sections
                if isinstance(section, dict)
            ],
        },
    }
    return normalized, errors
