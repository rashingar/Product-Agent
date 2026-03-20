from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from .csv_writer import write_csv_row
from .fetcher import ElectronetFetcher, FetchError
from .html_builders import extract_presentation_blocks
from .mapping import build_row
from .models import CLIInput, GalleryImage
from .parser_product import ElectronetProductParser
from .schema_matcher import SchemaMatcher
from .taxonomy import TaxonomyResolver
from .utils import SCHEMA_LIBRARY_PATH, build_model_output_dir, write_json, write_text

FAIL_MESSAGE = "Generation failed, provide 6-digit model"



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
    if parsed.scheme not in {"http", "https"} or "electronet.gr" not in parsed.netloc:
        raise ValueError("Input URL must be an Electronet product URL")
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



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        cli = validate_input(args)
    except ValueError as exc:
        message = str(exc)
        print(message)
        return 1 if message == FAIL_MESSAGE else 2

    schema_matcher = SchemaMatcher(str(SCHEMA_LIBRARY_PATH))
    product_parser = ElectronetProductParser(known_section_titles=schema_matcher.known_section_titles)
    fetcher = ElectronetFetcher()

    try:
        fetch = fetcher.fetch_httpx(cli.url)
    except FetchError:
        try:
            fetch = fetcher.fetch_playwright(cli.url)
        except FetchError as exc:
            print(str(exc), file=sys.stderr)
            return 3

    parsed = product_parser.parse(fetch.html, fetch.final_url, fallback_used=fetch.fallback_used)

    if parsed.critical_missing:
        try:
            fallback = fetcher.fetch_playwright(cli.url)
            reparsed = product_parser.parse(fallback.html, fallback.final_url, fallback_used=True)
            if len(reparsed.critical_missing) < len(parsed.critical_missing):
                fetch = fallback
                parsed = reparsed
        except FetchError:
            pass

    source_code = parsed.source.product_code
    if not source_code or source_code != cli.model:
        print(FAIL_MESSAGE)
        return 1

    if not parsed.source.name and not parsed.source.spec_sections:
        print("Total parse failure", file=sys.stderr)
        return 4

    model_dir = build_model_output_dir(cli.out, cli.model)
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
    if cli.sections > 0:
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
            if downloaded_besco:
                parsed.source.besco_images = downloaded_besco
                besco_filenames_by_section = {image.position: image.local_filename for image in downloaded_besco}
        except FetchError as exc:
            besco_warnings.append(f"besco_download_failed:{exc}")

    parsed.source.raw_html_path = str(raw_html_path)
    parsed.source.fallback_used = fetch.fallback_used

    write_text(raw_html_path, fetch.html)
    write_json(source_json_path, parsed.source.to_dict())

    taxonomy_resolver = TaxonomyResolver()
    taxonomy, taxonomy_candidates = taxonomy_resolver.resolve(
        breadcrumbs=parsed.source.breadcrumbs,
        url=parsed.source.canonical_url or parsed.source.url,
        name=parsed.source.name,
        key_specs=parsed.source.key_specs,
        spec_sections=parsed.source.spec_sections,
    )
    schema_match, schema_candidates = schema_matcher.match(parsed.source.spec_sections, taxonomy.sub_category)

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
        "fetch_mode": fetch.method,
        "critical_extractors": {
            "product_code": parsed.provenance.get("product_code", "missing"),
            "brand": parsed.provenance.get("brand", "missing"),
            "name": parsed.provenance.get("name", "missing"),
            "price": parsed.provenance.get("price", "missing"),
            "taxonomy": "resolved" if taxonomy.parent_category and taxonomy.leaf_category else "unresolved",
            "schema_match": "matched" if schema_match.score >= 0.35 else ("weak" if schema_match.score > 0 else "none"),
        },
        "missing_fields": parsed.missing_fields,
        "warnings": parsed.warnings
        + gallery_warnings
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
            *gallery_files,
            *besco_files,
        ],
    }
    write_json(report_json_path, report)

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
