from __future__ import annotations

import os
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Any

from ..csv_writer import write_csv_row
from ..html_builders import extract_presentation_blocks
from ..llm_contract import validate_intro_text_output, validate_seo_meta_output
from ..mapping import build_row
from ..models import CLIInput, GalleryImage, ParsedProduct, SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from ..presentation_sections import normalize_presentation_sections
from ..repo_paths import REPO_ROOT
from ..utils import ensure_directory, read_json, utcnow_iso, write_json, write_text
from ..validator import validate_candidate_csv, write_validation_report
from .errors import ServiceErrorCode, service_error_from_exception
from .metadata import maybe_write_run_metadata
from .models import RunArtifacts, RunStatus, RunType

WORK_ROOT = REPO_ROOT / "work"
PRODUCTS_ROOT = REPO_ROOT / "products"
OPENCART_UPLOAD_ENTRYPOINT = Path("tools") / "run_opencart_image_upload.sh"
OPENCART_UPLOAD_REPORT_NAME = "upload.opencart.json"


def _summarize_upload_output(stdout: str, stderr: str) -> str:
    lines = [line.strip() for line in [*stdout.splitlines(), *stderr.splitlines()] if line.strip()]
    if not lines:
        return ""
    return " | ".join(lines[-2:])


def _run_opencart_image_upload(*, repo_root: Path, model: str, current_job_product_file: Path) -> dict[str, Any]:
    script_path = repo_root / OPENCART_UPLOAD_ENTRYPOINT
    report_path = repo_root / "work" / model / OPENCART_UPLOAD_REPORT_NAME
    result: dict[str, Any] = {
        "upload_attempted": True,
        "upload_ok": False,
        "upload_report_path": report_path,
        "upload_warning": None,
    }

    if not script_path.exists():
        result["upload_warning"] = f"opencart_image_upload_failed: shell entrypoint not found at {script_path}"
        return result

    env = os.environ.copy()
    env["CURRENT_JOB_PRODUCT_FILE"] = str(current_job_product_file)
    env.setdefault("REPO_ROOT", str(repo_root))

    try:
        completed = subprocess.run(
            ["bash", str(script_path)],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        result["upload_warning"] = f"opencart_image_upload_failed: {exc}"
        return result
    except Exception as exc:
        result["upload_warning"] = f"opencart_image_upload_failed: {exc}"
        return result

    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)

    if completed.returncode != 0:
        summary = _summarize_upload_output(completed.stdout, completed.stderr)
        warning = f"opencart_image_upload_failed: exit={completed.returncode}"
        if summary:
            warning = f"{warning}: {summary}"
        result["upload_warning"] = warning
        return result

    result["upload_ok"] = True
    return result


