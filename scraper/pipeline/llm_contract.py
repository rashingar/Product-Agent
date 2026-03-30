from __future__ import annotations

import json
import re
from typing import Any

from .html_builders import extract_presentation_blocks
from .mapping import serialize_meta_keywords
from .models import CLIInput, ParsedProduct, SchemaMatchResult, TaxonomyResolution
from .normalize import normalize_whitespace
from .presentation_sections import normalize_presentation_sections

INTRO_MIN_WORDS = 120
INTRO_MAX_WORDS = 180
HTML_TAG_RE = re.compile(r"<[^>]+>")
INTRO_TEXT_TASK = "intro_text"
SEO_META_TASK = "seo_meta"
MAX_TASK_KEY_SPECS = 6


def build_intro_text_context(
    cli: CLIInput,
    parsed: ParsedProduct,
    taxonomy: TaxonomyResolution,
    deterministic_product: dict[str, Any],
) -> dict[str, Any]:
    source = parsed.source
    return {
        "task": INTRO_TEXT_TASK,
        "input": {
            "model": cli.model,
            "url": cli.url,
        },
        "product": {
            "name": str(deterministic_product.get("name", "") or source.name or "").strip(),
            "brand": str(deterministic_product.get("brand", "") or source.brand or "").strip(),
            "mpn": str(deterministic_product.get("mpn", "") or source.mpn or "").strip(),
            "category": str(deterministic_product.get("category_phrase", "") or taxonomy.leaf_category or "").strip(),
            "sub_category": str(taxonomy.sub_category or "").strip(),
        },
        "evidence": {
            "hero_summary": normalize_whitespace(source.hero_summary),
            "key_specs": _compact_key_specs(source.key_specs),
            "deterministic_differentiators": _compact_values(deterministic_product.get("name_differentiators", [])),
        },
        "writer_rules": {
            "language": "Greek",
            "llm_owned_fields": [INTRO_TEXT_TASK],
            "plain_text_only": True,
            "paragraphs": 1,
            "word_count_range": {"min": INTRO_MIN_WORDS, "max": INTRO_MAX_WORDS},
            "forbidden_outputs": ["html", "bullets", "cta_language"],
        },
    }


def build_seo_meta_context(
    cli: CLIInput,
    parsed: ParsedProduct,
    taxonomy: TaxonomyResolution,
    deterministic_product: dict[str, Any],
) -> dict[str, Any]:
    source = parsed.source
    brand = str(deterministic_product.get("brand", "") or source.brand or "").strip()
    mpn = str(deterministic_product.get("mpn", "") or source.mpn or "").strip()
    return {
        "task": SEO_META_TASK,
        "input": {
            "model": cli.model,
            "url": cli.url,
        },
        "product": {
            "name": str(deterministic_product.get("name", "") or source.name or "").strip(),
            "brand": brand,
            "mpn": mpn,
            "category": str(deterministic_product.get("category_phrase", "") or taxonomy.leaf_category or "").strip(),
            "sub_category": str(taxonomy.sub_category or "").strip(),
            "meta_title": str(deterministic_product.get("meta_title", "") or "").strip(),
            "seo_keyword": str(deterministic_product.get("seo_keyword", "") or "").strip(),
        },
        "evidence": {
            "meta_description_draft": str(deterministic_product.get("meta_description_draft", "") or "").strip(),
            "hero_summary": normalize_whitespace(source.hero_summary),
            "key_specs": _compact_key_specs(source.key_specs),
            "deterministic_differentiators": _compact_values(deterministic_product.get("name_differentiators", [])),
        },
        "writer_rules": {
            "language": "Greek",
            "llm_owned_fields": ["product.meta_description", "product.meta_keywords"],
            "meta_description_rule": "Smooth the Greek grammar of `evidence.meta_description_draft`. Keep all verified facts. Exactly one sentence. No HTML.",
            "meta_keywords_rule": "Return a structured JSON array of verified keywords only. Do not serialize as CSV. Always include brand and mpn/model.",
            "required_keywords": [value for value in [brand, mpn] if value],
        },
    }


