from __future__ import annotations

import csv
import re
from typing import Iterable

from typing import Any

from .models import SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from .normalize import normalize_for_match, normalize_whitespace
from .utils import DIFFERENTIATOR_PRIORITY_MAP_PATH

MODEL_TOKEN_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9][A-Z0-9._/-]{2,}$")
PURE_NUMERIC_TOKEN_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
NUMERIC_RE = re.compile(r"\d+(?:[.,]\d+)?")
ENERGY_CLASS_TOKEN_RE = re.compile(r"^[A-G](?:\+{1,3})?$", re.IGNORECASE)
DEFAULT_MAX_NAME_DIFFERENTIATORS = 3
DEFAULT_MAX_META_DESCRIPTION_DIFFERENTIATORS = 4

ARTICLE_MAP = {"fem": "Η", "neut": "Το", "masc": "Ο"}

_DIFFERENTIATOR_RULES_CACHE: dict[str, Any] | None = None


def _split_aliases(cell: str) -> list[str]:
    return [normalize_whitespace(part) for part in str(cell or "").split("|") if normalize_whitespace(part)]


def _parse_differentiator_cell(cell: str) -> list[list[str]]:
    segments = [normalize_whitespace(part) for part in str(cell or "").split("+") if normalize_whitespace(part)]
    return [_split_aliases(segment) for segment in segments if _split_aliases(segment)]


