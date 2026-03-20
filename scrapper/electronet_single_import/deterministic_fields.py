from __future__ import annotations

import re
from typing import Iterable

from .models import SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from .normalize import normalize_for_match, normalize_whitespace

MODEL_TOKEN_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9][A-Z0-9._/-]{2,}$")
PURE_NUMERIC_TOKEN_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
NUMERIC_RE = re.compile(r"\d+(?:[.,]\d+)?")


def build_deterministic_product_fields(
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
) -> dict[str, object]:
    raw_title = normalize_whitespace(source.name)
    brand = normalize_whitespace(source.brand)
    mpn = normalize_whitespace(source.mpn) or extract_mpn_from_name(raw_title, brand)
    category_phrase = derive_category_phrase(raw_title, brand, taxonomy)
    differentiators = derive_name_differentiators(source, category_phrase, taxonomy)
    composed_name = compose_name(brand, mpn, category_phrase, differentiators)
    preserve_title = should_preserve_parsed_title(raw_title, brand, mpn)
    name = raw_title if preserve_title and raw_title else composed_name
    meta_title = compose_meta_title(name, brand, mpn, category_phrase, differentiators, preserve_title)
    seo_keyword = seo_keyword_builder(name, model)
    return {
        "brand": brand,
        "mpn": mpn,
        "manufacturer": brand,
        "category_phrase": category_phrase,
        "name_differentiators": differentiators,
        "preserve_parsed_title": preserve_title,
        "name": name,
        "meta_title": meta_title,
        "seo_keyword": seo_keyword,
    }


def derive_category_phrase(name: str, brand: str, taxonomy: TaxonomyResolution) -> str:
    title = normalize_whitespace(name)
    brand_value = normalize_whitespace(brand)
    if title and brand_value:
        brand_match = re.search(rf"\b{re.escape(brand_value)}\b", title, flags=re.IGNORECASE)
        if brand_match:
            candidate = normalize_whitespace(title[: brand_match.start()].strip(" -–/|"))
            if candidate and len(candidate.split()) <= 8:
                return candidate
    for candidate in [taxonomy.sub_category or "", taxonomy.leaf_category, title]:
        normalized = normalize_whitespace(candidate)
        if normalized:
            return normalized
    return ""


