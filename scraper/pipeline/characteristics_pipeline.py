from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from bs4 import BeautifulSoup

from .deterministic_fields import build_spec_lookup, effective_spec_sections
from .html_builders import build_characteristics_html
from .models import SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from .normalize import normalize_for_match, normalize_whitespace
from .repo_paths import CHARACTERISTICS_TEMPLATES_PATH, SCHEMA_LIBRARY_PATH
from .utils import dedupe_strings, read_json


TV_INCH_TO_CM = {
    24: 61,
    32: 81,
    40: 101,
    42: 106,
    43: 108,
    48: 121,
    50: 126,
    55: 139,
    58: 146,
    65: 164,
    70: 177,
    75: 189,
    77: 195,
    83: 210,
    85: 215,
    98: 248,
}
RESOLUTION_TO_PIXELS = {
    "hd ready": "1366 × 768",
    "full hd": "1920 × 1080",
    "ultra hd ( 4k )": "3840 × 2160",
    "ultra hd ( 8k )": "7680 × 4320",
}
_REGISTRY: CharacteristicsTemplateRegistry | None = None


@dataclass(slots=True)
class _ResolutionContext:
    source: SourceProductData
    taxonomy: TaxonomyResolution
    spec_lookup: dict[str, str]
    raw_lookup: dict[str, str]
    section_lookup: dict[str, dict[str, str]]
    raw_html: str
    raw_text: str
    offer_titles: list[str]
    combined_text: str


class CharacteristicsTemplateRegistry:
    def __init__(self, path: str = str(CHARACTERISTICS_TEMPLATES_PATH)) -> None:
        self.path = path
        payload = read_json(path)
        self.templates: list[dict[str, Any]] = payload.get("templates", [])
        schema_payload = read_json(SCHEMA_LIBRARY_PATH)
        self.schemas_by_id: dict[str, dict[str, Any]] = {
            str(schema.get("schema_id", "")).strip(): schema
            for schema in schema_payload.get("schemas", [])
            if str(schema.get("schema_id", "")).strip()
        }

    def select_custom_template(self, source: SourceProductData, taxonomy: TaxonomyResolution) -> dict[str, Any] | None:
        source_name = normalize_for_match(source.source_name)
        parent = normalize_for_match(taxonomy.parent_category)
        leaf = normalize_for_match(taxonomy.leaf_category)
        sub = normalize_for_match(taxonomy.sub_category or "")
        for template in self.templates:
            match = template.get("match", {})
            if normalize_for_match(match.get("source_name", "")) not in {"", source_name}:
                continue
            if normalize_for_match(match.get("taxonomy_parent", "")) not in {"", parent}:
                continue
            if normalize_for_match(match.get("taxonomy_leaf", "")) not in {"", leaf}:
                continue
            if normalize_for_match(match.get("taxonomy_sub", "")) not in {"", sub}:
                continue
            return template
        return None

    def select_template(
        self,
        source: SourceProductData,
        taxonomy: TaxonomyResolution,
        schema_match: SchemaMatchResult | None = None,
    ) -> dict[str, Any] | None:
        custom_template = self.select_custom_template(source, taxonomy)
        if custom_template is not None and _template_requests_raw_spec_sections(custom_template):
            return {
                **custom_template,
                "template_source": "custom",
                "matched_schema_id": schema_match.matched_schema_id if schema_match else "",
            }
        schema_template = self.select_schema_template(schema_match.matched_schema_id if schema_match else None)
        if schema_template is not None:
            if custom_template is not None:
                return self.merge_template_overrides(schema_template, custom_template)
            return schema_template
        if custom_template is not None:
            return {
                **custom_template,
                "template_source": "custom",
                "matched_schema_id": "",
            }
        return None

    def select_schema_template(self, schema_id: str | None) -> dict[str, Any] | None:
        if not schema_id:
            return None
        schema = self.schemas_by_id.get(str(schema_id).strip())
        if schema is None:
            return None
        sections: list[dict[str, Any]] = []
        for section_index, section in enumerate(schema.get("sections", []), start=1):
            section_title = normalize_whitespace(section.get("title", ""))
            if not section_title:
                continue
            labels = [normalize_whitespace(label) for label in section.get("labels", []) if normalize_whitespace(label)]
            fields = [
                {
                    "key": normalize_for_match(f"{section_title} {label}") or f"schema_{section_index}_{label_index}",
                    "label": label,
                    "aliases": [label],
                    "section_title": section_title,
                }
                for label_index, label in enumerate(labels, start=1)
            ]
            sections.append({"title": section_title, "fields": fields})
        return {
            "template_id": f"schema:{schema_id}",
            "template_source": "schema_library",
            "matched_schema_id": schema_id,
            "preferred_schema_source_files": list(schema.get("source_files", [])),
            "sections": sections,
        }

    def merge_template_overrides(self, schema_template: dict[str, Any], custom_template: dict[str, Any]) -> dict[str, Any]:
        custom_sections = list(custom_template.get("sections", []))
        merged_sections: list[dict[str, Any]] = []
        for index, base_section in enumerate(schema_template.get("sections", [])):
            custom_section = self._match_custom_section(base_section, custom_sections, index)
            merged_fields: list[dict[str, Any]] = []
            for field_index, base_field in enumerate(base_section.get("fields", [])):
                custom_field = self._match_custom_field(base_field, custom_section, field_index)
                merged_field = dict(base_field)
                if custom_field:
                    merged_field.update(custom_field)
                    if "aliases" in custom_field:
                        merged_field["aliases"] = list(custom_field.get("aliases", []))
                merged_fields.append(merged_field)
            merged_sections.append(
                {
                    "title": custom_section.get("title", base_section.get("title", "")) if custom_section else base_section.get("title", ""),
                    "fields": merged_fields,
                }
            )
        return {
            **schema_template,
            "template_source": "schema_library_with_custom_overrides",
            "custom_template_id": custom_template.get("template_id", ""),
            "preferred_schema_source_files": dedupe_strings(
                [
                    *[str(item) for item in schema_template.get("preferred_schema_source_files", [])],
                    *[str(item) for item in custom_template.get("preferred_schema_source_files", [])],
                ]
            ),
            "sections": merged_sections,
        }

    def _match_custom_section(self, base_section: dict[str, Any], custom_sections: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
        base_title = normalize_for_match(base_section.get("title", ""))
        for section in custom_sections:
            if normalize_for_match(section.get("title", "")) == base_title:
                return section
        if 0 <= index < len(custom_sections):
            return custom_sections[index]
        return None

    def _match_custom_field(
        self,
        base_field: dict[str, Any],
        custom_section: dict[str, Any] | None,
        index: int,
    ) -> dict[str, Any] | None:
        if not custom_section:
            return None
        base_label = normalize_for_match(base_field.get("label", ""))
        fields = list(custom_section.get("fields", []))
        for field in fields:
            if normalize_for_match(field.get("label", "")) == base_label:
                return field
        if any(normalize_for_match(field.get("label", "")) for field in fields):
            return None
        if 0 <= index < len(fields):
            return fields[index]
        return None

    def preferred_schema_source_files(self, source: SourceProductData, taxonomy: TaxonomyResolution) -> list[str]:
        template = self.select_custom_template(source, taxonomy)
        if not template:
            return []
        return [str(item).strip() for item in template.get("preferred_schema_source_files", []) if str(item).strip()]


def get_characteristics_registry() -> CharacteristicsTemplateRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = CharacteristicsTemplateRegistry()
    return _REGISTRY


def build_characteristics_for_product(
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    schema_match: SchemaMatchResult | None = None,
    raw_html: str | None = None,
) -> tuple[str, dict[str, Any], list[str]]:
    registry = get_characteristics_registry()
    template = registry.select_template(source, taxonomy, schema_match=schema_match)
    if template is None:
        return _build_raw_spec_sections_result(source, schema_match=schema_match)

    if _template_requests_raw_spec_sections(template):
        return _build_raw_spec_sections_result(source, schema_match=schema_match, template=template)

    context = _build_resolution_context(source, taxonomy, raw_html=raw_html)
    warnings = [f"characteristics_template_used:{template['template_id']}"]
    diagnostics_fields: list[dict[str, Any]] = []
    resolved_sections: list[SpecSection] = []
    unresolved_count = 0
    template_source = normalize_whitespace(template.get("template_source")) or "custom"
    matched_schema_id = normalize_whitespace(template.get("matched_schema_id")) or (schema_match.matched_schema_id if schema_match else "")

    for section in template.get("sections", []):
        items: list[SpecItem] = []
        for field in section.get("fields", []):
            value, resolved_from = _resolve_template_field(context, field)
            normalized_value = normalize_whitespace(value) or "-"
            if normalized_value == "-":
                unresolved_count += 1
            items.append(SpecItem(label=str(field.get("label", "")).strip(), value=normalized_value))
            diagnostics_fields.append(
                {
                    "section": section.get("title", ""),
                    "key": field.get("key", ""),
                    "label": field.get("label", ""),
                    "value": normalized_value,
                    "resolved_from": resolved_from,
                }
            )
        resolved_sections.append(SpecSection(section=str(section.get("title", "")).strip(), items=items))

    if unresolved_count:
        warnings.append(f"characteristics_template_unresolved_fields:{unresolved_count}")

    diagnostics = {
        "mode": "template",
        "template_id": template.get("template_id", ""),
        "selection_reason": (
            "matched_schema_template_with_custom_overrides"
            if template_source == "schema_library_with_custom_overrides"
            else "matched_schema_template"
            if template_source == "schema_library"
            else "taxonomy_template_match"
        ),
        "template_source": template_source,
        "matched_schema_id": matched_schema_id,
        "custom_template_id": template.get("custom_template_id", ""),
        "preferred_schema_source_files": list(template.get("preferred_schema_source_files", [])),
        "field_count": len(diagnostics_fields),
        "unresolved_count": unresolved_count,
        "fields": diagnostics_fields,
    }
    return build_characteristics_html(resolved_sections), diagnostics, warnings


def _build_raw_spec_sections_result(
    source: SourceProductData,
    schema_match: SchemaMatchResult | None = None,
    template: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any], list[str]]:
    effective_sections = _effective_spec_sections(source)
    template_source = normalize_whitespace(template.get("template_source")) if template else ""
    diagnostics = {
        "mode": "raw_spec_sections",
        "template_id": template.get("template_id", "") if template else "",
        "selection_reason": "taxonomy_template_raw_spec_sections" if template else "no_matching_template",
        "template_source": template_source,
        "matched_schema_id": schema_match.matched_schema_id if schema_match else "",
        "preferred_schema_source_files": list(template.get("preferred_schema_source_files", [])) if template else [],
        "custom_template_id": template.get("template_id", "") if template_source == "custom" else "",
        "field_count": sum(len(section.items) for section in effective_sections),
        "unresolved_count": 0,
        "fields": [],
    }
    return build_characteristics_html(effective_sections), diagnostics, []