def _load_differentiator_rules() -> dict[str, Any]:
    global _DIFFERENTIATOR_RULES_CACHE
    if _DIFFERENTIATOR_RULES_CACHE is None:
        rules: list[dict[str, Any]] = []
        default_rule: dict[str, Any] = {"differentiator_specs": []}
        try:
            with open(DIFFERENTIATOR_PRIORITY_MAP_PATH, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                differentiator_columns = [field for field in reader.fieldnames or [] if field.startswith("differentiator_")]
                for raw_row in reader:
                    scope = normalize_for_match(raw_row.get("scope", "rule"))
                    differentiator_specs = [
                        parsed
                        for column in differentiator_columns
                        for parsed in [_parse_differentiator_cell(raw_row.get(column, ""))]
                        if parsed
                    ]
                    row_rule = {
                        "leaf_category": normalize_whitespace(raw_row.get("leaf_category", "")),
                        "category_phrase": normalize_whitespace(raw_row.get("category_phrase", "")),
                        "differentiator_specs": differentiator_specs,
                        "max_differentiators": len(differentiator_specs) or DEFAULT_MAX_NAME_DIFFERENTIATORS,
                    }
                    if scope == "default":
                        default_rule = row_rule
                    else:
                        rules.append(row_rule)
        except FileNotFoundError:
            pass
        _DIFFERENTIATOR_RULES_CACHE = {"rules": rules, "default": default_rule}
    return _DIFFERENTIATOR_RULES_CACHE


def match_name_rule(taxonomy: TaxonomyResolution) -> dict[str, Any] | None:
    rules_data = _load_differentiator_rules()
    sub = taxonomy.sub_category or ""
    leaf = taxonomy.leaf_category or ""
    normalized_sub = normalize_for_match(sub)
    normalized_leaf = normalize_for_match(leaf)

    for rule in rules_data.get("rules", []):
        target = normalize_for_match(rule.get("leaf_category", ""))
        if not target:
            continue
        if normalized_sub == target or normalized_leaf == target:
            return {**rule, "_matched_exact": True}

    for rule in rules_data.get("rules", []):
        target = normalize_for_match(rule.get("leaf_category", ""))
        if not target:
            continue
        if target in normalized_sub or normalized_sub in target or target in normalized_leaf or normalized_leaf in target:
            return {**rule, "_matched_exact": False}
    return None


def apply_name_rule(
    rule: dict[str, Any],
    source: SourceProductData,
    brand: str,
    mpn: str,
    taxonomy: TaxonomyResolution,
) -> tuple[str, list[str]]:
    category_phrase = rule.get("category_phrase", "")
    spec_labels = rule.get("differentiator_specs", [])
    max_differentiators = int(rule.get("max_differentiators", DEFAULT_MAX_NAME_DIFFERENTIATORS) or DEFAULT_MAX_NAME_DIFFERENTIATORS)
    spec_lookup = _build_preferred_spec_lookup(source)
    exact_match = bool(rule.get("_matched_exact"))
    if not exact_match:
        category_phrase = derive_category_phrase(source.name, brand, taxonomy) or category_phrase
    differentiators: list[str] = []
    for label_group in spec_labels:
        value = resolve_name_rule_value(
            source=source,
            spec_lookup=spec_lookup,
            alias_groups=label_group,
            category_phrase=category_phrase,
            taxonomy=taxonomy,
        )
        if value and len(differentiators) < max_differentiators:
            differentiators.append(value)
    if not differentiators:
        differentiators = derive_name_differentiators(source, category_phrase, taxonomy, brand, mpn)
    return category_phrase, differentiators


def build_meta_description_draft(
    brand: str,
    mpn: str,
    category_phrase: str,
    gender: str,
    key_differentiators: list[str],
) -> str:
    article = ARTICLE_MAP.get(gender, "Το")
    specs = ", ".join(d for d in key_differentiators[:DEFAULT_MAX_META_DESCRIPTION_DIFFERENTIATORS] if d)
    draft = f"{article} {brand} {mpn} είναι {category_phrase}"
    if specs:
        draft += f" με {specs}"
    return normalize_whitespace(draft) + "."


def build_deterministic_product_fields(
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
) -> dict[str, object]:
    skroutz_fields = build_skroutz_deterministic_fields(source, taxonomy, model, seo_keyword_builder)
    if skroutz_fields is not None:
        return skroutz_fields

    raw_title = normalize_whitespace(source.name)
    brand = normalize_whitespace(source.brand)
    mpn = normalize_whitespace(source.mpn) or extract_mpn_from_name(raw_title, brand)
    name_rule = match_name_rule(taxonomy)
    if name_rule:
        category_phrase, differentiators = apply_name_rule(name_rule, source, brand, mpn, taxonomy)
    else:
        category_phrase = derive_category_phrase(raw_title, brand, taxonomy)
        differentiators = derive_name_differentiators(source, category_phrase, taxonomy, brand, mpn)
    composed_name = compose_name(brand, mpn, category_phrase, differentiators)
    preserve_title = should_preserve_parsed_title(raw_title, brand, mpn, composed_name)
    name = composed_name or raw_title
    meta_title = compose_meta_title(name, brand, mpn, category_phrase, differentiators, preserve_title)
    seo_keyword = seo_keyword_builder(name, model)
    tail_parts = [normalize_whitespace(category_phrase)] + [normalize_whitespace(d) for d in differentiators if d]
    name_draft_tail = normalize_whitespace(" ".join(p for p in tail_parts if p))
    meta_description_draft = build_meta_description_draft(
        brand, mpn, category_phrase, taxonomy.gender, differentiators,
    )
    return {
        "brand": brand,
        "mpn": mpn,
        "manufacturer": brand,
        "category_phrase": category_phrase,
        "name_differentiators": differentiators,
        "preserve_parsed_title": preserve_title,
        "name": name,
        "name_draft_tail": name_draft_tail,
        "meta_title": meta_title,
        "meta_description_draft": meta_description_draft,
        "seo_keyword": seo_keyword,
    }


def build_skroutz_deterministic_fields(
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
) -> dict[str, object] | None:
    if normalize_for_match(source.source_name) != "skroutz":
        return None

    family = resolve_skroutz_family(taxonomy)
    if not family:
        return None

    raw_title = normalize_whitespace(source.name)
    brand = normalize_whitespace(source.brand)
    mpn = normalize_whitespace(source.mpn) or extract_mpn_from_name(raw_title, brand)
    spec_lookup = _build_preferred_spec_lookup(source)

    if family == "soundbar":
        category_phrase = "Soundbar"
        channels = normalize_value(spec_lookup, ["Κανάλια"])
        subwoofer = normalize_soundbar_subwoofer(normalize_value(spec_lookup, ["Subwoofer"]))
        differentiators = [item for item in [channels, subwoofer] if item]
        name = normalize_whitespace(" ".join(part for part in [brand, mpn, category_phrase, *differentiators] if part))
        meta_power = format_power(spec_lookup, ["Ισχύς"]) or extract_soundbar_power(" ".join([source.presentation_source_html, source.hero_summary, raw_title]))
        meta_standards = normalize_soundbar_standards_for_meta(normalize_value(spec_lookup, ["Πρότυπα Ήχου"]))
        meta_title_value = normalize_whitespace(" ".join(part for part in [brand, mpn, category_phrase, channels, meta_power, meta_standards] if part))
        meta_title = f"{meta_title_value} | eTranoulis" if meta_title_value else ""
        standards = normalize_soundbar_standards_for_seo(normalize_value(spec_lookup, ["Πρότυπα Ήχου"]))
        power = meta_power
        seo_keyword = seo_keyword_builder(
            normalize_whitespace(" ".join(part for part in [brand, mpn, category_phrase, normalize_soundbar_channels_for_seo(channels), standards, power] if part)),
            model,
        )
        return _skroutz_result(brand, mpn, category_phrase, differentiators, name, meta_title, seo_keyword, taxonomy)

    if family == "coffee_filter":
        category_phrase = "Καφετιέρα Φίλτρου"
        power = format_power(spec_lookup)
        capacity = format_liters(spec_lookup, ["Χωρητικότητα Δοχείου Νερού σε Λίτρα"])
        cups = format_cups(spec_lookup)
        differentiators = [item for item in [power, capacity, cups] if item]
        name = compose_name(brand, mpn, category_phrase, differentiators)
        meta_title = compose_meta_title(
            name=name,
            brand=brand,
            mpn=mpn,
            category_phrase=category_phrase,
            differentiators=[item for item in [power, capacity] if item],
            preserve_title=False,
        )
        seo_keyword = seo_keyword_builder(
            normalize_whitespace(" ".join(part for part in [brand, mpn, category_phrase, power, format_capacity_for_seo(capacity)] if part)),
            model,
        )
        return _skroutz_result(brand, mpn, category_phrase, differentiators, name, meta_title, seo_keyword, taxonomy)

    if family == "fridge_freezer":
        category_phrase = "Ψυγειοκαταψύκτης"
        cooling = normalize_fridge_cooling(normalize_value(spec_lookup, ["Σύστημα Ψύξης", "Τεχνολογία Ψύξης"]))
        capacity = normalize_value(spec_lookup, ["Συνολική Χωρητικότητα", "Συνολική Καθαρή Χωρητικότητα", "Χωρητικότητα"])
        color = normalize_value(spec_lookup, ["Χρώμα", "Χρώμα Συσκευής", "Χρώμα / Φινίρισμα"])
        width = normalize_value(spec_lookup, ["Πλάτος"])
        energy_class = normalize_value(spec_lookup, ["Ενεργειακή Κλάση"])
        differentiators = [item for item in [cooling, capacity, color, width, energy_class] if item]
        name = compose_name(brand, mpn, category_phrase, differentiators)
        meta_title = compose_meta_title(
            name=name,
            brand=brand,
            mpn=mpn,
            category_phrase=category_phrase,
            differentiators=[item for item in [cooling, capacity] if item],
            preserve_title=False,
        )
        seo_keyword = seo_keyword_builder(name, model)
        return _skroutz_result(brand, mpn, category_phrase, differentiators, name, meta_title, seo_keyword, taxonomy)

    if family == "kettle":
        category_phrase = "Βραστήρας"
        capacity = format_liters(spec_lookup, ["Χωρητικότητα σε Λίτρα"])
        power = format_power(spec_lookup)
        color = derive_kettle_color(raw_title, spec_lookup)
        differentiators = [item for item in [capacity, power, color] if item]
        name = compose_name(brand, mpn, category_phrase, differentiators)
        meta_title_value = normalize_whitespace(" ".join(part for part in [brand, mpn, category_phrase, *differentiators] if part))
        meta_title = f"{meta_title_value} | eTranoulis" if meta_title_value else ""
        seo_tail = extract_skroutz_tail_from_title(raw_title, category_phrase) or normalize_whitespace(
            " ".join(item for item in [category_phrase, capacity, power, color] if item)
        )
        seo_keyword = seo_keyword_builder(
            normalize_whitespace(" ".join(part for part in [brand, mpn, format_capacity_for_seo(seo_tail)] if part)),
            model,
        )
        return _skroutz_result(brand, mpn, category_phrase, differentiators, name, meta_title, seo_keyword, taxonomy)

    category_phrase = "Επιτραπέζια Εστία"
    burner_phrase = derive_hob_burner_phrase(spec_lookup, raw_title)
    power = format_power(spec_lookup, ["Ισχύς"])
    surface = normalize_value(spec_lookup, ["Τύπος Εστίας"])
    differentiators = [item for item in [burner_phrase, power, surface] if item]
    name = compose_name(brand, mpn, category_phrase, differentiators)
    meta_title = compose_meta_title(
        name=name,
        brand=brand,
        mpn=mpn,
        category_phrase=category_phrase,
        differentiators=[item for item in [burner_phrase, power] if item],
        preserve_title=False,
    )
    seo_name = compose_name(brand, mpn, category_phrase, [normalize_hob_burners_for_seo(burner_phrase), power, surface])
    seo_keyword = seo_keyword_builder(seo_name, model)
    return _skroutz_result(brand, mpn, category_phrase, differentiators, name, meta_title, seo_keyword, taxonomy)


def _skroutz_result(
    brand: str,
    mpn: str,
    category_phrase: str,
    differentiators: list[str],
    name: str,
    meta_title: str,
    seo_keyword: str,
    taxonomy: TaxonomyResolution,
) -> dict[str, object]:
    tail_parts = [normalize_whitespace(category_phrase)] + [normalize_whitespace(d) for d in differentiators if d]
    name_draft_tail = normalize_whitespace(" ".join(p for p in tail_parts if p))
    meta_description_draft = build_meta_description_draft(
        brand, mpn, category_phrase, taxonomy.gender, differentiators,
    )
    return {
        "brand": brand,
        "mpn": mpn,
        "manufacturer": brand,
        "category_phrase": category_phrase,
        "name_differentiators": differentiators,
        "preserve_parsed_title": False,
        "name": name,
        "name_draft_tail": name_draft_tail,
        "meta_title": meta_title,
        "meta_description_draft": meta_description_draft,
        "seo_keyword": seo_keyword,
    }


def resolve_skroutz_family(taxonomy: TaxonomyResolution) -> str | None:
    sub = normalize_for_match(taxonomy.sub_category)
    leaf = normalize_for_match(taxonomy.leaf_category)
    if sub == normalize_for_match("Sound Bars") and leaf == normalize_for_match("Audio Systems"):
        return "soundbar"
    if sub == normalize_for_match("Ψυγειοκαταψύκτες"):
        return "fridge_freezer"
    if sub == normalize_for_match("Καφετιέρες Φίλτρου"):
        return "coffee_filter"
    if sub == normalize_for_match("Βραστήρες"):
        return "kettle"
    if sub == normalize_for_match("Εστίες") and leaf == normalize_for_match("Μικροί Μάγειρες"):
        return "tabletop_hob"
    return None


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
    brand: str,
    mpn: str,
) -> list[str]:
    spec_lookup = _build_preferred_spec_lookup(source)
    ordered: list[str] = []

    capacity = format_capacity_differentiator(spec_lookup, category_phrase, taxonomy)
    cooling = normalize_value(spec_lookup, ["Τεχνολογία Ψύξης"])
    connectivity = normalize_connectivity(normalize_value(spec_lookup, ["Συνδεσιμότητα"]))
    family = extract_commercial_family_from_title(source.name, brand, mpn)
    color = normalize_color_differentiator(spec_lookup) or extract_title_suffix_differentiator(source.name, brand, mpn)

    for value in [capacity, cooling, connectivity, family, color]:
        normalized = normalize_whitespace(value)
        if normalized and normalized not in ordered:
            ordered.append(normalized)
        if len(ordered) >= DEFAULT_MAX_NAME_DIFFERENTIATORS:
            break
    return ordered


