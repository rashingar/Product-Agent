from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..csv_writer import write_csv_row
from ..llm_contract import validate_llm_output
from ..mapping import build_row
from ..models import CLIInput, GalleryImage, ParsedProduct, SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from ..repo_paths import REPO_ROOT
from ..utils import ensure_directory, read_json, utcnow_iso, write_json, write_text
from ..validator import validate_candidate_csv, write_validation_report
from .metadata import maybe_write_run_metadata
from .models import RunArtifacts, RunStatus, RunType

WORK_ROOT = REPO_ROOT / "work"
PRODUCTS_ROOT = REPO_ROOT / "products"


def execute_render_workflow(
    model: str,
    *,
    work_root: Path = WORK_ROOT,
    products_root: Path = PRODUCTS_ROOT,
) -> dict[str, Any]:
    model_root = work_root / model
    scrape_dir = model_root / "scrape"
    source_json = scrape_dir / f"{model}.source.json"
    normalized_json = scrape_dir / f"{model}.normalized.json"
    llm_output_json = model_root / "llm_output.json"
    candidate_dir = model_root / "candidate"
    candidate_csv_path = candidate_dir / f"{model}.csv"
    published_csv_path = products_root / f"{model}.csv"
    description_path = candidate_dir / "description.html"
    characteristics_path = candidate_dir / "characteristics.html"
    normalized_candidate_path = candidate_dir / f"{model}.normalized.json"
    validation_report_path = candidate_dir / f"{model}.validation.json"
    requested_at = utcnow_iso()
    started_at = requested_at
    try:
        if not source_json.exists() or not normalized_json.exists():
            raise FileNotFoundError(f"Missing scrape artifacts in {scrape_dir}")
        if not llm_output_json.exists():
            raise FileNotFoundError(f"Missing LLM output: {llm_output_json}")

        source = load_source_product(source_json)
        normalized = read_json(normalized_json)
        input_data = normalized.get("input", {})
        cli = CLIInput(
            model=str(input_data.get("model", model)),
            url=str(input_data.get("url", "")),
            photos=int(input_data.get("photos", 1)),
            sections=int(input_data.get("sections", 0)),
            skroutz_status=int(input_data.get("skroutz_status", 0)),
            boxnow=int(input_data.get("boxnow", 0)),
            price=input_data.get("price", 0),
            out=str(model_root / "candidate"),
        )
        taxonomy = TaxonomyResolution(**normalized.get("taxonomy", {}))
        schema_match = SchemaMatchResult(**normalized.get("schema_match", {}))
        parsed = ParsedProduct(source=source)

        llm_payload = read_json(llm_output_json)
        normalized_llm, llm_errors = validate_llm_output(llm_payload, cli.sections)

        candidate_dir = ensure_directory(model_root / "candidate")

        besco_filenames_by_section = {
            image.position: image.local_filename
            for image in source.besco_images
            if image.local_filename
        }
        row, candidate_normalized, mapping_warnings = build_row(
            cli=cli,
            parsed=parsed,
            taxonomy=taxonomy,
            schema_match=schema_match,
            downloaded_image_count=len(source.gallery_images),
            besco_filenames_by_section=besco_filenames_by_section,
            llm_product=normalized_llm.get("product", {}),
            llm_presentation=normalized_llm.get("presentation", {}),
        )
        headers, ordered_row = write_csv_row(row, candidate_csv_path)
        candidate_normalized["csv_headers"] = headers
        candidate_normalized["csv_ordered_row"] = ordered_row
        candidate_normalized["mapping_warnings"] = mapping_warnings
        write_json(normalized_candidate_path, candidate_normalized)
        write_text(description_path, row["description"])
        write_text(characteristics_path, row["characteristics"])

        baseline_path = products_root / f"{model}.csv"
        validation_report = validate_candidate_csv(
            csv_path=candidate_csv_path,
            baseline_path=baseline_path if baseline_path.exists() else None,
            llm_errors=llm_errors,
        )
        if mapping_warnings:
            validation_report["warnings"].extend(mapping_warnings)
        validation_ok = bool(validation_report.get("ok", False))
        if not validation_ok:
            validation_report["warnings"].append(
                "Candidate failed validation; skipping publish to products/."
            )
        write_validation_report(validation_report, validation_report_path)

        published_csv_result_path: Path | None = None
        if validation_ok:
            ensure_directory(products_root)
            shutil.copyfile(candidate_csv_path, published_csv_path)
            published_csv_result_path = published_csv_path
        run_status = RunStatus.COMPLETED if validation_ok else RunStatus.FAILED
        finished_at = utcnow_iso()
        metadata_path = maybe_write_run_metadata(
            model=model,
            run_type=RunType.RENDER,
            status=run_status,
            model_root=model_root,
            artifacts=RunArtifacts(
                model_root=model_root,
                scrape_dir=scrape_dir,
                candidate_dir=candidate_dir,
                source_json_path=source_json,
                scrape_normalized_json_path=normalized_json,
                llm_output_path=llm_output_json,
                candidate_csv_path=candidate_csv_path,
                published_csv_path=published_csv_result_path,
                candidate_normalized_json_path=normalized_candidate_path,
                validation_report_path=validation_report_path,
                description_html_path=description_path,
                characteristics_html_path=characteristics_path,
            ),
            requested_at=requested_at,
            started_at=started_at,
            finished_at=finished_at,
            warnings=list(validation_report.get("warnings", [])),
            details={
                "validation_ok": validation_ok,
                "published": validation_ok,
            },
        )

        return {
            "candidate_dir": candidate_dir,
            "candidate_csv_path": candidate_csv_path,
            "published_csv_path": published_csv_result_path,
            "description_path": description_path,
            "characteristics_path": characteristics_path,
            "validation_report_path": validation_report_path,
            "run_status": run_status.value,
            "metadata_path": metadata_path,
            "validation_report": validation_report,
        }
    except Exception as exc:
        finished_at = utcnow_iso()
        if model_root.exists():
            maybe_write_run_metadata(
                model=model,
                run_type=RunType.RENDER,
                status=RunStatus.FAILED,
                model_root=model_root,
                artifacts=RunArtifacts(
                    model_root=model_root,
                    scrape_dir=scrape_dir,
                    candidate_dir=candidate_dir,
                    source_json_path=source_json,
                    scrape_normalized_json_path=normalized_json,
                    llm_output_path=llm_output_json,
                    candidate_csv_path=candidate_csv_path,
                    published_csv_path=published_csv_path,
                    candidate_normalized_json_path=normalized_candidate_path,
                    validation_report_path=validation_report_path,
                    description_html_path=description_path,
                    characteristics_html_path=characteristics_path,
                ),
                requested_at=requested_at,
                started_at=started_at,
                finished_at=finished_at,
                error_code=type(exc).__name__,
                error_detail=str(exc),
            )
        raise