def _template_requests_raw_spec_sections(template: dict[str, Any]) -> bool:
    normalized = normalize_whitespace(str(template.get("render_mode", ""))).lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    return normalized == "raw_spec_sections"


def _build_resolution_context(
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    *,
    raw_html: str | None = None,
) -> _ResolutionContext:
    resolved_raw_html = raw_html or ""
    if not resolved_raw_html:
        raw_path = normalize_whitespace(source.raw_html_path)
        if raw_path:
            path = Path(raw_path)
            if path.exists():
                resolved_raw_html = path.read_text(encoding="utf-8")

    spec_sections = _effective_spec_sections(source)
    prefer_manufacturer = normalize_for_match(source.source_name) == "skroutz" and bool(source.manufacturer_spec_sections)
    spec_lookup = build_spec_lookup(source.key_specs, spec_sections, key_specs_last=prefer_manufacturer)
    raw_lookup = _extract_dt_dd_lookup(resolved_raw_html)
    section_lookup = _build_section_lookup(spec_sections)
    offer_titles = _extract_offer_titles(resolved_raw_html)
    raw_text = _extract_raw_text(resolved_raw_html)
    combined_text = normalize_whitespace(
        " ".join(
            part
            for part in [
                source.name,
                source.hero_summary,
                source.presentation_source_text,
                source.manufacturer_source_text,
                raw_text,
                *offer_titles,
            ]
            if normalize_whitespace(part)
        )
    )
    return _ResolutionContext(
        source=source,
        taxonomy=taxonomy,
        spec_lookup=spec_lookup,
        raw_lookup=raw_lookup,
        section_lookup=section_lookup,
        raw_html=resolved_raw_html,
        raw_text=raw_text,
        offer_titles=offer_titles,
        combined_text=combined_text,
    )


def _effective_spec_sections(source: SourceProductData) -> list[SpecSection]:
    return effective_spec_sections(source, manufacturer_first=normalize_for_match(source.source_name) == "skroutz")


def _extract_dt_dd_lookup(raw_html: str) -> dict[str, str]:
    if not raw_html:
        return {}
    soup = BeautifulSoup(raw_html, "lxml")
    lookup: dict[str, str] = {}
    for dt in soup.select("dt"):
        dd = dt.find_next_sibling("dd")
        if dd is None:
            continue
        key = normalize_for_match(dt.get_text(" ", strip=True))
        value = normalize_whitespace(dd.get_text(" ", strip=True))
        if key and value and key not in lookup:
            lookup[key] = value
    return lookup


def _build_section_lookup(spec_sections: list[SpecSection]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for section in spec_sections:
        section_key = normalize_for_match(section.section)
        if not section_key:
            continue
        values = lookup.setdefault(section_key, {})
        for item in section.items:
            label_key = normalize_for_match(item.label)
            value = normalize_whitespace(item.value)
            if label_key and value and label_key not in values:
                values[label_key] = value
    return lookup


def _extract_offer_titles(raw_html: str) -> list[str]:
    if not raw_html:
        return []
    soup = BeautifulSoup(raw_html, "lxml")
    return dedupe_strings(node.get("title", "") for node in soup.select(".product-name[title]"))


def _extract_raw_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "lxml")
    return normalize_whitespace(soup.get_text(" ", strip=True))