def derive_name_differentiators(
    source: SourceProductData,
    category_phrase: str,
    taxonomy: TaxonomyResolution,
) -> list[str]:
    spec_lookup = build_spec_lookup(source.key_specs, source.spec_sections)
    ordered: list[str] = []

    capacity = format_capacity_differentiator(spec_lookup, category_phrase, taxonomy)
    cooling = normalize_value(spec_lookup, ["Τεχνολογία Ψύξης"])
    connectivity = normalize_connectivity(normalize_value(spec_lookup, ["Συνδεσιμότητα"]))

    for value in [capacity, cooling, connectivity]:
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def build_spec_lookup(key_specs: list[SpecItem], spec_sections: list[SpecSection]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in iter_specs(key_specs, spec_sections):
        label = normalize_for_match(item.label)
        value = normalize_whitespace(item.value)
        if label and value and label not in lookup:
            lookup[label] = value
    return lookup


def iter_specs(key_specs: list[SpecItem], spec_sections: list[SpecSection]) -> Iterable[SpecItem]:
    for item in key_specs:
        yield item
    for section in spec_sections:
        for item in section.items:
            yield item


def normalize_value(spec_lookup: dict[str, str], labels: list[str]) -> str:
    normalized_labels = {normalize_for_match(label) for label in labels}
    for label, value in spec_lookup.items():
        if label in normalized_labels and value:
            return normalize_whitespace(value)
    return ""


def format_capacity_differentiator(
    spec_lookup: dict[str, str],
    category_phrase: str,
    taxonomy: TaxonomyResolution,
) -> str:
    raw_value = normalize_value(spec_lookup, ["Συνολική Καθαρή Χωρητικότητα", "Χωρητικότητα", "Χωρητικότητα σε Λίτρα"])
    if not raw_value:
        return ""
    match = NUMERIC_RE.search(raw_value)
    if not match:
        return raw_value
    numeric = match.group(0).replace(",", ".")
    if numeric.endswith(".0"):
        numeric = numeric[:-2]
    unit = infer_capacity_unit(category_phrase, taxonomy)
    return f"{numeric}{unit}" if unit else numeric


def infer_capacity_unit(category_phrase: str, taxonomy: TaxonomyResolution) -> str:
    haystack = normalize_for_match(" ".join([category_phrase, taxonomy.sub_category or "", taxonomy.leaf_category]))
    if any(token in haystack for token in ["ψυγει", "καταψυκ", "συντηρητ", "wine", "κρασι"]):
        return "Lt"
    if any(token in haystack for token in ["πλυντηρ", "στεγνωτ", "ρούχ"]):
        return "Kg"
    return ""


def normalize_connectivity(value: str) -> str:
    normalized = normalize_for_match(value)
    if normalized in {"wifi", "wi fi"}:
        return "WiFi"
    return normalize_whitespace(value)


def compose_name(brand: str, mpn: str, category_phrase: str, differentiators: list[str]) -> str:
    head = normalize_whitespace(" ".join(part for part in [brand, mpn] if part))
    tail_parts = [normalize_whitespace(category_phrase), *[normalize_whitespace(item) for item in differentiators if item]]
    tail = normalize_whitespace(" ".join(part for part in tail_parts if part))
    if head and tail:
        return f"{head} – {tail}"
    return head or tail


def compose_meta_title(
    name: str,
    brand: str,
    mpn: str,
    category_phrase: str,
    differentiators: list[str],
    preserve_title: bool,
) -> str:
    if preserve_title and name:
        return f"{name} | eTranoulis"
    parts = [normalize_whitespace(part) for part in [brand, mpn, category_phrase] if normalize_whitespace(part)]
    parts.extend(item for item in differentiators[:2] if normalize_whitespace(item))
    title = normalize_whitespace(" ".join(parts))
    return f"{title} | eTranoulis" if title else ""


def extract_mpn_from_name(name: str, brand: str) -> str:
    tokens = [token for token in normalize_whitespace(name).split() if token]
    brand_norm = normalize_for_match(brand)
    if brand_norm:
        for index, token in enumerate(tokens):
            if normalize_for_match(token) == brand_norm:
                best = select_best_model_token(tokens[index + 1 :])
                if best:
                    return best
    best = select_best_model_token(tokens)
    if best:
        return best
    return ""


def should_preserve_parsed_title(title: str, brand: str, mpn: str) -> bool:
    tokens = title_tokens(title)
    if not tokens or not brand:
        return False
    if not mpn:
        return bool(title)
    brand_norm = normalize_for_match(brand)
    mpn_norm = normalize_for_match(mpn)
    brand_index = next((idx for idx, token in enumerate(tokens) if normalize_for_match(token) == brand_norm), -1)
    mpn_index = next((idx for idx, token in enumerate(tokens) if normalize_for_match(token) == mpn_norm), -1)
    if brand_index == -1 or mpn_index == -1 or mpn_index <= brand_index:
        return False
    family_tokens = [
        token
        for token in tokens[brand_index + 1 : mpn_index]
        if normalize_for_match(token) not in {brand_norm, mpn_norm}
    ]
    non_numeric_family_tokens = [token for token in family_tokens if not PURE_NUMERIC_TOKEN_RE.fullmatch(token)]
    return bool(non_numeric_family_tokens)


def title_tokens(name: str) -> list[str]:
    out: list[str] = []
    for raw in normalize_whitespace(name).split():
        token = raw.strip(" -–/|,.;:()[]{}")
        if token:
            out.append(token)
    return out


def select_best_model_token(tokens: list[str]) -> str:
    best_token = ""
    best_score = 0
    for token in tokens:
        score = score_model_token(token)
        if score > best_score:
            best_token = token.upper()
            best_score = score
    return best_token


def score_model_token(token: str) -> int:
    upper = token.upper()
    if PURE_NUMERIC_TOKEN_RE.fullmatch(token):
        return 0
    if not MODEL_TOKEN_RE.match(upper):
        return 0
    score = 10
    if re.search(r"[A-Z]", upper):
        score += 5
    if re.search(r"\d", upper):
        score += 3
    if upper[0].isalpha():
        score += 2
    if len(upper) >= 6:
        score += 1
    return score
