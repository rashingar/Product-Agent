from __future__ import annotations

from pathlib import Path

from ..models import CLIInput
from .errors import ServiceError
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
            "product_name": str(getattr(result.get("parsed", None), "source", None).name if result.get("parsed", None) else ""),
            "product_code": str(getattr(result.get("parsed", None), "source", None).product_code if result.get("parsed", None) else ""),
            "brand": str(getattr(result.get("parsed", None), "source", None).brand if result.get("parsed", None) else ""),
            "taxonomy_path": str(getattr(result.get("taxonomy", None), "taxonomy_path", "") or ""),
            "matched_schema_id": str(getattr(result.get("schema_match", None), "matched_schema_id", "") or ""),
            "schema_score": float(getattr(result.get("schema_match", None), "score", 0.0) or 0.0),
            "warnings_count": len(warnings),
        },
    )