def build_task_manifest(
    *,
    llm_dir: str,
    intro_text_context_path: str,
    intro_text_prompt_path: str,
    intro_text_output_path: str,
    seo_meta_context_path: str,
    seo_meta_prompt_path: str,
    seo_meta_output_path: str,
    legacy_llm_context_path: str,
    legacy_prompt_path: str,
    legacy_llm_output_path: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "prepare_mode": "split_tasks_with_legacy_compatibility",
        "primary_outputs": {
            "llm_dir": llm_dir,
            "tasks": {
                INTRO_TEXT_TASK: {
                    "context_path": intro_text_context_path,
                    "prompt_path": intro_text_prompt_path,
                    "expected_output_path": intro_text_output_path,
                    "output_mode": "plain_text",
                    "llm_owned_fields": [INTRO_TEXT_TASK],
                },
                SEO_META_TASK: {
                    "context_path": seo_meta_context_path,
                    "prompt_path": seo_meta_prompt_path,
                    "expected_output_path": seo_meta_output_path,
                    "output_mode": "json",
                    "llm_owned_fields": ["product.meta_description", "product.meta_keywords"],
                },
            },
        },
        "compatibility": {
            "legacy_prepare_artifacts_written": True,
            "legacy_llm_context_path": legacy_llm_context_path,
            "legacy_prompt_path": legacy_prompt_path,
            "legacy_llm_output_path": legacy_llm_output_path,
            "render_still_reads_legacy_llm_output": True,
        },
    }


def build_llm_context(
    cli: CLIInput,
    parsed: ParsedProduct,
    taxonomy: TaxonomyResolution,
    schema_match: SchemaMatchResult,
    deterministic_product: dict[str, Any],
) -> dict[str, Any]:
    source = parsed.source
    sections_required = max(int(cli.sections), 0)
    extracted_sections = extract_presentation_blocks(
        presentation_source_html=source.presentation_source_html,
        presentation_source_text=source.presentation_source_text,
        base_url=source.canonical_url or source.url,
    )[:sections_required]
    presentation_sections = [
        section.to_dict()
        for section in normalize_presentation_sections(
            extracted_sections,
            sections_requested=sections_required,
        )
    ]
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
            "sections_required": sections_required,
            "llm_owned_fields": [
                "presentation.intro_html",
                "presentation.sections[].title",
                "presentation.sections[].body_html",
                "product.meta_description",
                "product.meta_keywords",
            ],
            "meta_description_rule": "Smooth the Greek grammar of `deterministic_product.meta_description_draft`. Keep all facts. Fix article agreement and natural phrasing. Exactly one sentence.",
            "intro_html_rule": f"{INTRO_MIN_WORDS}-{INTRO_MAX_WORDS} Greek words in one intro paragraph.",
        },
    }


def render_prompt(template_text: str, context: dict[str, Any]) -> str:
    return template_text.replace("{{LLM_CONTEXT_JSON}}", json.dumps(context, ensure_ascii=False, indent=2))


def count_html_words(value: str) -> int:
    text = normalize_whitespace(HTML_TAG_RE.sub(" ", value or ""))
    return len([token for token in text.split(" ") if token])


def validate_llm_output(
    payload: dict[str, Any],
    sections_required: int,
    intro_word_min: int = INTRO_MIN_WORDS,
    intro_word_max: int = INTRO_MAX_WORDS,
) -> tuple[dict[str, Any], list[str]]:
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

    product_keys = set(product)
    if product_keys not in ({"meta_description", "meta_keywords"}, {"meta_description", "meta_keywords", "name_tail_polished"}):
        errors.append("llm_product_shape_invalid")
    meta_description = product.get("meta_description", "")
    meta_keywords = product.get("meta_keywords", [])
    if not isinstance(meta_description, str):
        errors.append("llm_meta_description_invalid")
    if not isinstance(meta_keywords, list) or any(not isinstance(item, str) for item in meta_keywords):
        errors.append("llm_meta_keywords_invalid")

    if set(presentation) != {"intro_html", "sections"}:
        errors.append("llm_presentation_shape_invalid")
    intro_html = presentation.get("intro_html", "")
    sections = presentation.get("sections", [])
    if not isinstance(intro_html, str):
        errors.append("llm_intro_html_invalid")
    elif intro_html.strip():
        intro_word_count = count_html_words(intro_html)
        if intro_word_count < intro_word_min or intro_word_count > intro_word_max:
            errors.append("llm_intro_word_count_invalid")
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


def _compact_key_specs(items: list[Any]) -> list[dict[str, str]]:
    compact: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        label = normalize_whitespace(getattr(item, "label", ""))
        value = normalize_whitespace(getattr(item, "value", ""))
        if not label or not value:
            continue
        key = (label.casefold(), value.casefold())
        if key in seen:
            continue
        seen.add(key)
        compact.append({"label": label, "value": value})
        if len(compact) >= MAX_TASK_KEY_SPECS:
            break
    return compact


def _compact_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    compact: list[str] = []
    seen: set[str] = set()
    for item in values:
        value = normalize_whitespace(item)
        if not value:
            continue
        lowered = value.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        compact.append(value)
    return compact
