from __future__ import annotations

import re
from typing import Any

from .mapping import serialize_meta_keywords
from .models import CLIInput, ParsedProduct, TaxonomyResolution
from .normalize import normalize_whitespace

INTRO_MIN_WORDS = 100
INTRO_MAX_WORDS = 180
HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_DETECT_RE = re.compile(r"<[^>]+>")
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
            "meta_description_rule": (
                "Prefer 2 natural Greek sentences using verified evidence only and no HTML. "
                "Sentence 1 identifies the product using brand + mpn + category + strongest verified differentiators. "
                "Sentence 2 adds 2-4 verified features/benefits only from evidence already present in context, with evidence priority: "
                "1. `hero_summary` 2. `key_specs` 3. `deterministic_differentiators`. "
                "For TVs prefer `115 ιντσών` rather than `115\"`; if `4K` is verified, prefer `4K Ultra HD ανάλυση`; if `8K` is verified, prefer `8K Ultra HD ανάλυση`. "
                "Aim for roughly `160-260` characters unless verified detail clearly justifies somewhat more."
            ),
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
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "prepare_mode": "split_tasks",
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
    }


def count_html_words(value: str) -> int:
    text = normalize_whitespace(HTML_TAG_RE.sub(" ", value or ""))
    return len([token for token in text.split(" ") if token])


def validate_intro_text_output(
    payload: str | dict[str, Any],
    *,
    intro_word_min: int = INTRO_MIN_WORDS,
    intro_word_max: int = INTRO_MAX_WORDS,
) -> tuple[str, list[str]]:
    errors: list[str] = []
    value = payload.get("intro_text", "") if isinstance(payload, dict) else payload
    if not isinstance(value, str):
        return "", ["llm_intro_text_invalid"]
    normalized = normalize_whitespace(value)
    if HTML_DETECT_RE.search(value):
        errors.append("llm_intro_text_html_invalid")
    word_count = count_plain_text_words(normalized)
    if word_count < intro_word_min or word_count > intro_word_max:
        errors.append("llm_intro_text_word_count_invalid")
    return normalized, errors


def validate_seo_meta_output(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {}, ["llm_seo_meta_not_object"]
    if set(payload) != {"product"}:
        errors.append("llm_seo_meta_root_shape_invalid")
    product = payload.get("product")
    if not isinstance(product, dict):
        return {}, ["llm_seo_meta_product_invalid"]
    product_keys = set(product)
    if product_keys not in ({"meta_description", "meta_keywords"}, {"meta_description", "meta_keywords", "name_tail_polished"}):
        errors.append("llm_seo_meta_shape_invalid")
    meta_description = product.get("meta_description", "")
    meta_keywords = product.get("meta_keywords", [])
    if not isinstance(meta_description, str):
        errors.append("llm_seo_meta_description_invalid")
    if not isinstance(meta_keywords, list) or any(not isinstance(item, str) for item in meta_keywords):
        errors.append("llm_seo_meta_keywords_invalid")
    return {
        "product": {
            "meta_description": normalize_whitespace(meta_description),
            "meta_keywords": [normalize_whitespace(item) for item in meta_keywords if normalize_whitespace(item)],
            "meta_keyword_csv": serialize_meta_keywords(meta_keywords),
        }
    }, errors


def count_plain_text_words(value: str) -> int:
    text = normalize_whitespace(value)
    return len([token for token in text.split(" ") if token])


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
