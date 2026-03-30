from __future__ import annotations

from pathlib import Path

from .errors import ServiceError
from .render_execution import execute_render_workflow
from .models import RenderRequest, RunArtifacts, RunMetadata, RunStatus, RunType, ServiceResult


def render_product(request: RenderRequest) -> ServiceResult:
    try:
        result = execute_render_workflow(request.model)
    except Exception as exc:
        raise ServiceError(type(exc).__name__, str(exc), cause=exc) from exc

    candidate_dir = Path(result["candidate_dir"])
    model_root = candidate_dir.parent
    scrape_dir = model_root / "scrape"
    validation_report = result["validation_report"]
    return ServiceResult(
        run=RunMetadata(
            model=request.model,
            run_type=RunType.RENDER,
            status=RunStatus(result["run_status"]),
            warnings=list(validation_report.get("warnings", [])),
        ),
        artifacts=RunArtifacts(
            model_root=model_root,
            scrape_dir=scrape_dir,
            candidate_dir=candidate_dir,
            source_json_path=scrape_dir / f"{request.model}.source.json",
            scrape_normalized_json_path=scrape_dir / f"{request.model}.normalized.json",
            llm_output_path=model_root / "llm_output.json",
            candidate_csv_path=Path(result["candidate_csv_path"]),
            published_csv_path=Path(result["published_csv_path"]),
            candidate_normalized_json_path=candidate_dir / f"{request.model}.normalized.json",
            validation_report_path=Path(result["validation_report_path"]),
            description_html_path=Path(result["description_path"]),
            characteristics_html_path=Path(result["characteristics_path"]),
            metadata_path=Path(result["metadata_path"]),
        ),
        details={
            "validation_ok": bool(validation_report.get("ok", False)),
        },
    )

