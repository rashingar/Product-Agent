from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, Iterable

from .deterministic_rule_config import (
    GenericNameRule,
    ResolvedGenericNameRule,
    SourceScopedRule,
    load_deterministic_rule_config,
    resolve_generic_name_rule,
    resolve_source_scoped_rule,
)
from .models import SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from .normalize import normalize_for_match, normalize_whitespace

MODEL_TOKEN_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9][A-Z0-9._/-]{2,}$")
PURE_NUMERIC_TOKEN_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
NUMERIC_RE = re.compile(r"\d+(?:[.,]\d+)?")
ENERGY_CLASS_TOKEN_RE = re.compile(r"^[A-G](?:\+{1,3})?$", re.IGNORECASE)
DEFAULT_MAX_NAME_DIFFERENTIATORS = 3
DEFAULT_MAX_META_DESCRIPTION_DIFFERENTIATORS = 4
FUZZY_SINGLE_TOKEN_ALLOWLIST = {
    "βαθος",
    "διαμετρος",
    "ισχυς",
    "καναλια",
    "κιλα",
    "πλατος",
    "προτυπα",
    "συνδεσιμοτητα",
    "ταση",
    "υψος",
    "χωρητικοτητα",
    "χρωμα",
}
FUZZY_ALIAS_DENYLIST = {"τυπος"}

ARTICLE_MAP = {"fem": "Η", "neut": "Το", "masc": "Ο"}

@dataclass(frozen=True, slots=True)
class ResolvedNameComponent:
    value: str
    matched_label: str = ""
    source: str = ""


