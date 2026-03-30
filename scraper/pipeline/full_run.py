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
from .providers.registry import bootstrap_runtime_provider_registry, source_to_provider_id
from .repo_paths import SCHEMA_LIBRARY_PATH
from .schema_matcher import SchemaMatcher
from .source_detection import detect_source, validate_url_scope
from .taxonomy import TaxonomyResolver
from .utils import write_json


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
        bootstrap_provider_registry_fn=bootstrap_runtime_provider_registry,
        source_to_provider_id_fn=source_to_provider_id,
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
    "ManufacturerProductParser",
    "SchemaMatcher",
    "SkroutzProductParser",
    "TaxonomyResolver",
    "_select_skroutz_image_backed_sections",
    "apply_skroutz_contract_hints",
    "bootstrap_runtime_provider_registry",
    "build_identity_checks",
    "detect_source",
    "enrich_source_from_manufacturer_docs",
    "execute_full_run",
    "source_to_provider_id",
    "validate_url_scope",
]