def _prefer_manufacturer_evidence(source: SourceProductData) -> bool:
    return normalize_for_match(source.source_name) == "skroutz" and bool(source.manufacturer_spec_sections)


def effective_spec_sections(source: SourceProductData, manufacturer_first: bool = False) -> list[SpecSection]:
    if manufacturer_first and _prefer_manufacturer_evidence(source):
        return [*source.manufacturer_spec_sections, *source.spec_sections]
    return [*source.spec_sections, *source.manufacturer_spec_sections]


def _build_preferred_spec_lookup(source: SourceProductData) -> dict[str, str]:
    prefer_manufacturer = _prefer_manufacturer_evidence(source)
    return build_spec_lookup(
        source.key_specs,
        effective_spec_sections(source, manufacturer_first=prefer_manufacturer),
        key_specs_last=prefer_manufacturer,
    )


def build_spec_lookup(key_specs: list[SpecItem], spec_sections: list[SpecSection], *, key_specs_last: bool = False) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in iter_specs(key_specs, spec_sections, key_specs_last=key_specs_last):
        label = normalize_for_match(item.label)
        value = normalize_whitespace(item.value)
        if label and value and label not in lookup:
            lookup[label] = value
    return lookup


def iter_specs(key_specs: list[SpecItem], spec_sections: list[SpecSection], *, key_specs_last: bool = False) -> Iterable[SpecItem]:
    if not key_specs_last:
        for item in key_specs:
            yield item
    for section in spec_sections:
        for item in section.items:
            yield item
    if key_specs_last:
        for item in key_specs:
            yield item