def execute_render_workflow(
    model: str,
    *,
    work_root: Path = WORK_ROOT,
    products_root: Path = PRODUCTS_ROOT,
) -> dict[str, Any]:
    model_root = work_root / model
    scrape_dir = model_root / "scrape"
    llm_dir = model_root / "llm"
    source_json = scrape_dir / f"{model}.source.json"
    normalized_json = scrape_dir / f"{model}.normalized.json"
    task_manifest_json = llm_dir / "task_manifest.json"
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

        llm_inputs = _load_render_llm_inputs(
            model_root=model_root,
            llm_dir=llm_dir,
            task_manifest_path=task_manifest_json,
        )
        llm_product, llm_intro_text, llm_errors, llm_mode, llm_artifact_paths = _normalize_render_llm_inputs(llm_inputs)

        extracted_sections = extract_presentation_blocks(
            presentation_source_html=source.presentation_source_html,
            presentation_source_text=source.presentation_source_text,
            base_url=source.canonical_url or source.url,
        )
        render_sections, section_warnings = _resolve_render_sections(
            extracted_sections=extracted_sections,
            sections_requested=max(int(cli.sections), 0),
        )

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
            llm_product=llm_product,
            llm_intro_text=llm_intro_text,
            deterministic_presentation_sections=render_sections,
        )
        headers, ordered_row = write_csv_row(row, candidate_csv_path)
        candidate_normalized["csv_headers"] = headers
        candidate_normalized["csv_ordered_row"] = ordered_row
        candidate_normalized["mapping_warnings"] = mapping_warnings
        candidate_normalized["llm_mode"] = llm_mode
        candidate_normalized["llm_artifact_paths"] = {key: str(value) for key, value in llm_artifact_paths.items()}
        candidate_normalized["presentation_sections"] = render_sections
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
        if section_warnings:
            validation_report["warnings"].extend(section_warnings)
        validation_ok = bool(validation_report.get("ok", False))
        if not validation_ok:
            validation_report["warnings"].append(
                "Candidate failed validation; skipping publish to products/."
            )
        write_validation_report(validation_report, validation_report_path)

        published_csv_result_path: Path | None = None
        upload_attempted = False
        upload_ok: bool | None = None
        upload_report_path: Path | None = None
        upload_warning: str | None = None
        if validation_ok:
            ensure_directory(products_root)
            shutil.copyfile(candidate_csv_path, published_csv_path)
            published_csv_result_path = published_csv_path
            upload_result = _run_opencart_image_upload(
                repo_root=REPO_ROOT,
                model=model,
                current_job_product_file=published_csv_result_path,
            )
            upload_attempted = bool(upload_result.get("upload_attempted", False))
            upload_ok = bool(upload_result.get("upload_ok", False))
            upload_report_value = upload_result.get("upload_report_path")
            upload_report_path = Path(upload_report_value) if upload_report_value else None
            upload_warning_value = upload_result.get("upload_warning")
            upload_warning = str(upload_warning_value) if upload_warning_value else None
        run_status = RunStatus.COMPLETED if validation_ok else RunStatus.FAILED
        finished_at = utcnow_iso()
        run_warnings = list(validation_report.get("warnings", []))
        if upload_warning:
            run_warnings.append(upload_warning)
        metadata_path = maybe_write_run_metadata(
            model=model,
            run_type=RunType.RENDER,
            status=run_status,
            model_root=model_root,
            artifacts=RunArtifacts(
                model_root=model_root,
                scrape_dir=scrape_dir,
                llm_dir=llm_dir if llm_dir.exists() else None,
                candidate_dir=candidate_dir,
                source_json_path=source_json,
                scrape_normalized_json_path=normalized_json,
                llm_task_manifest_path=task_manifest_json if task_manifest_json.exists() else None,
                intro_text_output_path=llm_artifact_paths.get("intro_text_output_path"),
                seo_meta_output_path=llm_artifact_paths.get("seo_meta_output_path"),
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
            warnings=run_warnings,
            error_code=None if validation_ok else ServiceErrorCode.VALIDATION_FAILURE.value,
            error_detail=None if validation_ok else "Candidate validation failed",
            details={
                "validation_ok": validation_ok,
                "published": validation_ok,
                "llm_mode": llm_mode,
                "upload_attempted": upload_attempted,
                "upload_ok": upload_ok,
                "upload_report_path": str(upload_report_path) if upload_report_path else None,
                "upload_warning": upload_warning,
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
            "upload_attempted": upload_attempted,
            "upload_ok": upload_ok,
            "upload_report_path": upload_report_path,
            "upload_warning": upload_warning,
        }
    except Exception as exc:
        finished_at = utcnow_iso()
        if model_root.exists():
            service_error = service_error_from_exception(exc, operation="render")
            maybe_write_run_metadata(
                model=model,
                run_type=RunType.RENDER,
                status=RunStatus.FAILED,
                model_root=model_root,
                artifacts=RunArtifacts(
                    model_root=model_root,
                    scrape_dir=scrape_dir,
                    llm_dir=llm_dir if llm_dir.exists() else None,
                    candidate_dir=candidate_dir,
                    source_json_path=source_json,
                    scrape_normalized_json_path=normalized_json,
                    llm_task_manifest_path=task_manifest_json if task_manifest_json.exists() else None,
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
                error_code=service_error.code,
                error_detail=service_error.message,
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


def _load_render_llm_inputs(
    *,
    model_root: Path,
    llm_dir: Path,
    task_manifest_path: Path,
) -> dict[str, Any]:
    intro_text_output_path = llm_dir / "intro_text.output.txt"
    seo_meta_output_path = llm_dir / "seo_meta.output.json"
    manifest = read_json(task_manifest_path) if task_manifest_path.exists() else {}
    tasks = manifest.get("primary_outputs", {}).get("tasks", {}) if isinstance(manifest, dict) else {}
    if isinstance(tasks, dict):
        intro_text_output_path = Path(tasks.get("intro_text", {}).get("expected_output_path", intro_text_output_path))
        seo_meta_output_path = Path(tasks.get("seo_meta", {}).get("expected_output_path", seo_meta_output_path))

    if not intro_text_output_path.exists() or not seo_meta_output_path.exists():
        raise FileNotFoundError(f"Missing split-task LLM outputs in {llm_dir}")
    return {
        "mode": "split_tasks",
        "intro_text_output_path": intro_text_output_path,
        "seo_meta_output_path": seo_meta_output_path,
        "intro_text_payload": intro_text_output_path.read_text(encoding="utf-8"),
        "seo_meta_payload": read_json(seo_meta_output_path),
    }


def _normalize_render_llm_inputs(inputs: dict[str, Any]) -> tuple[dict[str, Any], str, list[str], str, dict[str, Path]]:
    intro_text, intro_errors = validate_intro_text_output(inputs.get("intro_text_payload", ""))
    normalized_seo, seo_errors = validate_seo_meta_output(inputs.get("seo_meta_payload", {}))
    return (
        normalized_seo.get("product", {}),
        intro_text,
        [*intro_errors, *seo_errors],
        "split_tasks",
        {
            "intro_text_output_path": Path(inputs["intro_text_output_path"]),
            "seo_meta_output_path": Path(inputs["seo_meta_output_path"]),
        },
    )


def _resolve_render_sections(
    *,
    extracted_sections: list[dict[str, Any]],
    sections_requested: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    if sections_requested <= 0:
        return [], []
    if not extracted_sections:
        raise ValueError("Missing presentation source sections for requested render sections")

    normalized_sections = normalize_presentation_sections(extracted_sections, sections_requested=sections_requested)
    usable_sections = [
        {
            "title": section.title,
            "body_text": section.body_text,
            "quality": section.quality,
            "reason": section.reason,
            "metrics": section.metrics.to_dict(),
            "source_index": section.source_index,
            "image_url": section.image_url,
        }
        for section in normalized_sections
        if section.quality == "usable"
    ]
    missing_count = sum(1 for section in normalized_sections if section.quality == "missing")
    weak_count = sum(1 for section in normalized_sections if section.quality == "weak")

    if not usable_sections:
        raise ValueError("No usable deterministic presentation sections for requested render sections")
    if missing_count > 1:
        raise ValueError(f"Too many missing deterministic presentation sections: {missing_count}")

    warnings: list[str] = []
    if weak_count > 0:
        warnings.append(f"presentation_sections_weak:{weak_count}")
    if missing_count == 1:
        warnings.append("presentation_sections_missing:1")
    if len(usable_sections) < sections_requested:
        warnings.append(f"requested_sections_reduced:{len(usable_sections)}")
    return usable_sections[:sections_requested], warnings