def _rule_value(rule: ResolvedGenericNameRule | GenericNameRule | Mapping[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(rule, ResolvedGenericNameRule):
        if key == "_matched_exact":
            return rule.matched_exact
        if key == "category_phrase":
            return rule.rule.category_phrase
        if key == "differentiator_specs":
            return [[list(aliases) for aliases in group] for group in rule.rule.differentiator_specs]
        if key == "max_differentiators":
            return rule.rule.max_differentiators
        if key == "outputs":
            return {
                "name": rule.outputs.name,
                "meta_title": rule.outputs.meta_title,
                "seo_keyword": rule.outputs.seo_keyword,
            }
        return default
    if isinstance(rule, GenericNameRule):
        if key == "category_phrase":
            return rule.category_phrase
        if key == "differentiator_specs":
            return [[list(aliases) for aliases in group] for group in rule.differentiator_specs]
        if key == "max_differentiators":
            return rule.max_differentiators
        return default
    return rule.get(key, default)


def match_name_rule(
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
) -> ResolvedGenericNameRule | None:
    return resolve_generic_name_rule(
        source_name=source.source_name or "any",
        leaf_category=taxonomy.leaf_category or "",
        sub_category=taxonomy.sub_category or "",
    )


def apply_name_rule(
    rule: ResolvedGenericNameRule | GenericNameRule | Mapping[str, Any],
    source: SourceProductData,
    brand: str,
    mpn: str,
    taxonomy: TaxonomyResolution,
) -> tuple[str, list[str]]:
    category_phrase = _rule_value(rule, "category_phrase", "")
    spec_labels = _rule_value(rule, "differentiator_specs", [])
    max_differentiators = int(
        _rule_value(rule, "max_differentiators", DEFAULT_MAX_NAME_DIFFERENTIATORS) or DEFAULT_MAX_NAME_DIFFERENTIATORS
    )
    spec_lookup = _build_preferred_spec_lookup(source)
    exact_match = bool(_rule_value(rule, "_matched_exact"))
    if not exact_match:
        category_phrase = derive_category_phrase(source.name, brand, taxonomy) or category_phrase
    differentiators: list[str] = []
    is_tv_rule = _is_tv_scope(category_phrase, taxonomy)
    for label_group in spec_labels:
        value = resolve_name_rule_value(
            source=source,
            spec_lookup=spec_lookup,
            alias_groups=label_group,
            category_phrase=category_phrase,
            taxonomy=taxonomy,
        )
        if not value:
            continue
        if is_tv_rule:
            differentiators = _append_tv_differentiator(differentiators, value, max_differentiators)
            continue
        if len(differentiators) < max_differentiators:
            differentiators.append(value)
    if not differentiators:
        differentiators = derive_name_differentiators(source, category_phrase, taxonomy, brand, mpn)
    return category_phrase, differentiators


def _select_generic_output_differentiators(differentiators: list[str], mode: str) -> list[str]:
    normalized_mode = normalize_for_match(mode)
    if normalized_mode == "first_1":
        return differentiators[:1]
    if normalized_mode == "first_2":
        return differentiators[:2]
    return differentiators


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
    name_rule = match_name_rule(source, taxonomy)
    output_profile = name_rule.outputs if name_rule else load_deterministic_rule_config().generic_outputs
    if name_rule:
        category_phrase, differentiators = apply_name_rule(name_rule, source, brand, mpn, taxonomy)
    else:
        category_phrase = derive_category_phrase(raw_title, brand, taxonomy)
        differentiators = derive_name_differentiators(source, category_phrase, taxonomy, brand, mpn)
    name_differentiators = _select_generic_output_differentiators(differentiators, output_profile.name)
    meta_title_differentiators = _select_generic_output_differentiators(differentiators, output_profile.meta_title)
    composed_name = compose_name(brand, mpn, category_phrase, name_differentiators)
    preserve_title = should_preserve_parsed_title(raw_title, brand, mpn, composed_name)
    name = composed_name or raw_title
    meta_title = compose_meta_title(name, brand, mpn, category_phrase, meta_title_differentiators, preserve_title)
    if normalize_for_match(output_profile.seo_keyword) == "name":
        seo_keyword = seo_keyword_builder(name, model)
    else:
        seo_keyword = seo_keyword_builder(
            compose_name(
                brand,
                mpn,
                category_phrase,
                _select_generic_output_differentiators(differentiators, output_profile.seo_keyword),
            ),
            model,
        )
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
    family = resolve_skroutz_family(taxonomy)
    if not family:
        return None

    source_rule = resolve_source_scoped_rule(
        source_name=source.source_name or "",
        family=family,
        leaf_category=taxonomy.leaf_category or "",
        sub_category=taxonomy.sub_category or "",
    )
    if source_rule is None:
        return None

    raw_title = normalize_whitespace(source.name)
    brand = normalize_whitespace(source.brand)
    mpn = normalize_whitespace(source.mpn) or extract_mpn_from_name(raw_title, brand)
    spec_lookup = _build_preferred_spec_lookup(source)
    return build_source_scoped_deterministic_fields(
        rule=source_rule,
        source=source,
        taxonomy=taxonomy,
        model=model,
        seo_keyword_builder=seo_keyword_builder,
        raw_title=raw_title,
        brand=brand,
        mpn=mpn,
        spec_lookup=spec_lookup,
    )

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
        title_tail = normalize_whitespace(source.name).split()[-1] if normalize_whitespace(source.name) else ""
        energy_class = normalize_value(spec_lookup, ["?????????? ?????"]) or extract_energy_class_from_source(source) or (title_tail.upper() if ENERGY_CLASS_TOKEN_RE.fullmatch(title_tail) else "")
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

    if family == "ice_cream_maker":
        category_phrase = "Παγωτομηχανή"
        capacity = format_liters(spec_lookup, ["Χωρητικότητα"])
        programs = format_program_count(spec_lookup, ["Αριθμός Προγραμμάτων"])
        bowls = format_count_differentiator(spec_lookup, ["Αριθμός Δοχείων"], singular="Δοχείου", plural="Δοχείων")
        color = normalize_value(spec_lookup, ["Χρώμα"])
        differentiators = [item for item in [capacity, programs, bowls or color] if item]
        name = compose_name(brand, mpn, category_phrase, differentiators)
        meta_title = compose_meta_title(
            name=name,
            brand=brand,
            mpn=mpn,
            category_phrase=category_phrase,
            differentiators=[item for item in [capacity, programs] if item],
            preserve_title=False,
        )
        seo_keyword = seo_keyword_builder(
            normalize_whitespace(" ".join(part for part in [brand, mpn, category_phrase, capacity, programs, bowls, color] if part)),
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


def build_source_scoped_deterministic_fields(
    *,
    rule: SourceScopedRule,
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
    raw_title: str,
    brand: str,
    mpn: str,
    spec_lookup: dict[str, str],
) -> dict[str, object] | None:
    strategy_id = rule.strategy_id
    if strategy_id == "soundbar":
        return _build_soundbar_deterministic_fields(rule, source, taxonomy, model, seo_keyword_builder, raw_title, brand, mpn, spec_lookup)
    if strategy_id == "coffee_filter":
        return _build_coffee_filter_deterministic_fields(rule, taxonomy, model, seo_keyword_builder, brand, mpn, spec_lookup)
    if strategy_id == "fridge_freezer":
        return _build_fridge_freezer_deterministic_fields(rule, source, taxonomy, model, seo_keyword_builder, brand, mpn, spec_lookup)
    if strategy_id == "kettle":
        return _build_kettle_deterministic_fields(rule, taxonomy, model, seo_keyword_builder, raw_title, brand, mpn, spec_lookup)
    if strategy_id == "ice_cream_maker":
        return _build_ice_cream_maker_deterministic_fields(rule, taxonomy, model, seo_keyword_builder, brand, mpn, spec_lookup)
    if strategy_id == "tabletop_hob":
        return _build_tabletop_hob_deterministic_fields(rule, taxonomy, model, seo_keyword_builder, raw_title, brand, mpn, spec_lookup)
    raise ValueError(f"Unsupported deterministic source strategy: {rule.strategy_id}")


def _source_rule_output_parts(rule: SourceScopedRule, output_key: str, components: Mapping[str, str]) -> list[str]:
    return [
        value
        for component_id in rule.outputs.get(output_key, ())
        for value in [normalize_whitespace(components.get(component_id, ""))]
        if value
    ]


def _build_soundbar_deterministic_fields(
    rule: SourceScopedRule,
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
    raw_title: str,
    brand: str,
    mpn: str,
    spec_lookup: dict[str, str],
) -> dict[str, object]:
    category_phrase = rule.category_phrase
    channels = normalize_value(spec_lookup, ["Κανάλια"])
    meta_power = format_power(spec_lookup, ["Ισχύς"]) or extract_soundbar_power(
        " ".join([source.presentation_source_html, source.hero_summary, raw_title])
    )
    components = {
        "channels": channels,
        "subwoofer": normalize_soundbar_subwoofer(normalize_value(spec_lookup, ["Subwoofer"])),
        "power": meta_power,
        "standards_meta": normalize_soundbar_standards_for_meta(normalize_value(spec_lookup, ["Πρότυπα Ήχου"])),
        "standards_seo": normalize_soundbar_standards_for_seo(normalize_value(spec_lookup, ["Πρότυπα Ήχου"])),
        "channels_seo": normalize_soundbar_channels_for_seo(channels),
    }
    differentiators = _source_rule_output_parts(rule, "name", components)
    name = normalize_whitespace(" ".join(part for part in [brand, mpn, category_phrase, *differentiators] if part))
    meta_title_value = normalize_whitespace(
        " ".join(part for part in [brand, mpn, category_phrase, *_source_rule_output_parts(rule, "meta_title", components)] if part)
    )
    meta_title = f"{meta_title_value} | eTranoulis" if meta_title_value else ""
    seo_keyword = seo_keyword_builder(
        normalize_whitespace(
            " ".join(part for part in [brand, mpn, category_phrase, *_source_rule_output_parts(rule, "seo_keyword", components)] if part)
        ),
        model,
    )
    return _skroutz_result(brand, mpn, category_phrase, differentiators, name, meta_title, seo_keyword, taxonomy)


def _build_coffee_filter_deterministic_fields(
    rule: SourceScopedRule,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
    brand: str,
    mpn: str,
    spec_lookup: dict[str, str],
) -> dict[str, object]:
    category_phrase = rule.category_phrase
    components = {
        "power": format_power(spec_lookup),
        "capacity": format_liters(spec_lookup, ["Χωρητικότητα Δοχείου Νερού σε Λίτρα"]),
        "cups": format_cups(spec_lookup),
    }
    differentiators = _source_rule_output_parts(rule, "name", components)
    name = compose_name(brand, mpn, category_phrase, differentiators)
    meta_title = compose_meta_title(
        name=name,
        brand=brand,
        mpn=mpn,
        category_phrase=category_phrase,
        differentiators=_source_rule_output_parts(rule, "meta_title", components),
        preserve_title=False,
    )
    seo_keyword = seo_keyword_builder(
        normalize_whitespace(
            " ".join(
                part
                for part in [
                    brand,
                    mpn,
                    category_phrase,
                    *_source_rule_output_parts(rule, "seo_keyword", {**components, "capacity_seo": format_capacity_for_seo(components["capacity"])}),
                ]
                if part
            )
        ),
        model,
    )
    return _skroutz_result(brand, mpn, category_phrase, differentiators, name, meta_title, seo_keyword, taxonomy)


def _build_fridge_freezer_deterministic_fields(
    rule: SourceScopedRule,
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
    brand: str,
    mpn: str,
    spec_lookup: dict[str, str],
) -> dict[str, object]:
    category_phrase = rule.category_phrase
    cooling = normalize_fridge_cooling(normalize_value(spec_lookup, ["Σύστημα Ψύξης", "Τεχνολογία Ψύξης"])) or normalize_fridge_cooling(
        extract_first_preferred_spec_value(source, [r"no\s*frost", r"nofrost", r"low\s*frost"])
    )
    capacity = format_liters(spec_lookup, ["Συνολική Χωρητικότητα", "Συνολική Καθαρή Χωρητικότητα", "Χωρητικότητα"]) or compact_unit_value(
        extract_first_preferred_spec_value(source, [r"\b\d+(?:[.,]\d+)?\s*lt\b"]),
        "Lt",
    )
    color = normalize_value(spec_lookup, ["Χρώμα", "Χρώμα Συσκευής", "Χρώμα / Φινίρισμα"]) or extract_first_preferred_spec_value(
        source, [r"\binox\b", r"metal look", r"silver", r"black", r"white", r"gray", r"grey"]
    )
    width = format_centimeters(spec_lookup, ["Πλάτος"]) or compact_unit_value(
        extract_first_preferred_spec_value(source, [r"\b\d+(?:[.,]\d+)?\s*cm\b"]),
        "cm",
    )
    energy_class = normalize_value(spec_lookup, ["Ενεργειακή Κλάση"]) or extract_energy_class_from_source(source)
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

def _build_kettle_deterministic_fields(
    rule: SourceScopedRule,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
    raw_title: str,
    brand: str,
    mpn: str,
    spec_lookup: dict[str, str],
) -> dict[str, object]:
    category_phrase = rule.category_phrase
    components = {
        "capacity": format_liters(spec_lookup, ["Χωρητικότητα σε Λίτρα"]),
        "power": format_power(spec_lookup),
        "color": derive_kettle_color(raw_title, spec_lookup),
    }
    differentiators = _source_rule_output_parts(rule, "name", components)
    name = compose_name(brand, mpn, category_phrase, differentiators)
    meta_title_value = normalize_whitespace(
        " ".join(part for part in [brand, mpn, category_phrase, *_source_rule_output_parts(rule, "meta_title", components)] if part)
    )
    meta_title = f"{meta_title_value} | eTranoulis" if meta_title_value else ""
    seo_tail = extract_skroutz_tail_from_title(raw_title, category_phrase) or normalize_whitespace(" ".join(item for item in [category_phrase, *differentiators] if item))
    seo_value = _source_rule_output_parts(rule, "seo_keyword", {"tail": seo_tail})
    seo_keyword = seo_keyword_builder(
        normalize_whitespace(" ".join(part for part in [brand, mpn, format_capacity_for_seo(seo_value[0] if seo_value else seo_tail)] if part)),
        model,
    )
    return _skroutz_result(brand, mpn, category_phrase, differentiators, name, meta_title, seo_keyword, taxonomy)


def _build_ice_cream_maker_deterministic_fields(
    rule: SourceScopedRule,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
    brand: str,
    mpn: str,
    spec_lookup: dict[str, str],
) -> dict[str, object]:
    category_phrase = rule.category_phrase
    bowls = format_count_differentiator(spec_lookup, ["Αριθμός Δοχείων"], singular="Δοχείου", plural="Δοχείων")
    color = normalize_value(spec_lookup, ["Χρώμα"])
    components = {
        "capacity": format_liters(spec_lookup, ["Χωρητικότητα"]),
        "programs": format_program_count(spec_lookup, ["Αριθμός Προγραμμάτων"]),
        "bowls_or_color": bowls or color,
        "bowls": bowls,
        "color": color,
    }
    differentiators = _source_rule_output_parts(rule, "name", components)
    name = compose_name(brand, mpn, category_phrase, differentiators)
    meta_title = compose_meta_title(
        name=name,
        brand=brand,
        mpn=mpn,
        category_phrase=category_phrase,
        differentiators=_source_rule_output_parts(rule, "meta_title", components),
        preserve_title=False,
    )
    seo_keyword = seo_keyword_builder(
        normalize_whitespace(" ".join(part for part in [brand, mpn, category_phrase, *_source_rule_output_parts(rule, "seo_keyword", components)] if part)),
        model,
    )
    return _skroutz_result(brand, mpn, category_phrase, differentiators, name, meta_title, seo_keyword, taxonomy)


def _build_tabletop_hob_deterministic_fields(
    rule: SourceScopedRule,
    taxonomy: TaxonomyResolution,
    model: str,
    seo_keyword_builder,
    raw_title: str,
    brand: str,
    mpn: str,
    spec_lookup: dict[str, str],
) -> dict[str, object]:
    category_phrase = rule.category_phrase
    burner_phrase = derive_hob_burner_phrase(spec_lookup, raw_title)
    power = format_power(spec_lookup, ["Ισχύς"])
    surface = normalize_value(spec_lookup, ["Τύπος Εστίας"])
    components = {
        "burner_phrase": burner_phrase,
        "power": power,
        "surface": surface,
        "seo_name": compose_name(brand, mpn, category_phrase, [normalize_hob_burners_for_seo(burner_phrase), power, surface]),
    }
    differentiators = _source_rule_output_parts(rule, "name", components)
    name = compose_name(brand, mpn, category_phrase, differentiators)
    meta_title = compose_meta_title(
        name=name,
        brand=brand,
        mpn=mpn,
        category_phrase=category_phrase,
        differentiators=_source_rule_output_parts(rule, "meta_title", components),
        preserve_title=False,
    )
    seo_parts = _source_rule_output_parts(rule, "seo_keyword", components)
    seo_keyword = seo_keyword_builder(seo_parts[0] if seo_parts else name, model)
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
    if sub == normalize_for_match("Παγωτομηχανές") and leaf == normalize_for_match("Μικροί Μάγειρες"):
        return "ice_cream_maker"
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
    title_tail = normalize_whitespace(source.name).split()[-1] if normalize_whitespace(source.name) else ""
    energy_class = normalize_value(spec_lookup, ["?????????? ?????"]) or extract_energy_class_from_source(source) or (title_tail.upper() if ENERGY_CLASS_TOKEN_RE.fullmatch(title_tail) else "")
    cooling = normalize_value(spec_lookup, ["Τεχνολογία Ψύξης"])
    connectivity = normalize_connectivity(normalize_value(spec_lookup, ["Συνδεσιμότητα"]))
    family = extract_commercial_family_from_title(source.name, brand, mpn)
    color = normalize_color_differentiator(spec_lookup) or extract_title_suffix_differentiator(source.name, brand, mpn)

    for value in [cooling, capacity, energy_class, family, color, connectivity]:
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


def _preferred_spec_values(source: SourceProductData) -> list[str]:
    prefer_manufacturer = _prefer_manufacturer_evidence(source)
    return [
        normalize_whitespace(item.value)
        for item in iter_specs(
            source.key_specs,
            effective_spec_sections(source, manufacturer_first=prefer_manufacturer),
            key_specs_last=prefer_manufacturer,
        )
        if normalize_whitespace(item.value)
    ]


def _extract_energy_class_from_value(value: str) -> str:
    for token in re.findall(r"\b([A-G](?:\+{1,3})?)\b", normalize_whitespace(value), flags=re.IGNORECASE):
        if ENERGY_CLASS_TOKEN_RE.fullmatch(token):
            return token.upper()
    return ""


def extract_title_energy_class(value: str) -> str:
    match = re.search(r"\b([A-G](?:\+{1,3})?)\b\s*$", normalize_whitespace(value), flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def extract_energy_class_from_source(source: SourceProductData) -> str:
    for value in _preferred_spec_values(source):
        extracted = _extract_energy_class_from_value(value)
        if extracted:
            return extracted
    return extract_title_energy_class(source.name) or _extract_energy_class_from_value(source.name)


def extract_first_preferred_spec_value(source: SourceProductData, patterns: list[str]) -> str:
    compiled = [re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns]
    for value in _preferred_spec_values(source):
        normalized = normalize_whitespace(value)
        if any(pattern.search(normalized) for pattern in compiled):
            return normalized
    return ""


def build_spec_lookup(key_specs: list[SpecItem], spec_sections: list[SpecSection], *, key_specs_last: bool = False) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in iter_specs(key_specs, spec_sections, key_specs_last=key_specs_last):
        label = normalize_for_match(item.label) or normalize_whitespace(item.label)
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
    normalized_labels = {
        normalized
        for label in labels
        for normalized in [normalize_for_match(label) or normalize_whitespace(label)]
        if normalized
    }
    for label, value in spec_lookup.items():
        if label in normalized_labels and value:
            return normalize_whitespace(value)
    return ""


def _normalize_rule_aliases(aliases: list[str]) -> list[str]:
    normalized_aliases: list[str] = []
    for alias in aliases:
        normalized = normalize_for_match(alias) or normalize_whitespace(alias)
        if normalized and normalized not in normalized_aliases:
            normalized_aliases.append(normalized)
    return normalized_aliases


def _score_spec_label_match(label: str, normalized_aliases: list[str]) -> int:
    normalized_label = normalize_for_match(label) or normalize_whitespace(label)
    if not normalized_label:
        return 0
    label_tokens = [token for token in normalized_label.split() if len(token) >= 2]
    best_score = 0
    for alias in normalized_aliases:
        alias_tokens = [token for token in alias.split() if len(token) >= 2]
        if len(alias_tokens) == 1:
            alias_token = alias_tokens[0]
            if alias_token in FUZZY_ALIAS_DENYLIST:
                continue
            if alias_token not in FUZZY_SINGLE_TOKEN_ALLOWLIST and len(alias_token) < 8:
                continue
        if len(alias) >= 2 and (alias in normalized_label or normalized_label in alias):
            best_score = max(best_score, 100 + len(alias))
            continue
        if not alias_tokens:
            continue
        overlap = sum(
            1
            for alias_token in alias_tokens
            if any(
                alias_token == label_token or alias_token in label_token or label_token in alias_token
                for label_token in label_tokens
            )
        )
        if overlap:
            best_score = max(best_score, overlap * 10 + len(alias_tokens))
    return best_score


def resolve_spec_value(spec_lookup: dict[str, str], aliases: list[str]) -> ResolvedNameComponent:
    normalized_aliases = _normalize_rule_aliases(aliases)
    if not normalized_aliases:
        return ResolvedNameComponent("")

    for alias in normalized_aliases:
        value = normalize_whitespace(spec_lookup.get(alias, ""))
        if value:
            return ResolvedNameComponent(value=value, matched_label=alias, source="exact_spec")

    best_match: ResolvedNameComponent | None = None
    best_score = 0
    for label, value in spec_lookup.items():
        normalized_value = normalize_whitespace(value)
        if not normalized_value:
            continue
        score = _score_spec_label_match(label, normalized_aliases)
        if score > best_score:
            best_score = score
            best_match = ResolvedNameComponent(value=normalized_value, matched_label=label, source="fuzzy_spec")
    return best_match or ResolvedNameComponent("")


def compact_numeric_string(value: str) -> str:
    numeric = extract_numeric(value)
    if not numeric:
        return ""
    return re.sub(r",0+$", "", numeric)


def compact_unit_value(value: str, unit: str) -> str:
    numeric = compact_numeric_string(value)
    if not numeric:
        return normalize_whitespace(value)
    return f"{numeric}{unit}"


def extract_measurement_from_text(text: str, aliases: list[str]) -> str:
    normalized_text = normalize_whitespace(text)
    alias_keys = set(_normalize_rule_aliases(aliases))
    patterns: list[str] = []
    if "volt" in alias_keys or "v" in alias_keys or any("Ο„Ξ±ΟƒΞ·" in alias for alias in alias_keys):
        patterns.append(r"\b\d+(?:[.,]\d+)?\s*(?:volt|v)\b")
    if "watt" in alias_keys or any("ΞΉΟƒΟ‡Ο…" in alias for alias in alias_keys):
        patterns.append(r"\b\d+(?:[.,]\d+)?\s*(?:watt(?:s)?|w)\b")
    if "lt" in alias_keys or any("Ξ»ΞΉΟ„Ο" in alias or "Ο‡Ο‰ΟΞ·Ο„ΞΉΞΊΟΟ„" in alias for alias in alias_keys):
        patterns.append(r"\b\d+(?:[.,]\d+)?\s*(?:lt|l|λιτρα|λίτρα)\b")
    if "kg" in alias_keys or any(token in alias for alias in alias_keys for token in ("ΞΊΞΉΞ»Ξ±", "Ο†ΞΏΟΟ„ΞΉ", "Ο€Ξ»Ο…ΟƒΞ·", "ΟƒΟ„ΞµΞ³Ξ½Ο‰ΞΌΞ±")):
        patterns.append(r"\b\d+(?:[.,]\d+)?\s*(?:kg|κιλα|κιλό|κιλά)\b")
    if "cm" in alias_keys or any(token in alias for alias in alias_keys for token in ("ΞµΞΊΞ±Ο„ΞΏΟƒΟ„", "Ο€Ξ»Ξ±Ο„ΞΏΟ‚", "Ξ²Ξ±ΞΈΞΏΟ‚", "Ο…ΟΞΏΟ‚", "Ξ΄ΞΉΞ±ΞΌΞµΟ„ΟΞΏ")):
        patterns.append(r"\b\d+(?:[.,]\d+)?\s*(?:cm|εκατοστ(?:ά|α)|εκατοστά)\b")
    for pattern in patterns:
        match = re.search(pattern, normalized_text, flags=re.IGNORECASE)
        if match:
            return normalize_whitespace(match.group(0))
    return ""


def infer_measurement_unit(
    aliases: list[str],
    matched_label: str,
    category_phrase: str,
    taxonomy: TaxonomyResolution,
    value: str = "",
) -> str:
    alias_keys = set(_normalize_rule_aliases(aliases))
    label_context = normalize_for_match(" ".join([matched_label, *alias_keys, value]))
    if "volt" in label_context or "ταση" in label_context or "v" in alias_keys:
        return "V"
    if "watt" in label_context or "ισχυ" in label_context:
        return "W"
    if "lt" in label_context or "λιτρ" in label_context:
        return "Lt"
    if "cm" in label_context or any(token in label_context for token in ("εκατοστ", "πλατος", "βαθος", "υψος", "διαμετρο")):
        return "cm"
    if "kg" in label_context or any(token in label_context for token in ("κιλα", "βαρος", "φορτι", "πλυση", "στεγνωμα")):
        return "kg"
    if "χωρητικοτ" in label_context:
        inferred = infer_capacity_unit(category_phrase, taxonomy)
        if inferred == "Kg":
            return "kg"
        if inferred == "Lt":
            return "Lt"
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
        if not resolved.value:
            return ""
        resolved_parts.append(resolved.value)
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
) -> ResolvedNameComponent:
    spec_value = resolve_spec_value(spec_lookup, aliases)
    if spec_value.value:
        return ResolvedNameComponent(
            value=normalize_name_rule_value(
                spec_value.value,
                aliases,
                category_phrase,
                taxonomy,
                matched_label=spec_value.matched_label,
            ),
            matched_label=spec_value.matched_label,
            source=spec_value.source,
        )

    fallback_value = extract_alias_value_from_evidence(source, aliases)
    if fallback_value:
        return ResolvedNameComponent(
            value=normalize_name_rule_value(fallback_value, aliases, category_phrase, taxonomy),
            source="fallback_evidence",
        )
    return ResolvedNameComponent("")


def normalize_name_rule_value(
    value: str,
    aliases: list[str],
    category_phrase: str,
    taxonomy: TaxonomyResolution,
    *,
    matched_label: str = "",
) -> str:
    normalized = normalize_whitespace(value)
    if not normalized:
        return ""
    alias_keys = {normalize_for_match(alias) for alias in aliases}
    unit = infer_measurement_unit(aliases, matched_label, category_phrase, taxonomy, normalized)
    if unit and not _is_tv_scope(category_phrase, taxonomy):
        return compact_unit_value(normalized, unit)
    if _is_tv_scope(category_phrase, taxonomy):
        tv_normalized = _normalize_tv_name_rule_value(normalized, alias_keys)
        if _is_tv_platform_alias(alias_keys):
            return tv_normalized
        normalized = tv_normalized or normalized
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


def _is_tv_scope(category_phrase: str, taxonomy: TaxonomyResolution) -> bool:
    haystack = normalize_for_match(" ".join([category_phrase, taxonomy.sub_category or "", taxonomy.leaf_category]))
    return "τηλεορασ" in haystack


def _normalize_tv_name_rule_value(value: str, alias_keys: set[str]) -> str:
    normalized_value = normalize_whitespace(value)
    if not normalized_value:
        return ""
    alias_text = " ".join(sorted(alias_keys))
    if any(token in alias_text for token in ("διαγων", "μεγεθοσ οθον", "μεγεθος οθον")):
        inches = extract_numeric(normalized_value)
        if inches:
            return f'{inches}"'
    if any(token in alias_text for token in ("αναλυση", "ευκριν")):
        return _normalize_tv_resolution(normalized_value)
    if _is_tv_platform_alias(alias_keys):
        return _normalize_tv_platform(normalized_value)
    return normalized_value


def _is_tv_platform_alias(alias_keys: set[str]) -> bool:
    alias_text = " ".join(sorted(alias_keys))
    return any(
        token in alias_text
        for token in (
            "λειτουργικ",
            "λογισμικ",
            "πλατφορμ",
            "operating system",
            "smart platform",
            "google tv",
            "webos",
            "tizen",
            "android tv",
            "smart tv",
        )
    )


def _normalize_tv_resolution(value: str) -> str:
    normalized = normalize_for_match(value)
    if "full hd" in normalized:
        return "Full HD"
    if "hd ready" in normalized:
        return "HD Ready"
    if "8k" in normalized:
        return "8K"
    if "4k" in normalized:
        return "4K"
    return normalize_whitespace(value)


def _normalize_tv_platform(value: str) -> str:
    normalized = normalize_for_match(value)
    if normalized in {"ναι", "οχι", "υποστηριζεται", "supported", "yes", "no", "true", "false"}:
        return ""
    if "google tv" in normalized:
        return "Google TV"
    if "android tv" in normalized:
        return "Android TV"
    if "webos" in normalized:
        return "webOS"
    if "tizen" in normalized:
        return "Tizen"
    if "smart tv" in normalized:
        return "Smart TV"
    return normalize_whitespace(value)


def _tv_differentiator_key(value: str) -> str:
    normalized = normalize_whitespace(value)
    if not normalized:
        return ""
    platform_key = _tv_platform_key(normalized)
    if platform_key:
        return f"platform:{platform_key}"
    resolution_key = _tv_resolution_key(normalized)
    if resolution_key:
        return f"resolution:{resolution_key}"
    return normalize_for_match(normalized)


def _tv_platform_key(value: str) -> str:
    normalized = normalize_for_match(value)
    if "google tv" in normalized:
        return "google_tv"
    if "android tv" in normalized:
        return "android_tv"
    if "webos" in normalized:
        return "webos"
    if "tizen" in normalized:
        return "tizen"
    if "smart tv" in normalized:
        return "smart_tv"
    return ""


def _tv_resolution_key(value: str) -> str:
    normalized = normalize_for_match(value)
    if "8k" in normalized:
        return "8k"
    if "4k" in normalized:
        return "4k"
    if "full hd" in normalized:
        return "full_hd"
    if "hd ready" in normalized:
        return "hd_ready"
    return ""


def _is_generic_tv_platform(value: str) -> bool:
    return _tv_platform_key(value) == "smart_tv"


def _is_concrete_tv_platform(value: str) -> bool:
    platform_key = _tv_platform_key(value)
    return bool(platform_key) and platform_key != "smart_tv"


def _append_tv_differentiator(differentiators: list[str], value: str, max_differentiators: int) -> list[str]:
    candidate = normalize_whitespace(value)
    if not candidate:
        return differentiators

    candidate_key = _tv_differentiator_key(candidate)
    if not candidate_key:
        return differentiators

    if _is_generic_tv_platform(candidate):
        if any(_is_concrete_tv_platform(existing) for existing in differentiators):
            return differentiators
        if any(_tv_differentiator_key(existing) == candidate_key for existing in differentiators):
            return differentiators
        if len(differentiators) < max_differentiators:
            differentiators.append(candidate)
        return differentiators

    if _is_concrete_tv_platform(candidate):
        for index, existing in enumerate(differentiators):
            if _is_generic_tv_platform(existing):
                differentiators[index] = candidate
                return differentiators
        if any(_tv_differentiator_key(existing) == candidate_key for existing in differentiators):
            return differentiators
        if len(differentiators) < max_differentiators:
            differentiators.append(candidate)
        return differentiators

    if any(_tv_differentiator_key(existing) == candidate_key for existing in differentiators):
        return differentiators
    if len(differentiators) < max_differentiators:
        differentiators.append(candidate)
    return differentiators


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
        measurement = extract_measurement_from_text(text, aliases)
        if measurement:
            return measurement
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
    if unit == "Kg":
        return compact_unit_value(numeric, "kg")
    if unit == "Lt":
        return compact_unit_value(numeric, "Lt")
    return numeric


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
    return compact_unit_value(raw, "W")


def format_liters(spec_lookup: dict[str, str], labels: list[str]) -> str:
    raw = normalize_value(spec_lookup, labels)
    if not raw:
        return ""
    return compact_unit_value(raw, "Lt")


def format_centimeters(spec_lookup: dict[str, str], labels: list[str]) -> str:
    raw = normalize_value(spec_lookup, labels)
    if not raw:
        return ""
    return compact_unit_value(raw, "cm")


def format_program_count(spec_lookup: dict[str, str], labels: list[str]) -> str:
    raw = normalize_value(spec_lookup, labels)
    numeric = extract_numeric(raw)
    if not numeric:
        return ""
    return f"{numeric} Προγράμματος" if numeric == "1" else f"{numeric} Προγραμμάτων"


def format_count_differentiator(spec_lookup: dict[str, str], labels: list[str], singular: str, plural: str) -> str:
    raw = normalize_value(spec_lookup, labels)
    numeric = extract_numeric(raw)
    if not numeric:
        return ""
    suffix = singular if numeric == "1" else plural
    return f"{numeric} {suffix}"


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