def normalize_value(spec_lookup: dict[str, str], labels: list[str]) -> str:
    normalized_labels = {normalize_for_match(label) for label in labels}
    for label, value in spec_lookup.items():
        if label in normalized_labels and value:
            return normalize_whitespace(value)
    return ""


def resolve_name_rule_value(
    source: SourceProductData,
    spec_lookup: dict[str, str],
    alias_groups: list[list[str]] | list[str],
    category_phrase: str,
    taxonomy: TaxonomyResolution,
) -> str:
    groups = alias_groups if alias_groups and isinstance(alias_groups[0], list) else [alias_groups]
    resolved_parts: list[str] = []
    for aliases in groups:
        resolved = resolve_name_rule_component(source, spec_lookup, [str(alias) for alias in aliases], category_phrase, taxonomy)
        if not resolved:
            return ""
        resolved_parts.append(resolved)
    if not resolved_parts:
        return ""
    if len(resolved_parts) == 1:
        return resolved_parts[0]
    return "/".join(resolved_parts)


def resolve_name_rule_component(
    source: SourceProductData,
    spec_lookup: dict[str, str],
    aliases: list[str],
    category_phrase: str,
    taxonomy: TaxonomyResolution,
) -> str:
    direct_value = normalize_value(spec_lookup, aliases)
    if direct_value:
        return normalize_name_rule_value(direct_value, aliases, category_phrase, taxonomy)

    fallback_value = extract_alias_value_from_evidence(source, aliases)
    if fallback_value:
        return normalize_name_rule_value(fallback_value, aliases, category_phrase, taxonomy)
    return ""


