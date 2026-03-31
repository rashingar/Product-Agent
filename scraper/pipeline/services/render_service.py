from __future__ import annotations

from pathlib import Path

from .errors import ServiceErrorCode, service_error_from_exception
from .render_execution import execute_render_workflow
from .models import RenderRequest, RunArtifacts, RunMetadata, RunStatus, RunType, ServiceResult


def _path_or_none(value) -> Path | None:
    if value in (None, ""):
        return None
    return Path(value)


def render_product(request: RenderRequest) -> ServiceResult:
    try:
        result = execute_render_workflow(request.model)
    except Exception as exc:
        raise service_error_from_exception(exc, operation="render") from exc

    candidate_dir = Path(result["candidate_dir"])
    model_root = candidate_dir.parent
    scrape_dir = model_root / "scrape"
    validation_report = result["validation_report"]
    validation_ok = bool(validation_report.get("ok", False))
    run_warnings = list(validation_report.get("warnings", []))
    upload_warning_value = result.get("upload_warning")
    upload_warning = str(upload_warning_value) if upload_warning_value else None
    if upload_warning:
        run_warnings.append(upload_warning)
    error_code = None if validation_ok else ServiceErrorCode.VALIDATION_FAILURE.value
    error_detail = None if validation_ok else "Candidate validation failed"
    return ServiceResult(
        run=RunMetadata(
            model=request.model,
            run_type=RunType.RENDER,
            status=RunStatus(result["run_status"]),
            warnings=run_warnings,
            error_code=error_code,
            error_detail=error_detail,
        ),
        artifacts=RunArtifacts(
            model_root=model_root,
            scrape_dir=scrape_dir,
            candidate_dir=candidate_dir,
            llm_dir=model_root / "llm",
            source_json_path=scrape_dir / f"{request.model}.source.json",
            scrape_normalized_json_path=scrape_dir / f"{request.model}.normalized.json",
            llm_task_manifest_path=model_root / "llm" / "task_manifest.json",
            intro_text_output_path=model_root / "llm" / "intro_text.output.txt",
            seo_meta_output_path=model_root / "llm" / "seo_meta.output.json",
            candidate_csv_path=Path(result["candidate_csv_path"]),
            published_csv_path=_path_or_none(result.get("published_csv_path")),
            candidate_normalized_json_path=candidate_dir / f"{request.model}.normalized.json",
            validation_report_path=Path(result["validation_report_path"]),
            description_html_path=Path(result["description_path"]),
            characteristics_html_path=Path(result["characteristics_path"]),
            metadata_path=Path(result["metadata_path"]),
        ),
        details={
            "validation_ok": validation_ok,
            "upload_attempted": bool(result.get("upload_attempted", False)),
            "upload_ok": result.get("upload_ok"),
            "upload_report_path": str(result["upload_report_path"]) if result.get("upload_report_path") else None,
            "upload_warning": upload_warning,
        },
    )

