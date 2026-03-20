from __future__ import annotations

import re
from typing import Any

from .deterministic_fields import build_deterministic_product_fields
from .html_builders import build_characteristics_html, build_description_html, build_description_html_from_llm
from .models import CLIInput, ParsedProduct, SchemaMatchResult, TaxonomyResolution
from .normalize import slugify_greek_for_seo
from .utils import as_decimal_string, build_additional_image_value


def derive_seo_keyword(name: str, model: str) -> str:
    if not name or not model:
        return ""
    slug = slugify_greek_for_seo(name)
    if not slug:
        return ""
    if model not in slug and not re.search(r"\d", slug):
        slug = f"{slug}-{model}"
    return slug


def serialize_meta_keywords(value: list[str] | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        keyword = str(item).strip()
        if not keyword:
            continue
        lowered = keyword.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(keyword)
    return ", ".join(out)


def build_row(
    cli: CLIInput,
    parsed: ParsedProduct,
    taxonomy: TaxonomyResolution,
    schema_match: SchemaMatchResult,
    downloaded_image_count: int | None = None,
    besco_filenames_by_section: dict[int, str] | None = None,
    llm_product: dict[str, Any] | None = None,
    llm_presentation: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    warnings: list[str] = []
    source = parsed.source
    cta_label = taxonomy.sub_category or taxonomy.leaf_category
    deterministic = build_deterministic_product_fields(
        source=source,
        taxonomy=taxonomy,
        model=cli.model,
        seo_keyword_builder=derive_seo_keyword,
    )
    canonical_name = str(deterministic["name"])
    meta_title = str(deterministic["meta_title"])
    canonical_mpn = str(deterministic["mpn"])
    manufacturer = str(deterministic["manufacturer"])
    seo_keyword = str(deterministic["seo_keyword"])

    if llm_presentation:
        description_html, desc_warnings = build_description_html_from_llm(
            product_name=canonical_name,
            model=cli.model,
            cta_url=taxonomy.cta_url,
            cta_label=cta_label,
            intro_html=str(llm_presentation.get("intro_html", "")),
            cta_text=str(llm_presentation.get("cta_text", "")),
            sections=list(llm_presentation.get("sections", [])),
            besco_filenames_by_section=besco_filenames_by_section,
        )
    else:
        description_html, desc_warnings = build_description_html(
            product_name=canonical_name,
            hero_summary=source.hero_summary,
            presentation_source_html=source.presentation_source_html,
            presentation_source_text=source.presentation_source_text,
            model=cli.model,
            sections_requested=max(int(cli.sections), 0),
            cta_url=taxonomy.cta_url,
            cta_label=cta_label,
            besco_filenames_by_section=besco_filenames_by_section,
        )
    warnings.extend(desc_warnings)
    characteristics_html = build_characteristics_html(source.spec_sections)

    final_price = cli.price
    try:
        cli_price_is_zero = float(str(cli.price)) == 0.0
    except ValueError:
        cli_price_is_zero = str(cli.price).strip() in {"", "0"}
    if cli_price_is_zero:
        final_price = 0

    category_value = ""
    if taxonomy.parent_category and taxonomy.leaf_category:
        from .taxonomy import TaxonomyResolver

        category_value = TaxonomyResolver().serialize_category(taxonomy, cli.boxnow)

    image_count_for_csv = cli.photos
    if downloaded_image_count is not None and downloaded_image_count > 0:
        image_count_for_csv = downloaded_image_count
        if downloaded_image_count < cli.photos:
            warnings.append("csv_image_count_capped_to_downloaded_gallery")

    row = {
        "model": cli.model,
        "mpn": canonical_mpn,
        "name": canonical_name,
        "description": description_html,
        "characteristics": characteristics_html,
        "category": category_value,
        "image": f"catalog/01_main/{cli.model}/{cli.model}-1.jpg",
        "additional_image": build_additional_image_value(cli.model, image_count_for_csv),
        "manufacturer": manufacturer,
        "price": as_decimal_string(final_price),
        "quantity": "0",
        "minimum": "1",
        "subtract": "1",
        "stock_status": "Έως 30 ημέρες",
        "status": "0",
        "meta_keyword": serialize_meta_keywords(llm_product.get("meta_keywords") if llm_product else ""),
        "meta_title": meta_title,
        "meta_description": str(llm_product.get("meta_description", "")).strip() if llm_product else "",
        "seo_keyword": seo_keyword,
        "product_url": f"https://www.etranoulis.gr/{seo_keyword}" if seo_keyword else "",
        "related_product": "",
        "bestprice_status": "1",
        "skroutz_status": str(cli.skroutz_status),
        "boxnow": str(cli.boxnow),
    }

    normalized = {
        "input": cli.to_dict(),
        "source": source.to_dict(),
        "taxonomy": taxonomy.to_dict(),
        "schema_match": schema_match.to_dict(),
        "deterministic_product": deterministic,
        "downloaded_gallery_count": downloaded_image_count or 0,
        "downloaded_besco_count": len(besco_filenames_by_section or {}),
        "llm_product": llm_product or {},
        "llm_presentation": llm_presentation or {},
        "csv_row": row,
    }
    return row, normalized, warnings