def normalize_name_rule_value(value: str, aliases: list[str], category_phrase: str, taxonomy: TaxonomyResolution) -> str:
    normalized = normalize_whitespace(value)
    if not normalized:
        return ""
    alias_keys = {normalize_for_match(alias) for alias in aliases}
    if any("ψυξης" in key for key in alias_keys):
        normalized = re.sub(r"\bNoFrost\b", "No Frost", normalized, flags=re.IGNORECASE)
    if any("χωρητικοτητα" in key or "κιλα" in key for key in alias_keys):
        numeric = extract_numeric(normalized)
        unit = infer_capacity_unit(category_phrase, taxonomy)
        if numeric and unit == "Kg":
            return f"{numeric} kg"
        if numeric and unit == "Lt":
            return f"{numeric}Lt"
    return normalized


def extract_alias_value_from_evidence(source: SourceProductData, aliases: list[str]) -> str:
    alias_candidates = [normalize_whitespace(alias) for alias in aliases if normalize_whitespace(alias)]
    if not alias_candidates:
        return ""
    texts = [normalize_whitespace(source.name)] + [
        normalize_whitespace(item.value)
        for item in iter_specs(source.key_specs, effective_spec_sections(source, manufacturer_first=_prefer_manufacturer_evidence(source)))
        if normalize_whitespace(item.value)
    ]
    for text in texts:
        for alias in alias_candidates:
            match = re.search(re.escape(alias), text, flags=re.IGNORECASE)
            if match:
                return normalize_whitespace(text[match.start() : match.end()])
    return ""


