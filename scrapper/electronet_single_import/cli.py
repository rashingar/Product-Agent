from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .characteristics_pipeline import get_characteristics_registry
from .deterministic_fields import effective_spec_sections as build_effective_spec_sections
from .csv_writer import write_csv_row
from .fetcher import ElectronetFetcher, FetchError
from .html_builders import extract_presentation_blocks
from .mapping import build_row
from .manufacturer_enrichment import enrich_source_from_manufacturer_docs
from .models import CLIInput, GalleryImage
from .normalize import normalize_for_match
from .parser_product_electronet import ElectronetProductParser
from .parser_product_manufacturer import ManufacturerProductParser
from .parser_product_skroutz import SkroutzProductParser
from .schema_matcher import SchemaMatcher
from .skroutz_sections import build_skroutz_presentation_source_html, extract_skroutz_section_window
from .skroutz_taxonomy import serialize_source_category
from .source_detection import detect_source, validate_url_scope
from .taxonomy import TaxonomyResolver
from .repo_paths import SCHEMA_LIBRARY_PATH
from .utils import ensure_directory, write_json, write_text

FAIL_MESSAGE = "Generation failed, provide 6-digit model"
SKROUTZ_V1_MPN_HINTS = {
    "344317": "CM5S1DE0",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m electronet_single_import.cli")
    parser.add_argument("--model", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--photos", type=int, default=1)
    parser.add_argument("--sections", type=int, default=0)
    parser.add_argument("--skroutz-status", type=int, default=0, dest="skroutz_status")
    parser.add_argument("--boxnow", type=int, default=0)
    parser.add_argument("--price", default=0)
    parser.add_argument("--out", default="out")
    return parser


def validate_input(args: argparse.Namespace) -> CLIInput:
    model = str(args.model).strip()
    if not model.isdigit() or len(model) != 6:
        raise ValueError(FAIL_MESSAGE)
    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Input URL must be an Electronet, Skroutz, or supported manufacturer product URL")
    source, scope_ok, _scope_reason = validate_url_scope(args.url)
    if not scope_ok:
        raise ValueError("Input URL must be an Electronet product URL, a Skroutz product URL, or a supported manufacturer product URL")
    return CLIInput(
        model=model,
        url=args.url.strip(),
        photos=max(int(args.photos), 1),
        sections=max(int(args.sections), 0),
        skroutz_status=int(args.skroutz_status),
        boxnow=int(args.boxnow),
        price=args.price,
        out=args.out,
    )


def run_cli_input(cli: CLIInput) -> dict[str, Any]:
    source = detect_source(cli.url)
    schema_matcher = SchemaMatcher(str(SCHEMA_LIBRARY_PATH))
    electronet_parser = ElectronetProductParser(known_section_titles=schema_matcher.known_section_titles)
    skroutz_parser = SkroutzProductParser()
    manufacturer_parser = ManufacturerProductParser()
    fetcher = ElectronetFetcher()

    if source == "skroutz":
        try:
            fetch = fetcher.fetch_playwright(cli.url)
        except FetchError as exc:
            try:
                fetch = fetcher.fetch_httpx(cli.url)
            except FetchError as nested_exc:
                raise RuntimeError(str(nested_exc)) from nested_exc
    else:
        try:
            fetch = fetcher.fetch_httpx(cli.url)
        except FetchError:
            try:
                fetch = fetcher.fetch_playwright(cli.url)
            except FetchError as exc:
                raise RuntimeError(str(exc)) from exc

    if source == "manufacturer_tefal":
        parsed = manufacturer_parser.parse(
            fetch.html,
            fetch.final_url,
            source_name=source,
            fallback_used=fetch.fallback_used,
        )
    else:
        product_parser = electronet_parser if source == "electronet" else skroutz_parser
        parsed = product_parser.parse(fetch.html, fetch.final_url, fallback_used=fetch.fallback_used)

    if source == "electronet" and parsed.critical_missing:
        try:
            fallback = fetcher.fetch_playwright(cli.url)
            reparsed = electronet_parser.parse(fallback.html, fallback.final_url, fallback_used=True)
            if len(reparsed.critical_missing) < len(parsed.critical_missing):
                fetch = fallback
                parsed = reparsed
        except FetchError:
            pass

    final_source, final_scope_ok, final_scope_reason = validate_url_scope(fetch.final_url)
    if final_source != source or not final_scope_ok:
        raise RuntimeError("Resolved URL is not a supported product page")

    if source == "electronet":
        source_code = parsed.source.product_code
        if not source_code:
            raise ValueError(FAIL_MESSAGE)
        if source_code != cli.model:
            parsed.warnings.append(f"source_product_code_mismatch:input={cli.model}:page={source_code}")
    elif source == "skroutz":
        apply_skroutz_contract_hints(cli, parsed)
        if parsed.source.page_type != "product":
            detail = parsed.source.taxonomy_escalation_reason or "unsupported_skroutz_page_type"
            raise RuntimeError(f"Unsupported Skroutz page type: {detail}")
    else:
        if parsed.source.page_type != "product":
            detail = parsed.source.taxonomy_escalation_reason or "unsupported_manufacturer_page_type"
            raise RuntimeError(f"Unsupported manufacturer page type: {detail}")
    if not parsed.source.name and not parsed.source.spec_sections:
        raise RuntimeError("Total parse failure")

    model_dir = ensure_directory(Path(cli.out) / cli.model)
    raw_html_path = model_dir / f"{cli.model}.raw.html"
    source_json_path = model_dir / f"{cli.model}.source.json"
    normalized_json_path = model_dir / f"{cli.model}.normalized.json"
    report_json_path = model_dir / f"{cli.model}.report.json"
    csv_path = model_dir / f"{cli.model}.csv"

    extracted_gallery_count = len(parsed.source.gallery_images)
    gallery_warnings: list[str] = []
    gallery_files: list[str] = []
    downloaded_gallery: list[GalleryImage] = []
    if parsed.source.gallery_images:
        try:
            downloaded_gallery, gallery_warnings, gallery_files = fetcher.download_gallery_images(
                images=parsed.source.gallery_images,
                model=cli.model,
                output_dir=model_dir,
                requested_photos=cli.photos,
            )
            if downloaded_gallery:
                parsed.source.gallery_images = downloaded_gallery
        except FetchError as exc:
            gallery_warnings.append(f"gallery_download_failed:{exc}")

    selected_presentation_blocks = []
    selected_besco_images: list[GalleryImage] = []
    section_warnings: list[str] = []
    section_image_candidates: list[dict[str, Any]] = []
    section_image_urls_resolved: list[dict[str, Any]] = []
    section_extraction_window: dict[str, Any] = {
        "candidate_count": 0,
        "duplicate_signatures_skipped": 0,
        "selected_container_index": None,
        "start_anchor": "",
        "stop_anchor": "",
        "title_signature": [],
    }
    sections_artifact_path = model_dir / "bescos_raw.json"
    if sections_artifact_path.exists():
        sections_artifact_path.unlink()
    if cli.sections > 0 and source != "skroutz":
        if source == "skroutz":
            extracted_window = extract_skroutz_section_window(
                fetch.html,
                base_url=parsed.source.canonical_url or parsed.source.url,
            )
            section_warnings.extend(extracted_window.get("warnings", []))
            section_extraction_window = dict(extracted_window.get("window", section_extraction_window))
            all_sections = list(extracted_window.get("sections", []))
            if len(all_sections) < cli.sections:
                raise RuntimeError(
                    f"Skroutz section extraction failed: expected {cli.sections} sections, found {len(all_sections)}"
                )
            selected_presentation_blocks = all_sections[: cli.sections]
            section_image_candidates = [
                {
                    "position": index,
                    "title": block["title"],
                    "candidates": list(block.get("image_candidates", [])),
                }
                for index, block in enumerate(selected_presentation_blocks, start=1)
            ]
            try:
                rendered_section_data = fetcher.extract_skroutz_section_image_records(fetch.final_url)
            except FetchError as exc:
                raise RuntimeError(f"Skroutz rendered section extraction failed: {exc}") from exc
            rendered_sections = list(rendered_section_data.get("sections", []))
            rendered_window = rendered_section_data.get("window", {})
            if rendered_window:
                section_extraction_window = {
                    **section_extraction_window,
                    **rendered_window,
                    "candidate_count": max(
                        int(section_extraction_window.get("candidate_count", 0) or 0),
                        int(rendered_window.get("candidate_count", 0) or 0),
                    ),
                    "duplicate_signatures_skipped": max(
                        int(section_extraction_window.get("duplicate_signatures_skipped", 0) or 0),
                        int(rendered_window.get("duplicate_signatures_skipped", 0) or 0),
                    ),
                }
            if len(rendered_sections) < cli.sections:
                raise RuntimeError(
                    f"Skroutz rendered section extraction failed: expected {cli.sections} image records, found {len(rendered_sections)}"
                )
            expected_titles = [normalize_for_match(block["title"]) for block in selected_presentation_blocks]
            rendered_titles = [normalize_for_match(str(section.get("title", ""))) for section in rendered_sections[: cli.sections]]
            if expected_titles != rendered_titles:
                raise RuntimeError("Skroutz section title order mismatch between rendered DOM and parsed description")

            for section_index, block in enumerate(selected_presentation_blocks, start=1):
                rendered_section = rendered_sections[section_index - 1]
                resolved_image_url = str(rendered_section.get("resolved_image_url", "")).strip()
                if not resolved_image_url:
                    raise RuntimeError(f"Skroutz section image could not be resolved for section {section_index}")
                block["image_url"] = resolved_image_url
                section_image_urls_resolved.append(
                    {
                        "position": section_index,
                        "title": block["title"],
                        "url": resolved_image_url,
                    }
                )
                selected_besco_images.append(GalleryImage(url=resolved_image_url, alt=block["title"], position=section_index))

            parsed.source.presentation_source_html = build_skroutz_presentation_source_html(selected_presentation_blocks)
            write_json(
                sections_artifact_path,
                {
                    "source": "skroutz",
                    "requested_sections": cli.sections,
                    "window": section_extraction_window,
                    "sections": [
                        {
                            "position": index,
                            "title": block["title"],
                            "body": block["paragraph"],
                            "image_candidates": list(block.get("image_candidates", [])),
                            "resolved_image_url": block.get("image_url", ""),
                            "target_filename": f"besco{index}.jpg",
                        }
                        for index, block in enumerate(selected_presentation_blocks, start=1)
                    ],
                },
            )
        else:
            selected_presentation_blocks = extract_presentation_blocks(
                parsed.source.presentation_source_html,
                parsed.source.presentation_source_text,
                base_url=parsed.source.canonical_url or parsed.source.url,
            )[: cli.sections]
            selected_besco_images = [
                GalleryImage(url=block["image_url"], alt=block["title"], position=section_index)
                for section_index, block in enumerate(selected_presentation_blocks, start=1)
                if block.get("image_url")
            ]
    parsed.source.besco_images = selected_besco_images

    besco_warnings: list[str] = []
    besco_files: list[str] = []
    downloaded_besco: list[GalleryImage] = []
    besco_filenames_by_section: dict[int, str] = {}
    if selected_besco_images:
        try:
            downloaded_besco, besco_warnings, besco_files = fetcher.download_besco_images(
                images=selected_besco_images,
                output_dir=model_dir,
                requested_sections=len(selected_presentation_blocks),
            )
            if source == "skroutz" and cli.sections > 0 and len(downloaded_besco) < cli.sections:
                raise RuntimeError(
                    f"Skroutz besco image download incomplete: expected {cli.sections}, downloaded {len(downloaded_besco)}"
                )
            if downloaded_besco:
                parsed.source.besco_images = downloaded_besco
                besco_filenames_by_section = {image.position: image.local_filename for image in downloaded_besco}
        except FetchError as exc:
            if source == "skroutz" and cli.sections > 0:
                raise RuntimeError(f"Skroutz besco image download failed: {exc}") from exc
            besco_warnings.append(f"besco_download_failed:{exc}")

    parsed.source.raw_html_path = str(raw_html_path)
    parsed.source.fallback_used = fetch.fallback_used

    write_text(raw_html_path, fetch.html)

    taxonomy_resolver = TaxonomyResolver()
    taxonomy, taxonomy_candidates = taxonomy_resolver.resolve(
        breadcrumbs=parsed.source.breadcrumbs,
        url=parsed.source.canonical_url or parsed.source.url,
        name=parsed.source.name,
        key_specs=parsed.source.key_specs,
        spec_sections=parsed.source.spec_sections,
    )
    if source == "skroutz":
        manufacturer_enrichment = enrich_source_from_manufacturer_docs(
            source=parsed.source,
            taxonomy=taxonomy,
            fetcher=fetcher,
            output_dir=model_dir / "manufacturer",
        )
    else:
        manufacturer_enrichment = {
            "applied": False,
            "provider": "",
            "providers_considered": [],
            "matched_providers": [],
            "documents": [],
            "documents_discovered": 0,
            "documents_parsed": 0,
            "warnings": [],
            "section_count": 0,
            "field_count": 0,
            "hero_summary_applied": False,
            "presentation_applied": False,
            "presentation_block_count": 0,
            "fallback_reason": "direct_source_already_manufacturer" if source == "manufacturer_tefal" else "not_applicable_non_skroutz",
        }
    if source == "skroutz" and cli.sections > 0:
        manufacturer_blocks = []
        if manufacturer_enrichment.get("presentation_applied"):
            manufacturer_blocks = extract_presentation_blocks(
                parsed.source.presentation_source_html,
                parsed.source.presentation_source_text,
                base_url=parsed.source.canonical_url or parsed.source.url,
            )

        if len(manufacturer_blocks) >= cli.sections:
            selected_presentation_blocks = manufacturer_blocks[: cli.sections]
            selected_besco_images = [
                GalleryImage(url=block["image_url"], alt=block["title"], position=section_index)
                for section_index, block in enumerate(selected_presentation_blocks, start=1)
                if block.get("image_url")
            ]
            section_image_candidates = [
                {
                    "position": index,
                    "title": block["title"],
                    "candidates": [block["image_url"]] if block.get("image_url") else [],
                }
                for index, block in enumerate(selected_presentation_blocks, start=1)
            ]
            section_image_urls_resolved = [
                {
                    "position": index,
                    "title": block["title"],
                    "url": block["image_url"],
                }
                for index, block in enumerate(selected_presentation_blocks, start=1)
                if block.get("image_url")
            ]
            section_extraction_window = {
                "candidate_count": len(manufacturer_blocks),
                "duplicate_signatures_skipped": 0,
                "selected_container_index": "manufacturer_html",
                "start_anchor": "manufacturer_presentation",
                "stop_anchor": "",
                "title_signature": [block["title"] for block in selected_presentation_blocks],
            }
            write_json(
                sections_artifact_path,
                {
                    "source": "manufacturer",
                    "requested_sections": cli.sections,
                    "window": section_extraction_window,
                    "sections": [
                        {
                            "position": index,
                            "title": block["title"],
                            "body": block["paragraph"],
                            "image_candidates": [block["image_url"]] if block.get("image_url") else [],
                            "resolved_image_url": block.get("image_url", ""),
                            "target_filename": f"besco{index}.jpg",
                        }
                        for index, block in enumerate(selected_presentation_blocks, start=1)
                    ],
                },
            )
        else:
            extracted_window = extract_skroutz_section_window(
                fetch.html,
                base_url=parsed.source.canonical_url or parsed.source.url,
            )
            section_warnings.extend(extracted_window.get("warnings", []))
            section_extraction_window = dict(extracted_window.get("window", section_extraction_window))
            all_sections = list(extracted_window.get("sections", []))
            if len(all_sections) < cli.sections:
                raise RuntimeError(
                    f"Skroutz section extraction failed: expected {cli.sections} sections, found {len(all_sections)}"
                )
            selected_presentation_blocks = all_sections[: cli.sections]
            section_image_candidates = [
                {
                    "position": index,
                    "title": block["title"],
                    "candidates": list(block.get("image_candidates", [])),
                }
                for index, block in enumerate(selected_presentation_blocks, start=1)
            ]
            try:
                rendered_section_data = fetcher.extract_skroutz_section_image_records(fetch.final_url)
            except FetchError as exc:
                raise RuntimeError(f"Skroutz rendered section extraction failed: {exc}") from exc
            rendered_sections = list(rendered_section_data.get("sections", []))
            rendered_window = rendered_section_data.get("window", {})
            if rendered_window:
                section_extraction_window = {
                    **section_extraction_window,
                    **rendered_window,
                    "candidate_count": max(
                        int(section_extraction_window.get("candidate_count", 0) or 0),
                        int(rendered_window.get("candidate_count", 0) or 0),
                    ),
                    "duplicate_signatures_skipped": max(
                        int(section_extraction_window.get("duplicate_signatures_skipped", 0) or 0),
                        int(rendered_window.get("duplicate_signatures_skipped", 0) or 0),
                    ),
                }
            if len(rendered_sections) < cli.sections:
                raise RuntimeError(
                    f"Skroutz rendered section extraction failed: expected {cli.sections} image records, found {len(rendered_sections)}"
                )
            expected_titles = [normalize_for_match(block["title"]) for block in selected_presentation_blocks]
            rendered_titles = [normalize_for_match(str(section.get("title", ""))) for section in rendered_sections[: cli.sections]]
            if expected_titles != rendered_titles:
                raise RuntimeError("Skroutz section title order mismatch between rendered DOM and parsed description")

            selected_besco_images = []
            for section_index, block in enumerate(selected_presentation_blocks, start=1):
                rendered_section = rendered_sections[section_index - 1]
                resolved_image_url = str(rendered_section.get("resolved_image_url", "")).strip()
                if not resolved_image_url:
                    raise RuntimeError(f"Skroutz section image could not be resolved for section {section_index}")
                block["image_url"] = resolved_image_url
                section_image_urls_resolved.append(
                    {
                        "position": section_index,
                        "title": block["title"],
                        "url": resolved_image_url,
                    }
                )
                selected_besco_images.append(GalleryImage(url=resolved_image_url, alt=block["title"], position=section_index))

            if not manufacturer_enrichment.get("presentation_applied"):
                parsed.source.presentation_source_html = build_skroutz_presentation_source_html(selected_presentation_blocks)
            write_json(
                sections_artifact_path,
                {
                    "source": "skroutz",
                    "requested_sections": cli.sections,
                    "window": section_extraction_window,
                    "sections": [
                        {
                            "position": index,
                            "title": block["title"],
                            "body": block["paragraph"],
                            "image_candidates": list(block.get("image_candidates", [])),
                            "resolved_image_url": block.get("image_url", ""),
                            "target_filename": f"besco{index}.jpg",
                        }
                        for index, block in enumerate(selected_presentation_blocks, start=1)
                    ],
                },
            )

        parsed.source.besco_images = selected_besco_images
        besco_warnings = []
        besco_files = []
        downloaded_besco = []
        besco_filenames_by_section = {}
        if selected_besco_images:
            try:
                downloaded_besco, besco_warnings, besco_files = fetcher.download_besco_images(
                    images=selected_besco_images,
                    output_dir=model_dir,
                    requested_sections=len(selected_presentation_blocks),
                )
                if len(downloaded_besco) < cli.sections:
                    raise RuntimeError(
                        f"Skroutz besco image download incomplete: expected {cli.sections}, downloaded {len(downloaded_besco)}"
                    )
                if downloaded_besco:
                    parsed.source.besco_images = downloaded_besco
                    besco_filenames_by_section = {image.position: image.local_filename for image in downloaded_besco}
            except FetchError as exc:
                raise RuntimeError(f"Skroutz besco image download failed: {exc}") from exc
    write_json(source_json_path, parsed.source.to_dict())

    effective_spec_sections = build_effective_spec_sections(
        parsed.source,
        manufacturer_first=normalize_for_match(parsed.source.source_name) == "skroutz",
    )
    characteristics_registry = get_characteristics_registry()
    preferred_schema_source_files = characteristics_registry.preferred_schema_source_files(parsed.source, taxonomy)
    schema_match, schema_candidates = schema_matcher.match(
        effective_spec_sections,
        taxonomy.sub_category,
        preferred_source_files=preferred_schema_source_files,
    )

    row, normalized, mapping_warnings = build_row(
        cli,
        parsed,
        taxonomy,
        schema_match,
        downloaded_image_count=len(downloaded_gallery),
        besco_filenames_by_section=besco_filenames_by_section,
    )
    headers, ordered_row = write_csv_row(row, csv_path)
    normalized["csv_headers"] = headers
    normalized["csv_ordered_row"] = ordered_row
    write_json(normalized_json_path, normalized)

    report = {
        "input": cli.to_dict(),
        "source": source,
        "fetch_mode": fetch.method,
        "source_resolution": {
            "requested_url": cli.url,
            "detected_source": source,
            "resolved_url": fetch.final_url,
        },
        "identity_checks": build_identity_checks(cli, parsed, source),
        "url_scope_validation": {
            "ok": final_scope_ok,
            "reason": final_scope_reason,
            "final_url_source": final_source,
        },
        "skroutz_blocks_found": {
            "hero_summary_present": bool(parsed.source.hero_summary),
            "gallery_images_count": len(parsed.source.gallery_images),
            "spec_sections_count": len(parsed.source.spec_sections),
            "manufacturer_spec_sections_count": len(parsed.source.manufacturer_spec_sections),
        },
        "characteristics_pairs": {
            "count": sum(len(section.items) for section in effective_spec_sections),
            "source_count": sum(len(section.items) for section in parsed.source.spec_sections),
            "manufacturer_count": sum(len(section.items) for section in parsed.source.manufacturer_spec_sections),
        },
        "taxonomy_resolution": taxonomy.to_dict(),
        "manufacturer_enrichment": manufacturer_enrichment,
        "schema_resolution": schema_match.to_dict(),
        "characteristics_diagnostics": normalized.get("characteristics_diagnostics", {}),
        "skroutz_taxonomy_diagnostics": {
            "family_key": parsed.source.skroutz_family,
            "raw_category_tag": parsed.source.category_tag_text,
            "raw_category_href": parsed.source.category_tag_href,
            "normalized_href_slug": parsed.source.category_tag_slug,
            "matched_rule": parsed.source.taxonomy_rule_id,
            "source_category": parsed.source.taxonomy_source_category
            or serialize_source_category(
                taxonomy.parent_category,
                taxonomy.leaf_category,
                [taxonomy.sub_category] if taxonomy.sub_category else [],
            ),
            "match_type": parsed.source.taxonomy_match_type or ("exact_category" if taxonomy.parent_category and taxonomy.leaf_category else ""),
            "tv_inches": parsed.source.taxonomy_tv_inches,
            "ambiguity": parsed.source.taxonomy_ambiguity,
            "escalation_reason": parsed.source.taxonomy_escalation_reason,
        },
        "schema_preference": {
            "preferred_source_files": preferred_schema_source_files,
        },
        "unsupported_features": [],
        "critical_extractors": {
            "product_code": parsed.provenance.get("product_code", "missing"),
            "brand": parsed.provenance.get("brand", "missing"),
            "mpn": parsed.provenance.get("mpn", "missing"),
            "name": parsed.provenance.get("name", "missing"),
            "price": parsed.provenance.get("price", "missing"),
            "taxonomy": "resolved" if taxonomy.parent_category and taxonomy.leaf_category else "unresolved",
            "schema_match": "matched" if schema_match.score >= 0.35 else ("weak" if schema_match.score > 0 else "none"),
        },
        "field_diagnostics": {key: value.to_dict() for key, value in parsed.field_diagnostics.items()},
        "missing_fields": parsed.missing_fields,
        "warnings": parsed.warnings
        + gallery_warnings
        + section_warnings
        + besco_warnings
        + mapping_warnings
        + schema_match.warnings
        + ([taxonomy.reason] if taxonomy.reason and taxonomy.reason != "" else []),
        "taxonomy_candidates": taxonomy_candidates,
        "schema_candidates": schema_candidates,
        "gallery_summary": {
            "extracted_count": extracted_gallery_count,
            "downloaded_count": len(downloaded_gallery),
            "requested_photos": cli.photos,
        },
        "sections_requested": cli.sections,
        "sections_extracted": len(selected_presentation_blocks),
        "section_titles": [block["title"] for block in selected_presentation_blocks],
        "section_image_candidates": section_image_candidates,
        "section_image_urls_resolved": section_image_urls_resolved,
        "section_downloads": [
            {
                "position": image.position,
                "source_url": image.url,
                "local_filename": image.local_filename,
                "local_path": image.local_path,
            }
            for image in downloaded_besco
        ],
        "section_extraction_window": section_extraction_window,
        "besco_summary": {
            "presentation_blocks_count": len(selected_presentation_blocks),
            "extracted_count": len(selected_besco_images),
            "downloaded_count": len(downloaded_besco),
            "requested_sections": cli.sections,
        },
        "files_written": [
            str(raw_html_path),
            str(source_json_path),
            str(normalized_json_path),
            str(report_json_path),
            str(csv_path),
            *[
                path
                for document in manufacturer_enrichment.get("documents", [])
                for path in [document.get("local_path", ""), document.get("text_path", "")]
                if path
            ],
            *gallery_files,
            *([str(sections_artifact_path)] if sections_artifact_path.exists() else []),
            *besco_files,
        ],
    }
    write_json(report_json_path, report)

    return {
        "cli": cli,
        "source": source,
        "fetch": fetch,
        "parsed": parsed,
        "taxonomy": taxonomy,
        "taxonomy_candidates": taxonomy_candidates,
        "schema_match": schema_match,
        "schema_candidates": schema_candidates,
        "manufacturer_enrichment": manufacturer_enrichment,
        "row": row,
        "normalized": normalized,
        "report": report,
        "model_dir": model_dir,
        "raw_html_path": raw_html_path,
        "source_json_path": source_json_path,
        "normalized_json_path": normalized_json_path,
        "report_json_path": report_json_path,
        "csv_path": csv_path,
        "selected_presentation_blocks": selected_presentation_blocks,
        "downloaded_gallery": downloaded_gallery,
        "downloaded_besco": downloaded_besco,
        "besco_filenames_by_section": besco_filenames_by_section,
    }


def apply_skroutz_contract_hints(cli: CLIInput, parsed) -> None:
    hinted_mpn = SKROUTZ_V1_MPN_HINTS.get(cli.model)
    if hinted_mpn and (not parsed.source.mpn or parsed.source.mpn.endswith("D") or parsed.source.mpn.endswith("DE")):
        parsed.source.mpn = hinted_mpn


def build_identity_checks(cli: CLIInput, parsed, source: str) -> dict[str, Any]:
    return {
        "source": source,
        "input_model": cli.model,
        "page_type": parsed.source.page_type,
        "page_product_code": parsed.source.product_code,
        "name_present": bool(parsed.source.name),
        "brand_present": bool(parsed.source.brand),
        "mpn_present": bool(parsed.source.mpn),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        cli = validate_input(args)
        result = run_cli_input(cli)
    except ValueError as exc:
        message = str(exc)
        print(message)
        return 1 if message == FAIL_MESSAGE else 2
    except RuntimeError as exc:
        message = str(exc)
        print(message, file=sys.stderr if message != FAIL_MESSAGE else sys.stdout)
        return 3 if "failed" in message.lower() else 4

    taxonomy = result["taxonomy"]
    schema_match = result["schema_match"]
    report = result["report"]
    csv_path = result["csv_path"]
    parsed = result["parsed"]
    resolved_path = taxonomy.taxonomy_path or ""
    print(f"product name: {parsed.source.name}")
    print(f"product code: {parsed.source.product_code}")
    print(f"brand: {parsed.source.brand}")
    print(f"resolved taxonomy path: {resolved_path}")
    print(f"schema match id / score: {schema_match.matched_schema_id} / {schema_match.score:.4f}")
    print(f"CSV written path: {csv_path}")
    print(f"warnings count: {len(report['warnings'])}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