def load_source_product(path: str | Path) -> SourceProductData:
    payload = read_json(path)
    return SourceProductData(
        source_name=payload.get("source_name", ""),
        page_type=payload.get("page_type", "product"),
        url=payload.get("url", ""),
        canonical_url=payload.get("canonical_url", ""),
        breadcrumbs=list(payload.get("breadcrumbs", [])),
        skroutz_family=payload.get("skroutz_family", ""),
        category_tag_text=payload.get("category_tag_text", ""),
        category_tag_href=payload.get("category_tag_href", ""),
        category_tag_slug=payload.get("category_tag_slug", ""),
        taxonomy_source_category=payload.get("taxonomy_source_category", ""),
        taxonomy_match_type=payload.get("taxonomy_match_type", ""),
        taxonomy_rule_id=payload.get("taxonomy_rule_id", ""),
        taxonomy_ambiguity=bool(payload.get("taxonomy_ambiguity", False)),
        taxonomy_escalation_reason=payload.get("taxonomy_escalation_reason", ""),
        taxonomy_tv_inches=payload.get("taxonomy_tv_inches"),
        product_code=payload.get("product_code", ""),
        brand=payload.get("brand", ""),
        name=payload.get("name", ""),
        hero_summary=payload.get("hero_summary", ""),
        price_text=payload.get("price_text", ""),
        price_value=payload.get("price_value"),
        installments_text=payload.get("installments_text", ""),
        delivery_text=payload.get("delivery_text", ""),
        pickup_text=payload.get("pickup_text", ""),
        gallery_images=[GalleryImage(**item) for item in payload.get("gallery_images", [])],
        besco_images=[GalleryImage(**item) for item in payload.get("besco_images", [])],
        energy_label_asset_url=payload.get("energy_label_asset_url", ""),
        product_sheet_asset_url=payload.get("product_sheet_asset_url", ""),
        key_specs=[SpecItem(**item) for item in payload.get("key_specs", [])],
        spec_sections=[
            SpecSection(
                section=section.get("section", ""),
                items=[SpecItem(**item) for item in section.get("items", [])],
            )
            for section in payload.get("spec_sections", [])
        ],
        manufacturer_spec_sections=[
            SpecSection(
                section=section.get("section", ""),
                items=[SpecItem(**item) for item in section.get("items", [])],
            )
            for section in payload.get("manufacturer_spec_sections", [])
        ],
        manufacturer_source_text=payload.get("manufacturer_source_text", ""),
        manufacturer_documents=list(payload.get("manufacturer_documents", [])),
        presentation_source_html=payload.get("presentation_source_html", ""),
        presentation_source_text=payload.get("presentation_source_text", ""),
        raw_html_path=payload.get("raw_html_path", ""),
        scraped_at=payload.get("scraped_at", ""),
        fallback_used=bool(payload.get("fallback_used", False)),
        mpn=payload.get("mpn", ""),
    )