def normalize_soundbar_subwoofer(value: str) -> str:
    normalized = normalize_whitespace(value)
    if not normalized:
        return ""
    return normalized if normalized.lower().startswith("με ") else f"με {normalized}"


def normalize_soundbar_standards_for_seo(value: str) -> str:
    normalized = normalize_whitespace(value.replace(",", " ").replace(":", " "))
    return normalized


def normalize_soundbar_standards_for_meta(value: str) -> str:
    normalized = normalize_whitespace(value.replace(", ", "/").replace(": ", ":"))
    return normalized


def normalize_soundbar_channels_for_seo(value: str) -> str:
    return normalize_whitespace(value.replace(".", " "))


def normalize_fridge_cooling(value: str) -> str:
    normalized = normalize_whitespace(value)
    if not normalized:
        return ""
    return re.sub(r"\bNoFrost\b", "No Frost", normalized, flags=re.IGNORECASE)


def extract_soundbar_power(text: str) -> str:
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*W\b", text or "", flags=re.IGNORECASE)
    if not matches:
        return ""
    numeric = max(float(value.replace(",", ".")) for value in matches)
    try:
        return f"{int(numeric)}W"
    except ValueError:
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
    if any(token in haystack for token in ["πλυντηρ", "στεγνωτ", "ρουχ"]):
        return "Kg"
    return ""


def normalize_connectivity(value: str) -> str:
    normalized = normalize_for_match(value)
    if normalized in {"wifi", "wi fi"}:
        return "WiFi"
    return normalize_whitespace(value)


def normalize_color_differentiator(spec_lookup: dict[str, str]) -> str:
    return normalize_value(spec_lookup, ["Χρώμα", "Χρώμα Συσκευής", "Χρώμα / Φινίρισμα"])


def extract_commercial_family_from_title(title: str, brand: str, mpn: str) -> str:
    tokens = title_tokens(title)
    brand_norm = normalize_for_match(brand)
    mpn_norm = normalize_for_match(mpn)
    if not tokens or not brand_norm or not mpn_norm:
        return ""
    brand_index = next((idx for idx, token in enumerate(tokens) if normalize_for_match(token) == brand_norm), -1)
    mpn_index = next((idx for idx, token in enumerate(tokens) if normalize_for_match(token) == mpn_norm), -1)
    if brand_index == -1 or mpn_index == -1 or mpn_index <= brand_index + 1:
        return ""
    family_tokens = [
        token
        for token in tokens[brand_index + 1 : mpn_index]
        if normalize_for_match(token) not in {brand_norm, mpn_norm}
    ]
    family = normalize_whitespace(" ".join(family_tokens))
    if not family or PURE_NUMERIC_TOKEN_RE.fullmatch(family):
        return ""
    return family


