from __future__ import annotations

from .errors import ServiceErrorCode, service_error_from_exception
from .render_execution import execute_render_workflow
from .models import RenderRequest, RunArtifacts, RunMetadata, RunType, ServiceResult


def render_product(request: RenderRequest) -> ServiceResult:
    try:
        result = execute_render_workflow(request.model)
    except Exception as exc:
        raise service_error_from_exception(exc, operation="render") from exc

    candidate_dir = result.candidate_dir
    model_root = result.model_root
    scrape_dir = result.scrape_dir
    validation_report = result.validation_report
    validation_ok = validation_report.ok
    run_warnings = list(validation_report.warnings)
    error_code = None if validation_ok else ServiceErrorCode.VALIDATION_FAILURE.value
    error_detail = None if validation_ok else "Candidate validation failed"
    return ServiceResult(
        run=RunMetadata(
            model=request.model,
            run_type=RunType.RENDER,
            status=result.run_status,
            warnings=run_warnings,
            error_code=error_code,
            error_detail=error_detail,
        ),
        artifacts=RunArtifacts(
            model_root=model_root,
            scrape_dir=scrape_dir,
            candidate_dir=candidate_dir,
            llm_dir=result.llm_dir,
            source_json_path=scrape_dir / f"{request.model}.source.json",
            scrape_normalized_json_path=scrape_dir / f"{request.model}.normalized.json",
            llm_task_manifest_path=result.llm_dir / "task_manifest.json",
            intro_text_output_path=result.llm_dir / "intro_text.output.txt",
            seo_meta_output_path=result.llm_dir / "seo_meta.output.json",
            candidate_csv_path=result.candidate_csv_path,
            published_csv_path=result.published_csv_path,
            candidate_normalized_json_path=candidate_dir / f"{request.model}.normalized.json",
            validation_report_path=result.validation_report_path,
            description_html_path=result.description_path,
            characteristics_html_path=result.characteristics_path,
            metadata_path=result.metadata_path,
        ),
        details={
            "validation_ok": validation_ok,
            "published": result.published_csv_path is not None,
        },
    )

