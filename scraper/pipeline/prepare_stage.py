from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .fetcher import ElectronetFetcher, FetchError
from .html_builders import extract_presentation_blocks
from .models import CLIInput, GalleryImage, ParsedProduct
from .normalize import normalize_for_match
from .prepare_provider_resolution import PrepareProviderResolutionResult, resolve_prepare_provider_resolution
from .prepare_result_assembly import assemble_prepare_result
from .prepare_scrape_persistence import (
    PrepareScrapePersistenceInput,
    PrepareScrapePersistenceResult,
    persist_prepare_scrape_artifacts,
)
from .prepare_taxonomy_enrichment import PrepareTaxonomyEnrichmentResult, resolve_prepare_taxonomy_enrichment
from .skroutz_sections import build_skroutz_presentation_source_html, extract_skroutz_section_window
from .source_detection import validate_url_scope
from .utils import ensure_directory


def _select_skroutz_image_backed_sections(
    all_sections: list[dict[str, Any]],
    rendered_sections: list[dict[str, Any]],
    requested_sections: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(all_sections) < requested_sections:
        raise RuntimeError(
            f"Skroutz section extraction failed: expected {requested_sections} sections, found {len(all_sections)}"
        )

    if len(rendered_sections) < requested_sections:
        raise RuntimeError(
            f"Skroutz rendered section extraction failed: expected {requested_sections} image records, found {len(rendered_sections)}"
        )

    selected_blocks: list[dict[str, Any]] = []
    selected_rendered_sections: list[dict[str, Any]] = []
    for block, rendered_section in zip(all_sections, rendered_sections):
        block_title = normalize_for_match(str(block.get("title", "")))
        rendered_title = normalize_for_match(str(rendered_section.get("title", "")))
        if block_title != rendered_title:
            raise RuntimeError("Skroutz section title order mismatch between rendered DOM and parsed description")

        resolved_image_url = str(rendered_section.get("resolved_image_url", "")).strip()
        if not resolved_image_url:
            continue

        selected_blocks.append(block)
        selected_rendered_sections.append(rendered_section)
        if len(selected_blocks) == requested_sections:
            return selected_blocks, selected_rendered_sections

    raise RuntimeError(
        f"Skroutz rendered section extraction failed: expected {requested_sections} image-backed sections, found {len(selected_blocks)}"
    )


def execute_prepare_stage(
    cli: CLIInput,
    *,
    model_dir: Path | None = None,
    validate_url_scope_fn: Callable[[str], tuple[str, bool, str]] = validate_url_scope,
    fetcher_factory: Callable[[], ElectronetFetcher] = ElectronetFetcher,
    resolve_prepare_provider_input_fn: Callable[..., PrepareProviderResolutionResult] = resolve_prepare_provider_resolution,
    resolve_prepare_taxonomy_enrichment_fn: Callable[..., PrepareTaxonomyEnrichmentResult] = resolve_prepare_taxonomy_enrichment,
    assemble_prepare_result_fn: Callable[..., Any] = assemble_prepare_result,
    persist_prepare_scrape_artifacts_fn: Callable[[PrepareScrapePersistenceInput], PrepareScrapePersistenceResult] = persist_prepare_scrape_artifacts,
) -> dict[str, Any]:
    fetcher = fetcher_factory()
    provider_resolution = resolve_prepare_provider_input_fn(
        cli,
        validate_url_scope_fn=validate_url_scope_fn,
        fetcher_factory=lambda: fetcher,
    )
    source = provider_resolution.source
    fetch = provider_resolution.fetch
    parsed = provider_resolution.parsed
    final_source, final_scope_ok, final_scope_reason = validate_url_scope_fn(fetch.final_url)

    resolved_model_dir = ensure_directory(model_dir or (Path(cli.out) / cli.model))
    scrape_persistence_input = PrepareScrapePersistenceInput(
        model=cli.model,
        scrape_dir=resolved_model_dir,
        raw_html=fetch.html,
        source_payload={},
        normalized_payload={},
        report_payload={},
    )

    extracted_gallery_count = len(parsed.source.gallery_images)
    gallery_warnings: list[str] = []
    gallery_files: list[str] = []
    downloaded_gallery: list[GalleryImage] = []
    if parsed.source.gallery_images:
        try:
            downloaded_gallery, gallery_warnings, gallery_files = fetcher.download_gallery_images(
                images=parsed.source.gallery_images,
                model=cli.model,
                output_dir=resolved_model_dir,
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
    sections_artifact_payload: dict[str, Any] | None = None
    if cli.sections > 0 and source != "skroutz":
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
                output_dir=resolved_model_dir,
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

    parsed.source.raw_html_path = str(scrape_persistence_input.raw_html_path)
    parsed.source.fallback_used = fetch.fallback_used

    taxonomy_enrichment = resolve_prepare_taxonomy_enrichment_fn(
        source=source,
        parsed=parsed,
        fetcher=fetcher,
        model_dir=resolved_model_dir,
    )
    taxonomy = taxonomy_enrichment.taxonomy
    taxonomy_candidates = taxonomy_enrichment.taxonomy_candidates
    manufacturer_enrichment = taxonomy_enrichment.manufacturer_enrichment
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
            sections_artifact_payload = {
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
            }
        else:
            extracted_window = extract_skroutz_section_window(
                fetch.html,
                base_url=parsed.source.canonical_url or parsed.source.url,
            )
            section_warnings.extend(extracted_window.get("warnings", []))
            section_extraction_window = dict(extracted_window.get("window", section_extraction_window))
            all_sections = list(extracted_window.get("sections", []))
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
            selected_presentation_blocks, rendered_sections = _select_skroutz_image_backed_sections(
                all_sections=all_sections,
                rendered_sections=rendered_sections,
                requested_sections=cli.sections,
            )
            section_image_candidates = [
                {
                    "position": index,
                    "title": block["title"],
                    "candidates": list(block.get("image_candidates", [])),
                }
                for index, block in enumerate(selected_presentation_blocks, start=1)
            ]

            selected_besco_images = []
            for section_index, block in enumerate(selected_presentation_blocks, start=1):
                rendered_section = rendered_sections[section_index - 1]
                resolved_image_url = str(rendered_section.get("resolved_image_url", "")).strip()
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
            sections_artifact_payload = {
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
            }

        parsed.source.besco_images = selected_besco_images
        besco_warnings = []
        besco_files = []
        downloaded_besco = []
        besco_filenames_by_section = {}
        if selected_besco_images:
            try:
                downloaded_besco, besco_warnings, besco_files = fetcher.download_besco_images(
                    images=selected_besco_images,
                    output_dir=resolved_model_dir,
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
    source_payload = parsed.source.to_dict()

    result_assembly = assemble_prepare_result_fn(
        cli=cli,
        source=source,
        fetch=fetch,
        parsed=parsed,
        taxonomy=taxonomy,
        taxonomy_candidates=taxonomy_candidates,
        manufacturer_enrichment=manufacturer_enrichment,
        extracted_gallery_count=extracted_gallery_count,
        downloaded_gallery=downloaded_gallery,
        gallery_warnings=gallery_warnings,
        gallery_files=gallery_files,
        selected_presentation_blocks=selected_presentation_blocks,
        section_warnings=section_warnings,
        section_image_candidates=section_image_candidates,
        section_image_urls_resolved=section_image_urls_resolved,
        section_extraction_window=section_extraction_window,
        selected_besco_images=selected_besco_images,
        downloaded_besco=downloaded_besco,
        besco_warnings=besco_warnings,
        besco_files=besco_files,
        besco_filenames_by_section=besco_filenames_by_section,
        final_source=final_source,
        final_scope_ok=final_scope_ok,
        final_scope_reason=final_scope_reason,
        scrape_persistence_input=scrape_persistence_input,
        sections_artifact_payload=sections_artifact_payload,
    )

    scrape_persistence_input.source_payload = source_payload
    scrape_persistence_input.normalized_payload = result_assembly.normalized
    scrape_persistence_input.report_payload = result_assembly.report
    scrape_persistence_input.bescos_raw_payload = sections_artifact_payload
    scrape_persistence = persist_prepare_scrape_artifacts_fn(scrape_persistence_input)

    return {
        "cli": cli,
        "source": source,
        "fetch": fetch,
        "parsed": parsed,
        "taxonomy": taxonomy,
        "taxonomy_candidates": taxonomy_candidates,
        "schema_match": result_assembly.schema_match,
        "schema_candidates": result_assembly.schema_candidates,
        "manufacturer_enrichment": manufacturer_enrichment,
        "row": result_assembly.row,
        "normalized": result_assembly.normalized,
        "report": result_assembly.report,
        "model_dir": resolved_model_dir,
        "raw_html_path": scrape_persistence.raw_html_path,
        "source_json_path": scrape_persistence.source_json_path,
        "normalized_json_path": scrape_persistence.normalized_json_path,
        "report_json_path": scrape_persistence.report_json_path,
        "selected_presentation_blocks": selected_presentation_blocks,
        "downloaded_gallery": downloaded_gallery,
        "downloaded_besco": downloaded_besco,
        "besco_filenames_by_section": besco_filenames_by_section,
    }
