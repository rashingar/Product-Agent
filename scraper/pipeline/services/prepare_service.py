from __future__ import annotations

from ..models import CLIInput
from .errors import service_error_from_exception
from .prepare_execution import WORK_ROOT, execute_prepare_workflow
from .models import PrepareRequest, RunArtifacts, RunMetadata, RunStatus, RunType, ServiceResult


def prepare_product(request: PrepareRequest) -> ServiceResult:
    cli = CLIInput(
        model=request.model,
        url=request.url,
        photos=request.photos,
        sections=request.sections,
        skroutz_status=request.skroutz_status,
        boxnow=request.boxnow,
        price=request.price,
        out=str(WORK_ROOT / request.model / "scrape"),
    )
    try:
        result = execute_prepare_workflow(cli, work_root=WORK_ROOT)
    except Exception as exc:
        raise service_error_from_exception(exc, operation="prepare") from exc

    scrape_result = result.scrape_result
    parsed = scrape_result.parsed
    taxonomy = scrape_result.taxonomy
    schema_match = scrape_result.schema_match
    model_root = result.model_root
    scrape_dir = result.scrape_dir
    metadata_path = result.metadata_path
    warnings = list(scrape_result.report_warnings)
    return ServiceResult(
        run=RunMetadata(
            model=request.model,
            run_type=RunType.PREPARE,
            status=result.run_status,
            warnings=warnings,
        ),
        artifacts=RunArtifacts(
            model_root=model_root,
            scrape_dir=scrape_dir,
            llm_dir=result.llm_dir,
            raw_html_path=scrape_dir / f"{request.model}.raw.html",
            source_json_path=scrape_dir / f"{request.model}.source.json",
            scrape_normalized_json_path=scrape_dir / f"{request.model}.normalized.json",
            source_report_json_path=scrape_dir / f"{request.model}.report.json",
            llm_task_manifest_path=result.task_manifest_path,
            intro_text_context_path=result.intro_text_context_path,
            intro_text_prompt_path=result.intro_text_prompt_path,
            intro_text_output_path=result.intro_text_output_path,
            seo_meta_context_path=result.seo_meta_context_path,
            seo_meta_prompt_path=result.seo_meta_prompt_path,
            seo_meta_output_path=result.seo_meta_output_path,
            metadata_path=metadata_path,
        ),
        details={
            "source": scrape_result.source,
            "product_name": str(getattr(getattr(parsed, "source", None), "name", "") or ""),
            "product_code": str(getattr(getattr(parsed, "source", None), "product_code", "") or ""),
            "brand": str(getattr(getattr(parsed, "source", None), "brand", "") or ""),
            "taxonomy_path": str(getattr(taxonomy, "taxonomy_path", "") or ""),
            "matched_schema_id": str(getattr(schema_match, "matched_schema_id", "") or ""),
            "schema_score": float(getattr(schema_match, "score", 0.0) or 0.0),
            "warnings_count": len(warnings),
            "llm_prepare_mode": "split_tasks",
        },
    )
