from __future__ import annotations

from pathlib import Path

from ..models import CLIInput
from .errors import ServiceError
from .models import PrepareRequest, RunArtifacts, RunMetadata, RunStatus, RunType, ServiceResult


def prepare_product(request: PrepareRequest) -> ServiceResult:
    from .. import workflow

    cli = CLIInput(
        model=request.model,
        url=request.url,
        photos=request.photos,
        sections=request.sections,
        skroutz_status=request.skroutz_status,
        boxnow=request.boxnow,
        price=request.price,
        out=str(workflow.WORK_ROOT / request.model / "scrape"),
    )
    try:
        result = workflow.prepare_workflow(cli)
    except Exception as exc:
        raise ServiceError(type(exc).__name__, str(exc), cause=exc) from exc

    model_root = Path(result["model_root"])
    scrape_dir = Path(result["scrape_dir"])
    metadata_path = Path(result["metadata_path"])
    warnings = list(result.get("scrape_result", {}).get("report", {}).get("warnings", []))
    return ServiceResult(
        run=RunMetadata(
            model=request.model,
            run_type=RunType.PREPARE,
            status=RunStatus(result["run_status"]),
            warnings=warnings,
        ),
        artifacts=RunArtifacts(
            model_root=model_root,
            scrape_dir=scrape_dir,
            raw_html_path=scrape_dir / f"{request.model}.raw.html",
            source_json_path=scrape_dir / f"{request.model}.source.json",
            scrape_normalized_json_path=scrape_dir / f"{request.model}.normalized.json",
            source_report_json_path=scrape_dir / f"{request.model}.report.json",
            llm_context_path=Path(result["llm_context_path"]),
            prompt_path=Path(result["prompt_path"]),
            llm_output_path=model_root / "llm_output.json",
            metadata_path=metadata_path,
        ),
        details={
            "source": str(result.get("scrape_result", {}).get("source", "")),
        },
    )

