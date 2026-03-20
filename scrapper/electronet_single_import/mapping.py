from __future__ import annotations

from typing import Any

from .html_builders import build_characteristics_html, build_description_html
from .models import CLIInput, ParsedProduct, SchemaMatchResult, TaxonomyResolution
from .normalize import slugify_greek_for_seo
from .utils import as_decimal_string, build_additional_image_value



def derive_seo_keyword(name: str, model: str) -> str:
    if not name or not model:
        return ""
    slug = slugify_greek_for_seo(name)
    if not slug:
        return ""
    if model not in slug:
        slug = f"{slug}-{model}"
    return slug



def build_row(
    cli: CLIInput,
    parsed: ParsedProduct,
    taxonomy: TaxonomyResolution,
    schema_match: SchemaMatchResult,
    downloaded_image_count: int | None = None,
    besco_filenames_by_section: dict[int, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    warnings: list[str] = []
    source = parsed.source
    cta_label = taxonomy.sub_category or taxonomy.leaf_category
    description_html, desc_warnings = build_description_html(
        product_name=source.name,
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
        final_price = source.price_value if source.price_value is not None else 0

    seo_keyword = derive_seo_keyword(source.name, cli.model)
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
        "mpn": source.mpn,
        "name": source.name,
        "description": description_html,
        "characteristics": characteristics_html,
        "category": category_value,
        "image": f"catalog/01_main/{cli.model}/{cli.model}-1.jpg",
        "additional_image": build_additional_image_value(cli.model, image_count_for_csv),
        "manufacturer": source.brand,
        "price": as_decimal_string(final_price),
        "quantity": "0",
        "minimum": "1",
        "subtract": "1",
        "stock_status": "Έως 30 ημέρες",
        "status": "0",
        "meta_keyword": "",
        "meta_title": "",
        "meta_description": "",
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
        "downloaded_gallery_count": downloaded_image_count or 0,
        "downloaded_besco_count": len(besco_filenames_by_section or {}),
        "csv_row": row,
    }
    return row, normalized, warnings