def _resolve_template_field(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    resolver_name = str(field.get("resolver", "")).strip()
    resolver = _RESOLVERS.get(resolver_name)
    if resolver is None:
        aliases = list(field.get("aliases", [])) or [str(field.get("label", "")).strip()]
        value, source = _first_value_from_aliases(
            context,
            aliases,
            section_name=str(field.get("section_title", "")).strip(),
        )
        return value, source or "unresolved"
    return resolver(context, field)


def _first_value_from_aliases(context: _ResolutionContext, aliases: list[str], section_name: str = "") -> tuple[str, str]:
    if section_name:
        for alias in aliases:
            value, source = _section_value(context, section_name, alias)
            if value:
                return value, source
    for alias in aliases:
        key = normalize_for_match(alias)
        if key in context.spec_lookup:
            return context.spec_lookup[key], f"spec_alias:{alias}"
    for alias in aliases:
        key = normalize_for_match(alias)
        if key in context.raw_lookup:
            return context.raw_lookup[key], f"raw_alias:{alias}"
    return "", ""


def _section_value(context: _ResolutionContext, section_name: str, label: str) -> tuple[str, str]:
    section_key = normalize_for_match(section_name)
    label_key = normalize_for_match(label)
    if section_key in context.section_lookup and label_key in context.section_lookup[section_key]:
        return context.section_lookup[section_key][label_key], f"section:{section_name}/{label}"
    if section_key in context.section_lookup:
        for candidate_label, candidate_value in context.section_lookup[section_key].items():
            if _labels_related(candidate_label, label_key) and candidate_value:
                return candidate_value, f"section_label_related:{section_name}/{label}"
    for candidate_section in _effective_spec_sections(context.source):
        candidate_key = normalize_for_match(candidate_section.section)
        if not _section_titles_related(section_key, candidate_key):
            continue
        for item in candidate_section.items:
            item_key = normalize_for_match(item.label)
            value = normalize_whitespace(item.value)
            if (item_key == label_key or _labels_related(item_key, label_key)) and value:
                return value, f"section_related:{candidate_section.section}/{label}"
    return "", ""


def _labels_related(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    compact_left = normalize_whitespace(re.sub(r"\b[χx]\b", " ", left))
    compact_right = normalize_whitespace(re.sub(r"\b[χx]\b", " ", right))
    return bool(compact_left and compact_left == compact_right)


def _value_or_unresolved(value: str, source: str) -> tuple[str, str]:
    normalized = normalize_whitespace(value)
    if normalized:
        return normalized, source or "resolved"
    return "", "unresolved"


def _extract_first_number(value: str) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", value or "")
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _extract_int_from_text(text: str) -> int | None:
    number = _extract_first_number(text)
    if number is None:
        return None
    return int(round(number))


def _tv_inches_int(context: _ResolutionContext) -> tuple[int | None, str]:
    if context.source.taxonomy_tv_inches:
        return int(context.source.taxonomy_tv_inches), "taxonomy_tv_inches"
    value, source = _first_value_from_aliases(context, ["Διαγώνιος", "Διαγώνιος Οθόνης ( Ίντσες )"])
    parsed = _extract_int_from_text(value)
    if parsed is not None:
        return parsed, source
    title_match = re.search(r"\b(\d{2,3})\s*(?:\"|''|ιντσ|inch|in)\b", context.combined_text, flags=re.IGNORECASE)
    if title_match:
        return int(title_match.group(1)), "title_inches"
    return None, ""


def _normalize_panel(value: str) -> str:
    normalized = normalize_for_match(value)
    if "oled" in normalized:
        return "OLED"
    if "qned" in normalized:
        return "QNED"
    if "qled" in normalized:
        return "QLED"
    if "mini led" in normalized:
        return "Mini LED"
    if "direct led" in normalized or "dled" in normalized or normalized == "led" or normalized.endswith(" led"):
        return "LED"
    return normalize_whitespace(value)


def _map_resolution(value: str) -> str:
    normalized = normalize_for_match(value)
    if "8k" in normalized:
        return "ULTRA HD ( 8K )"
    if "4k" in normalized or "ultra hd" in normalized:
        return "ULTRA HD ( 4K )"
    if "full hd" in normalized or "1080" in normalized:
        return "FULL HD"
    if "hd ready" in normalized:
        return "HD READY"
    return normalize_whitespace(value).upper()


def _format_pixels(value: str) -> str:
    match = re.search(r"(\d{3,4})\s*[x×]\s*(\d{3,4})", value or "", flags=re.IGNORECASE)
    if not match:
        return ""
    return f"{match.group(1)} × {match.group(2)}"


def _contains_any(text: str, *tokens: str) -> bool:
    haystack = normalize_for_match(text)
    return any(normalize_for_match(token) in haystack for token in tokens if token)


def _section_titles_related(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    left_tokens = {token for token in left.split() if token}
    right_tokens = {token for token in right.split() if token}
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    return overlap >= max(1, min(len(left_tokens), len(right_tokens)) // 2)


def _ordered_features(context: _ResolutionContext, candidates: list[tuple[str, tuple[str, ...]]]) -> list[str]:
    values: list[str] = []
    for display, tokens in candidates:
        if any(_contains_any(context.combined_text, token) for token in tokens):
            values.append(display)
    return values


def _resolve_tv_screen_technology(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    if value:
        return _normalize_panel(value), source
    if any(_contains_any(title, "dled", "direct led", "led") for title in context.offer_titles):
        return "LED", "offer_title:panel"
    return "", "unresolved"


def _resolve_tv_screen_size_inches(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    inches, source = _tv_inches_int(context)
    return (str(inches), source) if inches is not None else ("", "unresolved")


def _resolve_tv_screen_size_cm(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    for title in context.offer_titles:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*cm\b", title, flags=re.IGNORECASE)
        if match:
            return str(int(float(match.group(1).replace(",", ".")))), "offer_title:cm"
    inches, source = _tv_inches_int(context)
    if inches is None:
        return "", "unresolved"
    if inches in TV_INCH_TO_CM:
        return str(TV_INCH_TO_CM[inches]), f"{source}:mapped_cm"
    return str(int(inches * 2.54)), f"{source}:derived_cm"


def _resolve_tv_resolution(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    if value:
        return _map_resolution(value), source
    if _contains_any(context.combined_text, "4k", "ultra hd"):
        return "ULTRA HD ( 4K )", "title_resolution"
    return "", "unresolved"


def _resolve_tv_pixels(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    for candidate in [context.combined_text, *context.offer_titles]:
        pixels = _format_pixels(candidate)
        if pixels:
            return pixels, "text_pixels"
    resolution, source = _resolve_tv_resolution(context, {})
    if resolution:
        return RESOLUTION_TO_PIXELS.get(normalize_for_match(resolution), ""), f"{source}:mapped_pixels"
    return "", "unresolved"


def _resolve_tv_image_features(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    features = _ordered_features(
        context,
        [
            ("FILMMAKER MODE", ("filmmaker",)),
            ("Direct Full Array", ("direct full array", "dfa")),
            ("4K AI Upscaling", ("ai 4k upscaler", "4k upscaler", "4k ai upscaling")),
            ("Dolby Vision", ("dolby vision",)),
        ],
    )
    return (",".join(features), "combined_text:features") if features else ("", "unresolved")


def _resolve_tv_refresh_rate(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    if not value:
        return "", "unresolved"
    values = [int(part) for part in re.findall(r"\d+", value)]
    if not values:
        return "", "unresolved"
    return str(max(values)), source


def _resolve_tv_hdr(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    haystack = normalize_whitespace(" ".join(part for part in [value, context.combined_text] if part))
    tokens = _ordered_features(
        _ResolutionContext(
            source=context.source,
            taxonomy=context.taxonomy,
            spec_lookup=context.spec_lookup,
            raw_lookup=context.raw_lookup,
            section_lookup=context.section_lookup,
            raw_html=context.raw_html,
            raw_text=context.raw_text,
            offer_titles=context.offer_titles,
            combined_text=haystack,
        ),
        [
            ("HDR10", ("hdr10",)),
            ("HDR10+", ("hdr10+",)),
            ("Dolby Vision ™HDR", ("dolby vision",)),
            ("HLG", ("hlg",)),
        ],
    )
    return (",".join(tokens), source or "combined_text:hdr") if tokens else ("", "unresolved")


def _resolve_tv_energy_class(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    return _value_or_unresolved(value, source)


def _resolve_tv_energy_class_hdr(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Ενεργειακή Κλάση HDR"])
    return _value_or_unresolved(value, source)


def _resolve_tv_energy_sdr(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Κατανάλωση Ενέργειας σε Λειτουργία SDR (kWh/1000h)"])
    return _value_or_unresolved(value, source)


def _resolve_tv_energy_hdr(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Κατανάλωση Ενέργειας σε Λειτουργία HDR (kWh/1000h)"])
    return _value_or_unresolved(value, source)


def _resolve_tv_tuner(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    if not value:
        return "", "unresolved"
    key = re.sub(r"[\s,/-]+", "", normalize_for_match(value))
    parts: list[str] = []
    if "dvbt2" in key:
        parts.append("DVB-T2")
    if "dvbc" in key:
        parts.append("C")
    if "dvbs2" in key:
        parts.append("S2")
    return ("/".join(parts), source) if parts else (normalize_whitespace(value), source)


def _resolve_tv_sound_system(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    parts: list[str] = []
    channels_value, channels_source = _first_value_from_aliases(context, ["Κανάλια"])
    if channels_value:
        channels = normalize_whitespace(channels_value).replace(" ", "")
        if re.fullmatch(r"\d+(?:\.\d+)?", channels):
            parts.append(f"{channels}ch")
        else:
            parts.append(channels)
    tokens = _ordered_features(
        context,
        [
            ("Dolby Atmos", ("dolby atmos",)),
            ("Dolby Audio", ("dolby audio",)),
            ("DTS:X", ("dts:x",)),
            ("DTS Virtual:X", ("dts virtual:x", "dts virtual x")),
        ],
    )
    parts.extend(token for token in tokens if token not in parts)
    return (",".join(parts), channels_source or "combined_text:sound") if parts else ("", "unresolved")


def _resolve_tv_processor(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    match = re.search(r"hi[\s-]?view ai engine", context.combined_text, flags=re.IGNORECASE)
    return ("Hi-View AI Engine", "combined_text:processor") if match else ("", "unresolved")


def _resolve_tv_smart_tv(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    if _contains_any(context.combined_text, "smart tv", "vidaa", "netflix", "youtube"):
        return "Υποστηρίζεται", "combined_text:smart_tv"
    return "", "unresolved"


def _resolve_tv_os(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    match = re.search(r"vidaa\s*u?\s*(\d+(?:\.\d+)?)", context.combined_text, flags=re.IGNORECASE)
    if match:
        return f"VIDAA U{match.group(1)}", "combined_text:os_version"
    if _contains_any(context.combined_text, "vidaa smart os", "vidaa"):
        return "VIDAA", "combined_text:os"
    return "", "unresolved"


def _resolve_tv_smart_functions(_context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    return "", "unresolved"


def _resolve_tv_extra_functions(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    values = _ordered_features(
        context,
        [
            ("AI Energy Mode", ("ai energy mode",)),
            ("AI Sports Mode", ("ai sports mode",)),
            ("AnyView Cast", ("anyview cast",)),
            ("Voice Remote", ("voice remote",)),
            ("Gaming Mode", ("gaming mode", "game mode plus")),
            ("Game Bar", ("game bar",)),
        ],
    )
    return (",".join(values), "combined_text:extra_functions") if values else ("", "unresolved")


def _resolve_tv_hdmi(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Σύνολο Θυρών HDMI"])
    count = _extract_int_from_text(value)
    if count is None:
        for title in context.offer_titles:
            match = re.search(r"(\d+)\s*x\s*hdmi", title, flags=re.IGNORECASE)
            if match:
                count = int(match.group(1))
                source = "offer_title:hdmi_count"
                break
    if count is None:
        return "", "unresolved"
    parts = [f"Ναι,{count}"]
    if _contains_any(context.combined_text, "earc", "e arc"):
        parts.append("eARC")
    return ",".join(parts), source or "combined_text:hdmi"


def _resolve_tv_bluetooth(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Bluetooth"])
    if _contains_any(value, "ναι", "yes", "bluetooth") or _contains_any(context.combined_text, "bluetooth", " bt "):
        return "Bluetooth", source or "combined_text:bluetooth"
    return "", "unresolved"


def _resolve_tv_usb(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Πλήθος USB", "USB"])
    count = _extract_int_from_text(value)
    if count is None:
        for title in context.offer_titles:
            match = re.search(r"(\d+)\s*x\s*usb", title, flags=re.IGNORECASE)
            if match:
                count = int(match.group(1))
                source = "offer_title:usb_count"
                break
    return (f"Ναι,{count}", source or "combined_text:usb") if count is not None else ("", "unresolved")


def _resolve_tv_io(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    values = _ordered_features(
        context,
        [
            ("ALLM", ("allm",)),
            ("VRR", ("vrr",)),
            ("CI+", ("ci+",)),
        ],
    )
    return (",".join(values), "combined_text:io") if values else ("", "unresolved")


def _resolve_tv_equipment(_context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    return "", "unresolved"


def _resolve_tv_appearance(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    values = _ordered_features(
        context,
        [
            ("Bezel-less", ("bezel-less", "bezel less")),
        ],
    )
    return (",".join(values), "combined_text:appearance") if values else ("", "unresolved")


def _resolve_tv_vesa(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    match = re.search(r"(\d+)\s*[x×]\s*(\d+)", value or "", flags=re.IGNORECASE)
    if not match:
        return "", "unresolved"
    dims = sorted([int(match.group(1)), int(match.group(2))])
    return f"{dims[0]} × {dims[1]}", source


def _resolve_tv_color(_context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    return "", "unresolved"


def _resolve_tv_weight_with_stand(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    number = _extract_first_number(value)
    if number is None:
        return "", "unresolved"
    rounded = int(round(number))
    return str(rounded), source


def _resolve_tv_country(_context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    return "", "unresolved"


def _resolve_tv_warranty(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    match = re.search(r"(\d+)\s+χρόνια\s+εγγύηση", context.raw_html, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"εγγύηση[^0-9]{0,25}(\d+)\s+χρόν", context.raw_html, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)} έτη", "raw_html:warranty"
    return "", "unresolved"


def _resolve_tv_dimensions_with_stand(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    width, width_source = _section_value(context, "Διαστάσεις (με Βάση)", "Πλάτος")
    height, height_source = _section_value(context, "Διαστάσεις (με Βάση)", "Ύψος")
    depth, depth_source = _section_value(context, "Διαστάσεις (με Βάση)", "Πάχος")
    if not width or not height or not depth:
        return "", "unresolved"

    def to_cm(value: str) -> str:
        number = _extract_first_number(value)
        if number is None:
            return ""
        if "mm" in normalize_for_match(value):
            number = number / 10
        return f"{number:.2f}"

    values = [to_cm(height), to_cm(width), to_cm(depth)]
    if any(not item for item in values):
        return "", "unresolved"
    source = ",".join(item for item in [height_source, width_source, depth_source] if item)
    return " × ".join(values), source


def _normalize_yes_no(value: str) -> str:
    normalized = normalize_for_match(value)
    if not normalized:
        return ""
    if any(token in normalized for token in ["ναι", "yes", "supported", "ξεχωριστ", "υποστηριζ"]):
        return "Ναι"
    if any(token in normalized for token in ["οχι", "no", "not supported"]):
        return "Όχι"
    return ""


def _format_decimal(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _format_power_watts(value: str) -> str:
    number = _extract_first_number(value)
    if number is None:
        return ""
    unit_text = (value or "").casefold()
    if re.search(r"(?:[kκ]\s*[wω]|κιλοβατ)", unit_text):
        number *= 1000
    return f"{int(round(number))} W"


def _format_dimension_token(token: str, assume_millimeters: bool = False) -> str:
    values: list[str] = []
    for part in [segment.strip() for segment in re.split(r"\s*-\s*", token) if segment.strip()]:
        number = _extract_first_number(part)
        if number is None:
            continue
        if assume_millimeters:
            number /= 10
        values.append(_format_decimal(number))
    if not values:
        return ""
    return f"{' - '.join(values)} cm"


def _extract_dimension_tokens(value: str) -> list[str]:
    cleaned = normalize_whitespace(value).replace("(", "").replace(")", "")
    return re.findall(r"\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?", cleaned)


def _dimension_from_triplet(value: str, position: int) -> str:
    tokens = _extract_dimension_tokens(value)
    if len(tokens) <= position:
        return ""
    return _format_dimension_token(tokens[position], assume_millimeters=True)


def _resolve_hob_yes_no(context: _ResolutionContext, aliases: list[str], *tokens: str) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, aliases)
    normalized = _normalize_yes_no(value)
    if normalized:
        return normalized, source
    if tokens and any(_contains_any(context.combined_text, token) for token in tokens):
        return "Ναι", "combined_text:token_match"
    return "", "unresolved"


def _extract_hob_zone_powers(text: str) -> dict[str, str]:
    powers: dict[str, str] = {}
    pattern = re.compile(
        r"(Μπροστά|Πίσω)\s+(αριστερά|δεξιά)\s*:\s*.*?(\d+(?:[.,]\d+)?)\s*[kκΚ]\s*[wωW]",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text or ""):
        key = f"{normalize_for_match(match.group(1))}_{normalize_for_match(match.group(2))}"
        powers.setdefault(key, f"{_format_decimal(float(match.group(3).replace(',', '.')))} kW")
    return powers


def _resolve_hob_installation_type(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Τύπος εγκατάστασης", "Τρόπος Τοποθέτησης"])
    if value:
        return value, source
    if normalize_for_match(context.taxonomy.leaf_category) == normalize_for_match("Εντοιχιζόμενες Συσκευές"):
        return "Εντοιχιζόμενη συσκευή", "taxonomy:leaf_category"
    return "", "unresolved"


def _resolve_hob_surface_technology(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(
        context,
        ["Βασικό υλικό επιφανειών", "Τεχνολογία Πλατώ Εστιών", "Τύπος Εστίας", "Τύπος"],
    )
    normalized = normalize_for_match(value)
    if "υαλοκεραμ" in normalized or "κεραμ" in normalized:
        return "Υαλοκεραμική", source
    if "επαγωγ" in normalized:
        return "Επαγωγική", source
    if "αερι" in normalized or "gas" in normalized:
        return "Αερίου", source
    return _value_or_unresolved(value, source)


def _resolve_hob_zone_count(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(
        context,
        [
            "Συνολικός αριθμός ζωνών που μπορούν να χρησιμοποιηθούν ταυτόχρονα",
            "Πλήθος ζωνών και/ή περιοχών μαγειρέματος",
            "Αριθμός Ζωνών",
            "Αριθμός Εστιών",
            "Εστίες",
        ],
    )
    count = _extract_int_from_text(value)
    return (str(count), source) if count is not None else ("", "unresolved")


def _resolve_hob_control_type(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Είδος ηλεκτρονικού ελέγχου", "Τύπος Χειριστηρίου", "Διακόπτες", "Neff"])
    haystack = normalize_whitespace(" ".join(part for part in [value, context.combined_text] if part))
    if _contains_any(haystack, "twistpad", "twist pad"):
        return "TwistPad®", source or "combined_text:twistpad"
    if _contains_any(haystack, "αφης", "touch"):
        return "Αφής", source or "combined_text:touch"
    return _value_or_unresolved(value, source)


def _resolve_hob_digital_indicators(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Ψηφιακές Ενδείξεις", "Ψηφιακό χρονόμετρο"])
    normalized = _normalize_yes_no(value)
    if normalized:
        return normalized, source
    if value:
        return "Ναι", source
    if _contains_any(context.combined_text, "ψηφιακ", "twistpad", "πλήκτρα αφής"):
        return "Ναι", "combined_text:digital"
    return "", "unresolved"


def _resolve_hob_residual_heat(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    return _resolve_hob_yes_no(
        context,
        ["Ένδειξη Υπολοίπου Θερμότητας", "Ενδεικτική λυχνία εναπομένουσας θερμότητας", "Διπλή ένδειξη (H/h) υπολοίπου θερμότητας για κάθε ζώνη"],
        "υπολοιπου θερμοτητας",
    )


def _resolve_hob_timer(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    return _resolve_hob_yes_no(
        context,
        ["Χρονοδιακόπτης", "Χρονοδιακόπτης απενεργοποίησης", "Λειτουργία Alarm με ηχητική ειδοποίηση", "Ψηφιακό χρονόμετρο"],
        "χρονοδιακοπτη",
        "alarm",
        "χρονόμετρο",
    )


def _resolve_hob_pan_recognition(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Αυτόματη Αναγνώρηση Σκευών"])
    normalized = _normalize_yes_no(value)
    if normalized:
        return normalized, source
    if _contains_any(context.combined_text, "αναγνωριση σκευων", "ανιχνευση σκευους"):
        return "Ναι", "combined_text:pan_recognition"
    return "", "unresolved"


def _resolve_hob_coffee_zone(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Ζώνη Καφέ"])
    normalized = _normalize_yes_no(value)
    if normalized:
        return normalized, source
    if _contains_any(context.combined_text, "ζωνη καφε", "coffee zone"):
        return "Ναι", "combined_text:coffee_zone"
    return "", "unresolved"


def _resolve_hob_natural_gas(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Σύνδεση με Φυσικό Αέριο", "Τύπος λειτουργίας", "Τύπος εστίας", "Τύπος"])
    normalized = _normalize_yes_no(value)
    if normalized:
        return normalized, source
    if _contains_any(value or context.combined_text, "φυσικο αεριο", "αεριου", "gas"):
        return "Ναι", source or "combined_text:gas"
    if _contains_any(value or context.combined_text, "ηλεκτρ", "κεραμ", "υαλοκεραμ", "επαγωγ"):
        return "Όχι", source or "combined_text:electric"
    return "", "unresolved"


def _resolve_hob_connectivity(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Συνδεσιμότητα", "Smart"])
    normalized = _normalize_yes_no(value)
    if normalized:
        return normalized, source
    if _contains_any(context.combined_text, "home connect", "wifi", "wi-fi", "bluetooth"):
        return "Ναι", "combined_text:connectivity"
    if _contains_any(value, "smart") and _contains_any(value, "οχι", "no"):
        return "Όχι", source
    return "", "unresolved"


def _resolve_hob_other_features(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    features: list[str] = []
    if re.search(r"17\s+βαθμ", context.combined_text, flags=re.IGNORECASE):
        features.append("17 βαθμίδες ισχύος")
    if _contains_any(context.combined_text, "restart"):
        features.append("λειτουργία Restart")
    if _contains_any(context.combined_text, "alarm"):
        features.append("λειτουργία Alarm")
    if _contains_any(context.combined_text, "διατηρησης θερμοτητας", "διατήρησης θερμότητας"):
        features.append("διατήρηση θερμότητας")
    return (", ".join(features), "combined_text:other_features") if features else ("", "unresolved")


def _resolve_hob_zone_power(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    position = str(field.get("zone_position", "")).strip()
    powers = _extract_hob_zone_powers(context.combined_text)
    if position and position in powers:
        return powers[position], f"combined_text:zone_power:{position}"
    return "", "unresolved"


def _resolve_hob_total_power(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Συνολική ισχύς", "Μέγιστη Ονομαστική Ισχύς"])
    formatted = _format_power_watts(value)
    return (formatted, source) if formatted else ("", "unresolved")


def _resolve_hob_child_lock(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    return _resolve_hob_yes_no(
        context,
        ["Κλείδωμα ασφαλείας για τα παιδιά", "Λειτουργία Κλειδώματος"],
        "κλειδωμα ασφαλειας",
    )


def _resolve_hob_auto_safety_off(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    return _resolve_hob_yes_no(
        context,
        ["Αυτόματη απενεργοποίηση ασφαλείας"],
        "αυτοματη απενεργοποιηση ασφαλειας",
    )


def _resolve_hob_color(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Χρώμα", "Χρώμα επιφανειών"])
    return _value_or_unresolved(value, source)


def _resolve_hob_frame_color(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Χρώμα Πλαισίου"])
    if value:
        if "ανοξειδ" in normalize_for_match(value):
            return "Ανοξείδωτο", source
        return value, source
    if _contains_any(context.combined_text, "ανοξειδωτο πλαισιο", "περιμετρικο πλαισιο"):
        return "Ανοξείδωτο", "combined_text:frame_color"
    return "", "unresolved"


def _resolve_hob_weight(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Καθαρό βάρος", "Βάρος Συσκευής σε Κιλά"])
    number = _extract_first_number(value)
    if number is None:
        return "", "unresolved"
    if re.search(r"[.,]\d", value):
        return f"{number:.1f}", source
    return _format_decimal(number), source


def _resolve_hob_cutout_height(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Διαστάσεις εντοιχισμού (υ x π x β)", "Διαστάσεις Εντοιχισμού (ΥxΠxΒ mm)"])
    formatted = _dimension_from_triplet(value, 0)
    return (formatted, source) if formatted else ("", "unresolved")


def _resolve_hob_cutout_width(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Πλάτος Εντοιχισμού"])
    if value:
        return _value_or_unresolved(value, source)
    triple_value, triple_source = _first_value_from_aliases(context, ["Διαστάσεις εντοιχισμού (υ x π x β)", "Διαστάσεις Εντοιχισμού (ΥxΠxΒ mm)"])
    formatted = _dimension_from_triplet(triple_value, 1)
    return (formatted, triple_source) if formatted else ("", "unresolved")


def _resolve_hob_cutout_depth(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    triple_value, triple_source = _first_value_from_aliases(context, ["Διαστάσεις εντοιχισμού (υ x π x β)", "Διαστάσεις Εντοιχισμού (ΥxΠxΒ mm)"])
    formatted = _dimension_from_triplet(triple_value, 2)
    if formatted:
        return formatted, triple_source
    value, source = _first_value_from_aliases(context, ["Βάθος Εντοιχισμού"])
    return _value_or_unresolved(value, source)


def _resolve_hob_device_width(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _section_value(context, "Διαστάσεις Συσκευής", "Πλάτος")
    if value:
        return value, source
    triple_value, triple_source = _first_value_from_aliases(context, ["Διαστάσεις συσκευής (ΥxΠxΒ mm)", "Διαστάσεις Εσωτερικής μονάδας: (ΥxΠxΒ)"])
    formatted = _dimension_from_triplet(triple_value, 1)
    return (formatted, triple_source) if formatted else ("", "unresolved")


def _resolve_hob_device_depth(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _section_value(context, "Διαστάσεις Συσκευής", "Βάθος")
    if value:
        return value, source
    triple_value, triple_source = _first_value_from_aliases(context, ["Διαστάσεις συσκευής (ΥxΠxΒ mm)", "Διαστάσεις Εσωτερικής μονάδας: (ΥxΠxΒ)"])
    formatted = _dimension_from_triplet(triple_value, 2)
    return (formatted, triple_source) if formatted else ("", "unresolved")


def _resolve_hob_warranty(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Εγγύηση Κατασκευαστή"])
    if value:
        return value, source
    match = re.search(r"(\d+)\s+έτ", context.raw_html, flags=re.IGNORECASE)
    if match and _contains_any(context.raw_html, "εγγυ"):
        return f"{match.group(1)} έτη", "raw_html:warranty"
    return "", "unresolved"


def _extract_count_from_text(text: str, pattern: str) -> str:
    match = re.search(pattern, text or "", flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1)


def _resolve_fridge_temperature_control(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    if _contains_any(context.combined_text, "panel ελέγχου", "panel ελεγχου", "οθόνη ενδείξεων", "οθονη ενδειξεων"):
        return "Ηλεκτρονικό panel ελέγχου (LED)", "combined_text:temperature_control"
    return "", "unresolved"


def _resolve_fridge_installation_type(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Τύπος εγκατάστασης", "Εντοιχιζόμενη / Ελεύθερη", "Εντοιχιζόμενο"])
    normalized = normalize_for_match(value)
    if "ελευθερ" in normalized:
        return "Ελεύθερη συσκευή", source
    if "εντοιχιζ" in normalized and "οχι" not in normalized and "όχι" not in (value or "").lower():
        return "Εντοιχιζόμενη συσκευή", source
    if _contains_any(context.combined_text, "perfect fit", "δίπλα σε τοίχους", "διπλα σε τοιχους"):
        return "Ελεύθερη συσκευή", "combined_text:perfect_fit"
    if normalized in {"οχι", "oxi", "no", "false"}:
        return "Ελεύθερη συσκευή", source
    return "", "unresolved"


def _resolve_fridge_dual_cooling_circuits(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Αριθμός ανεξάρτητων συστημάτων ψύξης"])
    count = _extract_int_from_text(value)
    if count is None:
        return "", "unresolved"
    return ("Ναι" if count >= 2 else "Όχι"), source


def _resolve_fridge_multi_airflow(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    if _contains_any(context.combined_text, "multiairflow", "multi airflow", "dynamic multiairflow"):
        return "Ναι", "combined_text:multi_airflow"
    return "", "unresolved"


def _resolve_fridge_connectivity(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Wi-Fi", "Bluetooth", "Συνδεσιμότητα"])
    normalized = _normalize_yes_no(value)
    if normalized:
        return normalized, source
    if _contains_any(context.combined_text, "wifi", "wi-fi", "home connect", "bluetooth"):
        return "Ναι", "combined_text:connectivity"
    return "Όχι", source or "combined_text:no_connectivity"


def _resolve_fridge_open_door_alert(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Extra Δυνατότητες"])
    if _contains_any(" ".join([value, context.combined_text]), "ειδοποίηση πόρτας", "ειδοποιηση πορτας", "ανοικτής πόρτας", "ανοιχτής πόρτας"):
        return "Ναι", source or "combined_text:door_alert"
    return "", "unresolved"


def _resolve_fridge_overview_features(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    features = _ordered_features(
        context,
        [
            ("Perfect Fit", ("perfect fit",)),
            ("Ενσωματωμένη οριζόντια χειρολαβή", ("ενσωματωμένη οριζόντια χειρολαβή", "ενσωματωμενη οριζοντια χειρολαβη")),
        ],
    )
    return (", ".join(features), "combined_text:fridge_features") if features else ("", "unresolved")


def _resolve_fridge_fridge_shelf_count(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Στην Συντήρηση"])
    count = _extract_count_from_text(value, r"(\d+)\s+ράφια")
    if count:
        return count, source
    count = _extract_count_from_text(context.combined_text, r"(\d+)\s+ράφια")
    return (count, "combined_text:fridge_shelves") if count else ("", "unresolved")


def _resolve_fridge_adjustable_shelves(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Αριθμός ρυθμιζόμενων ραφιών στη συντήρηση"])
    count = _extract_int_from_text(value)
    if count is not None:
        return str(count), source
    count_text = _extract_count_from_text(context.combined_text, r"αριθμός ρυθμιζόμενων ραφιών στη συντήρηση[: ]+(\d+)")
    if count_text:
        return count_text, "combined_text:adjustable_shelves"
    count_text = _extract_count_from_text(context.combined_text, r"ρυθμιζόμενα σε ύψος[: ]+(\d+)")
    if count_text:
        return count_text, "combined_text:adjustable_shelves"
    count_text = _extract_count_from_text(context.combined_text, r"ρυθμιζονται σε ύψος[: ]+(\d+)")
    return (count_text, "combined_text:adjustable_shelves") if count_text else ("", "unresolved")


def _resolve_fridge_shelf_material(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    if _contains_any(context.combined_text, "γυαλί ασφαλείας", "γυάλινα ράφια", "γυαλινα ραφια"):
        return "Γυαλί Ασφαλείας", "combined_text:shelf_material"
    return "", "unresolved"


def _resolve_fridge_fridge_drawer_count(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Στην Συντήρηση"])
    count = _extract_count_from_text(value, r"(\d+)\s+συρτάρι")
    if count:
        return count, source
    count = _extract_count_from_text(context.combined_text, r"(\d+)\s+συρτάρι")
    return (count, "combined_text:fridge_drawers") if count else ("", "unresolved")


def _resolve_fridge_humidity_drawer(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    if _contains_any(context.combined_text, "ρύθμιση υγρασίας", "ρυθμιση υγρασιας"):
        return "Ναι", "combined_text:humidity_drawer"
    return "", "unresolved"


def _resolve_fridge_door_shelves(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Στην Συντήρηση"])
    count = _extract_count_from_text(value, r"(\d+)\s+ράφια\s+στην\s+πόρτα")
    if count:
        return count, source
    count = _extract_count_from_text(context.combined_text, r"(\d+)\s+ράφια\s+θύρας")
    if count:
        return count, "combined_text:door_shelves"
    count = _extract_count_from_text(context.combined_text, r"(\d+)\s+ράφια\s+στην\s+πόρτα")
    return (count, "combined_text:door_shelves") if count else ("", "unresolved")


def _resolve_fridge_internal_light(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    if _contains_any(context.combined_text, "φωτισμός led", "φωτισμος led"):
        return "LED", "combined_text:internal_light"
    return "", "unresolved"


def _resolve_fridge_fast_cool(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Extra Δυνατότητες"])
    if _contains_any(" ".join([value, context.combined_text]), "γρήγορη ψύξη", "γρηγορη ψυξη"):
        return "Ναι", source or "combined_text:fast_cool"
    return "", "unresolved"


def _resolve_fridge_storage_features(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    features = _ordered_features(context, [("MultiBox", ("multibox",))])
    return (", ".join(features), "combined_text:storage_features") if features else ("", "unresolved")


def _resolve_fridge_freezer_drawer_count(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Στην Κατάψυξη"])
    count = _extract_count_from_text(value, r"(\d+)\s+συρτάρια")
    if count:
        return count, source
    count = _extract_count_from_text(context.combined_text, r"(\d+)\s+συρτάρια")
    return (count, "combined_text:freezer_drawers") if count else ("", "unresolved")


def _resolve_fridge_freezer_shelf_count(_context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    return "", "unresolved"


def _resolve_fridge_fast_freeze(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    if _contains_any(context.combined_text, "superfreezing", "γρήγορη κατάψυξη", "γρηγορη καταψυξη"):
        return "Ναι", "combined_text:fast_freeze"
    return "", "unresolved"


def _resolve_fridge_freezer_features(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    features = _ordered_features(context, [("SuperFreezing", ("superfreezing",))])
    return (", ".join(features), "combined_text:freezer_features") if features else ("", "unresolved")


def _resolve_fridge_climate_class(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Κλιματική Κλάση"])
    if value:
        return value, source
    match = re.search(r"Κλιματική\s+Κλάση[: ]+([A-Z]{1,3}(?:-[A-Z]{1,3})?)", context.combined_text, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper(), "combined_text:climate_class"
    return "", "unresolved"


def _resolve_fridge_dimensions_triplet(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Διαστάσεις συσκευής ΥxΠxΒ", "Διαστάσεις συσκευής Υ x Π x Β"])
    if value:
        tokens = re.findall(r"\d+(?:[.,]\d+)?", value)
        if len(tokens) >= 3:
            return f"{tokens[0]} x {tokens[1]} x {tokens[2]} cm", source
    height, height_source = _first_value_from_aliases(context, ["Ύψος"])
    width, width_source = _first_value_from_aliases(context, ["Πλάτος"])
    depth, depth_source = _first_value_from_aliases(context, ["Βάθος"])
    if height and width and depth:
        compact = [re.sub(r"\s*cm\b", "", part, flags=re.IGNORECASE) for part in [height, width, depth]]
        return f"{compact[0]} x {compact[1]} x {compact[2]} cm", ",".join([height_source, width_source, depth_source])
    return "", "unresolved"


def _resolve_fridge_warranty(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, ["Επιμέρους Εγγύηση Κατασκευαστή", "Εγγύηση Κατασκευαστή"])
    if value:
        return value, source
    return "", "unresolved"


def _resolve_air_conditioner_technology(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    if value:
        return value, source
    if _contains_any(" ".join([context.source.name, context.combined_text]), "inverter"):
        return "Inverter", "combined_text:technology"
    return "", "unresolved"


def _resolve_air_conditioner_refrigerant(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    aliases = list(field.get("aliases", []))
    refrigerant_code = normalize_whitespace(str(field.get("refrigerant_code", ""))).upper()
    for alias in aliases:
        value, source = _first_value_from_aliases(context, [alias])
        if not value:
            continue
        direct_match = re.search(r"\b(R[0-9A-Z]+)\b", value, flags=re.IGNORECASE)
        if direct_match:
            return direct_match.group(1).upper(), source
        alias_match = re.search(r"\((R[0-9A-Z]+)\)", alias, flags=re.IGNORECASE)
        if alias_match and _normalize_yes_no(value) == "Ναι":
            return alias_match.group(1).upper(), source
        if refrigerant_code and _normalize_yes_no(value) == "Ναι":
            return refrigerant_code, source
    if refrigerant_code and _contains_any(context.combined_text, refrigerant_code):
        return refrigerant_code, "combined_text:refrigerant"
    return "", "unresolved"


def _resolve_air_conditioner_dehumidification(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    normalized = _normalize_yes_no(value)
    if normalized:
        return normalized, source
    if _contains_any(context.combined_text, "αφύγρανση", "αφυγρανση"):
        return "Ναι", "combined_text:dehumidification"
    return "", "unresolved"


def _resolve_air_conditioner_extra_features(context: _ResolutionContext, _field: dict[str, Any]) -> tuple[str, str]:
    features: list[str] = []
    sources: list[str] = []

    def add_feature(display: str, source: str) -> None:
        if display not in features:
            features.append(display)
        if source and source not in sources:
            sources.append(source)

    wifi_value, wifi_source = _first_value_from_aliases(context, ["WiFi"])
    if _normalize_yes_no(wifi_value) == "Ναι":
        add_feature("WiFi", wifi_source or "spec_alias:WiFi")

    follow_me_value, follow_me_source = _first_value_from_aliases(context, ["Λειτουργία Follow Me"])
    if _normalize_yes_no(follow_me_value) == "Ναι":
        add_feature("Follow Me", follow_me_source or "spec_alias:Λειτουργία Follow Me")

    combined_candidates = [
        ("Voice Control", ("voice control",)),
        ("Timer", ("timer",)),
        ("Turbo Mode", ("turbo mode",)),
        ("Sleep Mode", ("sleep mode",)),
        ("Silence Mode", ("silence mode",)),
        ("Smart Defrost", ("smart defrost",)),
        ("Auto Restart", ("autorestart", "auto restart")),
        ("Smooth Start", ("smooth start",)),
        ("Self Clean 56°C", ("i-clean", "self clean", "56°c", "56 c")),
        ("Hotel Menu", ("hotel menu",)),
        ("8°C Heating", ("8°c heating", "8 c heating")),
        ("I-Feel", ("i-feel", "i sense", "i-sense")),
    ]
    for display, tokens in combined_candidates:
        if any(_contains_any(context.combined_text, token) for token in tokens):
            add_feature(display, "combined_text:ac_features")

    return (", ".join(features), ",".join(sources)) if features else ("", "unresolved")


def _format_air_conditioner_dimension_mm(value: str) -> str:
    number = _extract_first_number(value)
    if number is None:
        return ""
    normalized = normalize_for_match(value)
    if "cm" in normalized or "εκατοστ" in normalized:
        number *= 10
    elif "mm" in normalized or "χιλιοστ" in normalized:
        pass
    elif number < 100:
        number *= 10
    return _format_decimal(number)


def _resolve_air_conditioner_dimension_mm(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    value, source = _first_value_from_aliases(context, field.get("aliases", []))
    formatted = _format_air_conditioner_dimension_mm(value)
    return (formatted, source) if formatted else ("", "unresolved")


def _extract_air_conditioner_warranty_years(text: str, target: str) -> str:
    normalized = normalize_whitespace(text)
    if not normalized:
        return ""

    if target == "compressor":
        match = re.search(r"(\d+)\s*χρ(?:ο|ό)ν(?:ια|ος)?[^,.;]*συμπιεστ", normalized, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        if "συμπιεστ" in normalize_for_match(normalized):
            fallback = re.search(r"(\d+)\s*χρ(?:ο|ό)ν(?:ια|ος)?", normalized, flags=re.IGNORECASE)
            if fallback:
                return fallback.group(1)
        return ""

    unit_patterns = [
        r"(\d+)\s*χρ(?:ο|ό)ν(?:ια|ος)?[^,.;]*(?:ηλεκτρικ|μηχανικ|μέρ|μερη)",
        r"(\d+)\s*χρ(?:ο|ό)ν(?:ια|ος)?\s+σε\s+όλα",
    ]
    for pattern in unit_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    if "συμπιεστ" not in normalize_for_match(normalized):
        fallback = re.search(r"(\d+)\s*χρ(?:ο|ό)ν(?:ια|ος)?", normalized, flags=re.IGNORECASE)
        if fallback:
            return fallback.group(1)
    return ""


def _resolve_air_conditioner_warranty_years(context: _ResolutionContext, field: dict[str, Any]) -> tuple[str, str]:
    aliases = list(field.get("aliases", [])) or ["Επιμέρους Εγγύηση Κατασκευαστή", "Εγγύηση Κατασκευαστή"]
    target = normalize_for_match(str(field.get("warranty_target", ""))) or "unit"
    value, source = _first_value_from_aliases(context, aliases)
    for candidate_text, candidate_source in [(value, source), (context.combined_text, "combined_text:warranty")]:
        years = _extract_air_conditioner_warranty_years(candidate_text, target)
        if years:
            return years, candidate_source
    return "", "unresolved"


_RESOLVERS: dict[str, Callable[[_ResolutionContext, dict[str, Any]], tuple[str, str]]] = {
    "air_conditioner_technology": _resolve_air_conditioner_technology,
    "air_conditioner_refrigerant": _resolve_air_conditioner_refrigerant,
    "air_conditioner_dehumidification": _resolve_air_conditioner_dehumidification,
    "air_conditioner_extra_features": _resolve_air_conditioner_extra_features,
    "air_conditioner_dimension_mm": _resolve_air_conditioner_dimension_mm,
    "air_conditioner_warranty_years": _resolve_air_conditioner_warranty_years,
    "fridge_temperature_control": _resolve_fridge_temperature_control,
    "fridge_installation_type": _resolve_fridge_installation_type,
    "fridge_dual_cooling_circuits": _resolve_fridge_dual_cooling_circuits,
    "fridge_multi_airflow": _resolve_fridge_multi_airflow,
    "fridge_connectivity": _resolve_fridge_connectivity,
    "fridge_open_door_alert": _resolve_fridge_open_door_alert,
    "fridge_overview_features": _resolve_fridge_overview_features,
    "fridge_fridge_shelf_count": _resolve_fridge_fridge_shelf_count,
    "fridge_adjustable_shelves": _resolve_fridge_adjustable_shelves,
    "fridge_shelf_material": _resolve_fridge_shelf_material,
    "fridge_fridge_drawer_count": _resolve_fridge_fridge_drawer_count,
    "fridge_humidity_drawer": _resolve_fridge_humidity_drawer,
    "fridge_door_shelves": _resolve_fridge_door_shelves,
    "fridge_internal_light": _resolve_fridge_internal_light,
    "fridge_fast_cool": _resolve_fridge_fast_cool,
    "fridge_storage_features": _resolve_fridge_storage_features,
    "fridge_freezer_drawer_count": _resolve_fridge_freezer_drawer_count,
    "fridge_freezer_shelf_count": _resolve_fridge_freezer_shelf_count,
    "fridge_fast_freeze": _resolve_fridge_fast_freeze,
    "fridge_freezer_features": _resolve_fridge_freezer_features,
    "fridge_climate_class": _resolve_fridge_climate_class,
    "fridge_dimensions_triplet": _resolve_fridge_dimensions_triplet,
    "fridge_warranty": _resolve_fridge_warranty,
    "tv_screen_technology": _resolve_tv_screen_technology,
    "tv_screen_size_inches": _resolve_tv_screen_size_inches,
    "tv_screen_size_cm": _resolve_tv_screen_size_cm,
    "tv_resolution": _resolve_tv_resolution,
    "tv_pixels": _resolve_tv_pixels,
    "tv_image_features": _resolve_tv_image_features,
    "tv_refresh_rate": _resolve_tv_refresh_rate,
    "tv_hdr": _resolve_tv_hdr,
    "tv_energy_class": _resolve_tv_energy_class,
    "tv_energy_class_hdr": _resolve_tv_energy_class_hdr,
    "tv_energy_sdr": _resolve_tv_energy_sdr,
    "tv_energy_hdr": _resolve_tv_energy_hdr,
    "tv_tuner": _resolve_tv_tuner,
    "tv_sound_system": _resolve_tv_sound_system,
    "tv_processor": _resolve_tv_processor,
    "tv_smart_tv": _resolve_tv_smart_tv,
    "tv_os": _resolve_tv_os,
    "tv_smart_functions": _resolve_tv_smart_functions,
    "tv_extra_functions": _resolve_tv_extra_functions,
    "tv_hdmi": _resolve_tv_hdmi,
    "tv_bluetooth": _resolve_tv_bluetooth,
    "tv_usb": _resolve_tv_usb,
    "tv_io": _resolve_tv_io,
    "tv_equipment": _resolve_tv_equipment,
    "tv_appearance": _resolve_tv_appearance,
    "tv_vesa": _resolve_tv_vesa,
    "tv_color": _resolve_tv_color,
    "tv_weight_with_stand": _resolve_tv_weight_with_stand,
    "tv_country": _resolve_tv_country,
    "tv_warranty": _resolve_tv_warranty,
    "tv_dimensions_with_stand": _resolve_tv_dimensions_with_stand,
    "hob_installation_type": _resolve_hob_installation_type,
    "hob_surface_technology": _resolve_hob_surface_technology,
    "hob_zone_count": _resolve_hob_zone_count,
    "hob_control_type": _resolve_hob_control_type,
    "hob_digital_indicators": _resolve_hob_digital_indicators,
    "hob_residual_heat": _resolve_hob_residual_heat,
    "hob_timer": _resolve_hob_timer,
    "hob_pan_recognition": _resolve_hob_pan_recognition,
    "hob_coffee_zone": _resolve_hob_coffee_zone,
    "hob_natural_gas": _resolve_hob_natural_gas,
    "hob_connectivity": _resolve_hob_connectivity,
    "hob_other_features": _resolve_hob_other_features,
    "hob_zone_power": _resolve_hob_zone_power,
    "hob_total_power": _resolve_hob_total_power,
    "hob_child_lock": _resolve_hob_child_lock,
    "hob_auto_safety_off": _resolve_hob_auto_safety_off,
    "hob_color": _resolve_hob_color,
    "hob_frame_color": _resolve_hob_frame_color,
    "hob_weight": _resolve_hob_weight,
    "hob_cutout_height": _resolve_hob_cutout_height,
    "hob_cutout_width": _resolve_hob_cutout_width,
    "hob_cutout_depth": _resolve_hob_cutout_depth,
    "hob_device_width": _resolve_hob_device_width,
    "hob_device_depth": _resolve_hob_device_depth,
    "hob_warranty": _resolve_hob_warranty,
}
