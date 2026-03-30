from __future__ import annotations

from pathlib import Path
from typing import Any

from .csv_writer import write_csv_row
from .fetcher import ElectronetFetcher
from .manufacturer_enrichment import enrich_source_from_manufacturer_docs
from .parser_product_electronet import ElectronetProductParser
from .parser_product_manufacturer import ManufacturerProductParser
from .parser_product_skroutz import SkroutzProductParser
from .prepare_stage import (
    _select_skroutz_image_backed_sections,
    apply_skroutz_contract_hints,
    build_identity_checks,
    execute_prepare_stage,
)
from .providers.electronet_provider import ElectronetProvider
from .providers.manufacturer_tefal_provider import ManufacturerTefalProvider
from .providers.skroutz_provider import SkroutzProvider
from .repo_paths import SCHEMA_LIBRARY_PATH
from .schema_matcher import SchemaMatcher
from .source_detection import detect_source, validate_url_scope
from .taxonomy import TaxonomyResolver
from .utils import write_json


def _resolve_provider_for_source(
    *,
    source: str,
    cli,
    fetcher,
    electronet_parser,
    skroutz_parser,
    manufacturer_parser,
):
    del cli
    if source == "electronet":
        return ElectronetProvider(fetcher=fetcher, parser=electronet_parser)
    if source == "skroutz":
        return SkroutzProvider(fetcher=fetcher, parser=skroutz_parser)
    if source == "manufacturer_tefal":
        return ManufacturerTefalProvider(fetcher=fetcher, parser=manufacturer_parser)
    return None


def execute_full_run(cli) -> dict[str, Any]:
    result = execute_prepare_stage(
        cli,
        detect_source_fn=detect_source,
        validate_url_scope_fn=validate_url_scope,
        schema_matcher_factory=SchemaMatcher,
        electronet_parser_factory=ElectronetProductParser,
        skroutz_parser_factory=SkroutzProductParser,
        manufacturer_parser_factory=ManufacturerProductParser,
        fetcher_factory=ElectronetFetcher,
        taxonomy_resolver_factory=TaxonomyResolver,
        resolve_provider_for_source_fn=_resolve_provider_for_source,
        enrich_source_from_manufacturer_docs_fn=enrich_source_from_manufacturer_docs,
    )

    model_dir = Path(result["model_dir"])
    csv_path = model_dir / f"{cli.model}.csv"
    headers, ordered_row = write_csv_row(result["row"], csv_path)
    result["normalized"]["csv_headers"] = headers
    result["normalized"]["csv_ordered_row"] = ordered_row
    write_json(result["normalized_json_path"], result["normalized"])
    if str(csv_path) not in result["report"]["files_written"]:
        result["report"]["files_written"].append(str(csv_path))
    write_json(result["report_json_path"], result["report"])
    result["csv_path"] = csv_path
    return result


__all__ = [
    "SCHEMA_LIBRARY_PATH",
    "ElectronetFetcher",
    "ElectronetProductParser",
    "ElectronetProvider",
    "ManufacturerProductParser",
    "ManufacturerTefalProvider",
    "SchemaMatcher",
    "SkroutzProductParser",
    "SkroutzProvider",
    "TaxonomyResolver",
    "_resolve_provider_for_source",
    "_select_skroutz_image_backed_sections",
    "apply_skroutz_contract_hints",
    "build_identity_checks",
    "detect_source",
    "enrich_source_from_manufacturer_docs",
    "execute_full_run",
    "validate_url_scope",
]
