from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from .csv_writer import write_csv_row
from .full_run import execute_full_run
from .input_validation import FAIL_MESSAGE, validate_input
from .llm_contract import build_llm_context, render_prompt, validate_llm_output
from .mapping import build_row
from .models import CLIInput, GalleryImage, ParsedProduct, SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from .repo_paths import MASTER_PROMPT_PATH, REPO_ROOT
from .services.errors import ServiceError
from .services.metadata import maybe_write_run_metadata
from .services.models import PrepareRequest, RenderRequest, RunArtifacts, RunStatus, RunType
from .services.prepare_service import prepare_product
from .services.render_service import render_product
from .utils import ensure_directory, read_json, utcnow_iso, write_json, write_text
from .validator import validate_candidate_csv, write_validation_report

WORK_ROOT = REPO_ROOT / "work"
PRODUCTS_ROOT = REPO_ROOT / "products"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    add_template_options(prepare_parser)
    add_input_fields(prepare_parser)

    render_parser = subparsers.add_parser("render")
    add_template_options(render_parser)
    render_parser.add_argument("--model", default=None)

    return parser


def add_template_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--template-file", default=None)
    parser.add_argument("--stdin", action="store_true")


def add_input_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=None)
    parser.add_argument("--url", default=None)
    parser.add_argument("--photos", type=int, default=None)
    parser.add_argument("--sections", type=int, default=None)
    parser.add_argument("--skroutz-status", type=int, default=None, dest="skroutz_status")
    parser.add_argument("--boxnow", type=int, default=None)
    parser.add_argument("--price", default=None)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            cli = build_cli_input_from_args(args)
            result = prepare_product(
                PrepareRequest(
                    model=cli.model,
                    url=cli.url,
                    photos=cli.photos,
                    sections=cli.sections,
                    skroutz_status=cli.skroutz_status,
                    boxnow=cli.boxnow,
                    price=cli.price,
                )
            )
            print(f"Scrape artifacts: {result.artifacts.scrape_dir}")
            print(f"LLM context: {result.artifacts.llm_context_path}")
            print(f"Prompt: {result.artifacts.prompt_path}")
            print(f"Run status: {result.run.status.value}")
            print(f"Metadata path: {result.artifacts.metadata_path}")
            return 0

        model = resolve_model_for_render(args)
        result = render_product(RenderRequest(model=model))
        print(f"Candidate CSV: {result.artifacts.candidate_csv_path}")
        print(f"Validation report: {result.artifacts.validation_report_path}")
        print(f"Validation ok: {bool(result.details.get('validation_ok', False))}")
        print(f"Run status: {result.run.status.value}")
        print(f"Metadata path: {result.artifacts.metadata_path}")
        return 0 if bool(result.details.get("validation_ok", False)) else 5
    except ValueError as exc:
        message = str(exc)
        print(message)
        return 1 if message == FAIL_MESSAGE else 2
    except ServiceError as exc:
        print(exc.message, file=sys.stderr)
        return 3 if exc.code == "FileNotFoundError" else 4


def build_cli_input_from_args(args: argparse.Namespace) -> CLIInput:
    template_values = read_template_values(args.template_file, args.stdin)
    merged = {
        "model": template_values.get("model", ""),
        "url": template_values.get("url", ""),
        "photos": template_values.get("photos", "1"),
        "sections": template_values.get("sections", "0"),
        "skroutz_status": template_values.get("skroutz_status", "0"),
        "boxnow": template_values.get("boxnow", "0"),
        "price": template_values.get("price", "0"),
    }
    for key in ["model", "url", "photos", "sections", "skroutz_status", "boxnow", "price"]:
        value = getattr(args, key, None)
        if value is not None:
            merged[key] = value
    namespace = argparse.Namespace(
        model=merged["model"],
        url=merged["url"],
        photos=merged["photos"],
        sections=merged["sections"],
        skroutz_status=merged["skroutz_status"],
        boxnow=merged["boxnow"],
        price=merged["price"],
        out=str(WORK_ROOT),
    )
    cli = validate_input(namespace)
    return CLIInput(
        model=cli.model,
        url=cli.url,
        photos=cli.photos,
        sections=cli.sections,
        skroutz_status=cli.skroutz_status,
        boxnow=cli.boxnow,
        price=cli.price,
        out=str(WORK_ROOT / cli.model / "scrape"),
    )


