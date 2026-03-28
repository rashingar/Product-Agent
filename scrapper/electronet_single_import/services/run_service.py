from __future__ import annotations

from pathlib import Path

from ..models import CLIInput
from .errors import ServiceError
from .models import FullRunRequest, RunArtifacts, RunMetadata, RunStatus, RunType, ServiceResult


def run_product(request: FullRunRequest) -> ServiceResult:
    from .. import cli

    try:
        result = cli.run_cli_input(
            CLIInput(
                model=request.model,
                url=request.url,
                photos=request.photos,
                sections=request.sections,
                skroutz_status=request.skroutz_status,
                boxnow=request.boxnow,
                price=request.price,
                out=request.out,
            )
        )
    except Exception as exc:
        raise ServiceError(type(exc).__name__, str(exc), cause=exc) from exc

    model_dir = Path(result["model_dir"])
    csv_path = Path(result["csv_path"])
    report = result["report"]
    parsed = result["parsed"]
    taxonomy = result["taxonomy"]
    schema_match = result["schema_match"]
    return ServiceResult(
        run=RunMetadata(
            model=request.model,
            run_type=RunType.FULL,
            status=RunStatus.COMPLETED,
            warnings=list(report.get("warnings", [])),
        ),
        artifacts=RunArtifacts(
            model_root=model_dir,
            raw_html_path=Path(result["raw_html_path"]),
            source_json_path=Path(result["source_json_path"]),
            scrape_normalized_json_path=Path(result["normalized_json_path"]),
            source_report_json_path=Path(result["report_json_path"]),
        ),
        details={
            "source": str(result.get("source", "")),
            "csv_path": str(csv_path),
            "product_name": parsed.source.name,
            "product_code": parsed.source.product_code,
            "brand": parsed.source.brand,
            "taxonomy_path": taxonomy.taxonomy_path or "",
            "matched_schema_id": schema_match.matched_schema_id,
            "schema_score": float(schema_match.score),
            "warnings_count": len(report.get("warnings", [])),
        },
    )
