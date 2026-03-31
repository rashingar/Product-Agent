from __future__ import annotations

from .models import FullRunRequest, PrepareRequest, PublishRequest, RenderRequest, RunArtifacts, RunMetadata, RunType, ServiceResult
from .prepare_service import prepare_product
from .publish_service import build_publish_phase_details, publish_product
from .render_service import render_product


def execute_run_workflow(request: FullRunRequest) -> ServiceResult:
    prepare_result = prepare_product(
        PrepareRequest(
            model=request.model,
            url=request.url,
            photos=request.photos,
            sections=request.sections,
            skroutz_status=request.skroutz_status,
            boxnow=request.boxnow,
            price=request.price,
        )
    )
    render_result = render_product(RenderRequest(model=request.model))
    publish_result = (
        publish_product(
            PublishRequest(
                model=request.model,
                current_job_product_file=render_result.artifacts.published_csv_path,
            )
        )
        if render_result.artifacts.published_csv_path is not None
        else None
    )
    publish_details = build_publish_phase_details(request.model, publish_result)

    return ServiceResult(
        run=RunMetadata(
            model=request.model,
            run_type=RunType.FULL,
            status=render_result.run.status,
            warnings=[
                *prepare_result.run.warnings,
                *render_result.run.warnings,
                *(publish_result.run.warnings if publish_result is not None else []),
            ],
            error_code=render_result.run.error_code or prepare_result.run.error_code,
            error_detail=render_result.run.error_detail or prepare_result.run.error_detail,
        ),
        artifacts=RunArtifacts(
            model_root=prepare_result.artifacts.model_root or render_result.artifacts.model_root,
            scrape_dir=prepare_result.artifacts.scrape_dir or render_result.artifacts.scrape_dir,
            llm_dir=prepare_result.artifacts.llm_dir,
            candidate_dir=render_result.artifacts.candidate_dir,
            raw_html_path=prepare_result.artifacts.raw_html_path,
            source_json_path=prepare_result.artifacts.source_json_path or render_result.artifacts.source_json_path,
            scrape_normalized_json_path=prepare_result.artifacts.scrape_normalized_json_path
            or render_result.artifacts.scrape_normalized_json_path,
            source_report_json_path=prepare_result.artifacts.source_report_json_path,
            llm_task_manifest_path=prepare_result.artifacts.llm_task_manifest_path,
            intro_text_context_path=prepare_result.artifacts.intro_text_context_path,
            intro_text_prompt_path=prepare_result.artifacts.intro_text_prompt_path,
            intro_text_output_path=prepare_result.artifacts.intro_text_output_path,
            seo_meta_context_path=prepare_result.artifacts.seo_meta_context_path,
            seo_meta_prompt_path=prepare_result.artifacts.seo_meta_prompt_path,
            seo_meta_output_path=prepare_result.artifacts.seo_meta_output_path,
            candidate_csv_path=render_result.artifacts.candidate_csv_path,
            published_csv_path=render_result.artifacts.published_csv_path,
            candidate_normalized_json_path=render_result.artifacts.candidate_normalized_json_path,
            validation_report_path=render_result.artifacts.validation_report_path,
            description_html_path=render_result.artifacts.description_html_path,
            characteristics_html_path=render_result.artifacts.characteristics_html_path,
        ),
        details={
            "prepare_status": prepare_result.run.status.value,
            "prepare_metadata_path": str(prepare_result.artifacts.metadata_path) if prepare_result.artifacts.metadata_path else None,
            "render_status": render_result.run.status.value,
            "render_metadata_path": str(render_result.artifacts.metadata_path) if render_result.artifacts.metadata_path else None,
            "validation_ok": bool(render_result.details.get("validation_ok", False)),
            "published": bool(render_result.details.get("published", False)),
            "source": str(prepare_result.details.get("source", "")),
            "product_name": str(prepare_result.details.get("product_name", "")),
            "product_code": str(prepare_result.details.get("product_code", "")),
            "brand": str(prepare_result.details.get("brand", "")),
            "taxonomy_path": str(prepare_result.details.get("taxonomy_path", "")),
            "matched_schema_id": str(prepare_result.details.get("matched_schema_id", "")),
            "schema_score": float(prepare_result.details.get("schema_score", 0.0) or 0.0),
            "publish_attempted": bool(publish_details.get("publish_attempted", False)),
            "publish_status": str(publish_details.get("publish_status", "not_attempted")),
            "publish_stage": str(publish_details.get("publish_stage", "-")),
            "publish_message": str(publish_details["publish_message"]) if publish_details.get("publish_message") is not None else None,
            "upload_report_path": str(publish_details["upload_report_path"]) if publish_details.get("upload_report_path") is not None else None,
            "import_report_path": str(publish_details["import_report_path"]) if publish_details.get("import_report_path") is not None else None,
            "publish_metadata_path": str(publish_details["publish_metadata_path"]) if publish_details.get("publish_metadata_path") is not None else None,
            "warnings_count": len(prepare_result.run.warnings)
            + len(render_result.run.warnings)
            + (len(publish_result.run.warnings) if publish_result is not None else 0),
        },
    )