def read_template_values(template_file: str | None, use_stdin: bool) -> dict[str, str]:
    if template_file:
        text = Path(template_file).read_text(encoding="utf-8")
        return parse_template_text(text)
    if use_stdin:
        text = sys.stdin.read()
        return parse_template_text(text)
    return {}


def parse_template_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized_key in {"model", "url", "photos", "sections", "skroutz_status", "boxnow", "price"}:
            values[normalized_key] = value.strip()
    return values


def replace_path_prefix(value: str, old_prefix: str, new_prefix: str) -> str:
    if value.startswith(old_prefix):
        return f"{new_prefix}{value[len(old_prefix):]}"
    return value


def rewrite_path_prefixes(payload: Any, old_prefix: str, new_prefix: str) -> Any:
    if isinstance(payload, dict):
        return {key: rewrite_path_prefixes(value, old_prefix, new_prefix) for key, value in payload.items()}
    if isinstance(payload, list):
        return [rewrite_path_prefixes(value, old_prefix, new_prefix) for value in payload]
    if isinstance(payload, str):
        return replace_path_prefix(payload, old_prefix, new_prefix)
    return payload


def normalize_scrape_result_paths(result: dict[str, Any], old_root: Path, new_root: Path, model: str) -> None:
    old_prefix = str(old_root)
    new_prefix = str(new_root)
    for key in ["normalized", "report"]:
        if key in result:
            result[key] = rewrite_path_prefixes(result[key], old_prefix, new_prefix)

    parsed = result.get("parsed")
    if parsed is not None:
        parsed.source.raw_html_path = replace_path_prefix(parsed.source.raw_html_path, old_prefix, new_prefix)
        for image in [*parsed.source.gallery_images, *parsed.source.besco_images]:
            image.local_path = replace_path_prefix(image.local_path, old_prefix, new_prefix)

    path_keys = {
        "model_dir": new_root,
        "raw_html_path": new_root / f"{model}.raw.html",
        "source_json_path": new_root / f"{model}.source.json",
        "normalized_json_path": new_root / f"{model}.normalized.json",
        "report_json_path": new_root / f"{model}.report.json",
        "csv_path": new_root / f"{model}.csv",
    }
    result.update(path_keys)

    for artifact_name in [f"{model}.source.json", f"{model}.normalized.json", f"{model}.report.json"]:
        artifact_path = new_root / artifact_name
        if artifact_path.exists():
            payload = read_json(artifact_path)
            write_json(artifact_path, rewrite_path_prefixes(payload, old_prefix, new_prefix))


def _path_or_none(value: str | Path | None) -> Path | None:
    if value in (None, ""):
        return None
    return Path(value)