def extract_title_suffix_differentiator(title: str, brand: str, mpn: str) -> str:
    tokens = title_tokens(title)
    mpn_norm = normalize_for_match(mpn)
    brand_norm = normalize_for_match(brand)
    if not tokens or not mpn_norm:
        return ""
    mpn_index = next((idx for idx, token in enumerate(tokens) if normalize_for_match(token) == mpn_norm), -1)
    if mpn_index == -1 or mpn_index >= len(tokens) - 1:
        return ""
    suffix_tokens: list[str] = []
    for token in tokens[mpn_index + 1 :]:
        normalized = normalize_for_match(token)
        if not normalized or normalized in {brand_norm, mpn_norm}:
            continue
        if PURE_NUMERIC_TOKEN_RE.fullmatch(token):
            continue
        if ENERGY_CLASS_TOKEN_RE.fullmatch(token.upper()):
            continue
        suffix_tokens.append(token)
    return normalize_whitespace(" ".join(suffix_tokens))


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


def format_power(spec_lookup: dict[str, str], labels: list[str] | None = None) -> str:
    raw = normalize_value(spec_lookup, labels or ["Ισχύς σε Watts", "Ισχύς"])
    if not raw:
        return ""
    numeric = extract_numeric(raw)
    return f"{numeric}W" if numeric else ""


def format_liters(spec_lookup: dict[str, str], labels: list[str]) -> str:
    raw = normalize_value(spec_lookup, labels)
    numeric = extract_numeric(raw)
    return f"{numeric}Lt" if numeric else ""


def format_cups(spec_lookup: dict[str, str]) -> str:
    raw = normalize_value(spec_lookup, ["Χωρητικότητα σε Φλυτζάνια"])
    if not raw:
        return ""
    normalized = normalize_whitespace(raw).replace(" - ", "-")
    if normalize_for_match(normalized).endswith(normalize_for_match("φλιτζάνια")):
        return normalized
    return f"{normalized} Φλιτζάνια"


def format_capacity_for_seo(value: str) -> str:
    normalized = normalize_whitespace(value)
    if not normalized:
        return ""
    normalized = re.sub(r"(?<=\d)[,.](?=\d)", " ", normalized)
    return normalized


def derive_kettle_color(raw_title: str, spec_lookup: dict[str, str]) -> str:
    base_color = normalize_value(spec_lookup, ["Χρώμα"])
    if not base_color:
        return ""
    if re.search(r"\bmat\b", raw_title, flags=re.IGNORECASE):
        return f"{base_color} Ματ"
    return base_color


def extract_skroutz_tail_from_title(raw_title: str, category_phrase: str) -> str:
    title = normalize_whitespace(raw_title)
    if not title:
        return ""
    match = re.search(rf"\b{re.escape(category_phrase)}\b", title, flags=re.IGNORECASE)
    if not match:
        return ""
    return normalize_whitespace(title[match.start() :])


def derive_hob_burner_phrase(spec_lookup: dict[str, str], raw_title: str) -> str:
    burners = normalize_value(spec_lookup, ["Εστίες"])
    if burners:
        numeric = extract_numeric(burners)
        if numeric:
            return f"{numeric} Εστιών"
    title_norm = normalize_for_match(raw_title)
    if "διπλη" in title_norm:
        return "2 Εστιών"
    if "μονη" in title_norm:
        return "1 Εστιών"
    return ""


def normalize_hob_burners_for_seo(value: str) -> str:
    normalized = normalize_whitespace(value)
    if normalized == "2 Εστιών":
        return "2 Εστίες"
    if normalized == "1 Εστιών":
        return "1 Εστία"
    return normalized


def extract_numeric(value: str) -> str:
    match = NUMERIC_RE.search(normalize_whitespace(value))
    return match.group(0).replace(".", ",") if match else ""


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


def should_preserve_parsed_title(title: str, brand: str, mpn: str, composed_name: str = "") -> bool:
    del brand, mpn
    return not normalize_whitespace(composed_name) and bool(normalize_whitespace(title))


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