def prepare_workflow(cli: CLIInput) -> dict[str, Any]:
    requested_at = utcnow_iso()
    started_at = requested_at
    model_root = ensure_directory(WORK_ROOT / cli.model)
    scrape_dir = ensure_directory(model_root / "scrape")
    llm_context_path = model_root / "llm_context.json"
    prompt_path = model_root / "prompt.txt"
    llm_output_path = model_root / "llm_output.json"
    scrape_cli = CLIInput(**{**cli.to_dict(), "out": str(scrape_dir)})
    try:
        result = execute_full_run(scrape_cli)
        generated_scrape_dir = Path(result.get("model_dir", scrape_dir))
        if generated_scrape_dir != scrape_dir:
            staged_items = list(generated_scrape_dir.iterdir())
            for item in list(scrape_dir.iterdir()):
                if item == generated_scrape_dir:
                    continue
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            for item in staged_items:
                target = scrape_dir / item.name
                if target.exists():
                    if target.is_file():
                        target.unlink()
                    else:
                        shutil.rmtree(target)
                shutil.move(str(item), str(target))
            if generated_scrape_dir.exists():
                generated_scrape_dir.rmdir()
            normalize_scrape_result_paths(result, generated_scrape_dir, scrape_dir, cli.model)
        deterministic_product = result["normalized"].get("deterministic_product", {})
        llm_context = build_llm_context(
            cli=scrape_cli,
            parsed=result["parsed"],
            taxonomy=result["taxonomy"],
            schema_match=result["schema_match"],
            deterministic_product=deterministic_product,
        )
        prompt_template = MASTER_PROMPT_PATH.read_text(encoding="utf-8")
        prompt_text = render_prompt(prompt_template, llm_context)
        write_json(llm_context_path, llm_context)
        write_text(prompt_path, prompt_text)
        finished_at = utcnow_iso()
        metadata_path = maybe_write_run_metadata(
            model=cli.model,
            run_type=RunType.PREPARE,
            status=RunStatus.COMPLETED,
            model_root=model_root,
            artifacts=RunArtifacts(
                model_root=model_root,
                scrape_dir=scrape_dir,
                raw_html_path=_path_or_none(result.get("raw_html_path")),
                source_json_path=_path_or_none(result.get("source_json_path")),
                scrape_normalized_json_path=_path_or_none(result.get("normalized_json_path")),
                source_report_json_path=_path_or_none(result.get("report_json_path")),
                llm_context_path=llm_context_path,
                prompt_path=prompt_path,
                llm_output_path=llm_output_path,
            ),
            requested_at=requested_at,
            started_at=started_at,
            finished_at=finished_at,
            warnings=list(result.get("report", {}).get("warnings", [])),
            details={"source": str(result.get("source", ""))},
        )
        return {
            "model_root": model_root,
            "scrape_dir": scrape_dir,
            "llm_context_path": llm_context_path,
            "prompt_path": prompt_path,
            "run_status": RunStatus.COMPLETED.value,
            "metadata_path": metadata_path,
            "scrape_result": result,
        }
    except Exception as exc:
        finished_at = utcnow_iso()
        maybe_write_run_metadata(
            model=cli.model,
            run_type=RunType.PREPARE,
            status=RunStatus.FAILED,
            model_root=model_root,
            artifacts=RunArtifacts(
                model_root=model_root,
                scrape_dir=scrape_dir,
                raw_html_path=scrape_dir / f"{cli.model}.raw.html",
                source_json_path=scrape_dir / f"{cli.model}.source.json",
                scrape_normalized_json_path=scrape_dir / f"{cli.model}.normalized.json",
                source_report_json_path=scrape_dir / f"{cli.model}.report.json",
                llm_context_path=llm_context_path,
                prompt_path=prompt_path,
                llm_output_path=llm_output_path,
            ),
            requested_at=requested_at,
            started_at=started_at,
            finished_at=finished_at,
            error_code=type(exc).__name__,
            error_detail=str(exc),
        )
        raise


def resolve_model_for_render(args: argparse.Namespace) -> str:
    values = read_template_values(args.template_file, args.stdin)
    model = str(args.model or values.get("model", "")).strip()
    if not model:
        raise ValueError(FAIL_MESSAGE)
    if not model.isdigit() or len(model) != 6:
        raise ValueError(FAIL_MESSAGE)
    return model


def render_workflow(model: str) -> dict[str, Any]:
    model_root = WORK_ROOT / model
    scrape_dir = model_root / "scrape"
    source_json = scrape_dir / f"{model}.source.json"
    normalized_json = scrape_dir / f"{model}.normalized.json"
    llm_output_json = model_root / "llm_output.json"
    candidate_dir = model_root / "candidate"
    candidate_csv_path = candidate_dir / f"{model}.csv"
    published_csv_path = PRODUCTS_ROOT / f"{model}.csv"
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

        baseline_path = PRODUCTS_ROOT / f"{model}.csv"
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
            ensure_directory(PRODUCTS_ROOT)
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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
