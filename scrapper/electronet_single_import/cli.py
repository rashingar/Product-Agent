from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .input_validation import FAIL_MESSAGE, validate_input
from .models import CLIInput
from .services.metadata import maybe_write_run_metadata
from .services.models import FullRunRequest, RunArtifacts, RunStatus, RunType
from .services.errors import ServiceError
from .services.run_service import run_product
from .utils import utcnow_iso


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m electronet_single_import.cli")
    parser.add_argument("--model", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--photos", type=int, default=1)
    parser.add_argument("--sections", type=int, default=0)
    parser.add_argument("--skroutz-status", type=int, default=0, dest="skroutz_status")
    parser.add_argument("--boxnow", type=int, default=0)
    parser.add_argument("--price", default=0)
    parser.add_argument("--out", default="out")
    return parser

def run_cli_input(cli: CLIInput):
    return run_product(
        FullRunRequest(
            model=cli.model,
            url=cli.url,
            photos=cli.photos,
            sections=cli.sections,
            skroutz_status=cli.skroutz_status,
            boxnow=cli.boxnow,
            price=cli.price,
            out=cli.out,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cli: CLIInput | None = None
    requested_at: str | None = None
    try:
        cli = validate_input(args)
        requested_at = utcnow_iso()
        service_result = run_cli_input(cli)
        model_root = Path(cli.out) / cli.model
        metadata_path = maybe_write_run_metadata(
            model=cli.model,
            run_type=RunType.FULL,
            status=RunStatus.COMPLETED,
            model_root=model_root,
            artifacts=RunArtifacts(
                model_root=model_root,
                raw_html_path=model_root / f"{cli.model}.raw.html",
                source_json_path=model_root / f"{cli.model}.source.json",
                scrape_normalized_json_path=model_root / f"{cli.model}.normalized.json",
                source_report_json_path=model_root / f"{cli.model}.report.json",
            ),
            requested_at=requested_at,
            started_at=requested_at,
            finished_at=utcnow_iso(),
            warnings=list(service_result.run.warnings),
            details={
                "source": str(service_result.details.get("source", "")),
                "csv_path": str(model_root / f"{cli.model}.csv"),
            },
        )
    except ValueError as exc:
        message = str(exc)
        print(message)
        return 1 if message == FAIL_MESSAGE else 2
    except ServiceError as exc:
        if cli is not None and requested_at is not None:
            model_root = Path(cli.out) / cli.model
            metadata_path = maybe_write_run_metadata(
                model=cli.model,
                run_type=RunType.FULL,
                status=RunStatus.FAILED,
                model_root=model_root,
                artifacts=RunArtifacts(
                    model_root=model_root,
                    raw_html_path=model_root / f"{cli.model}.raw.html",
                    source_json_path=model_root / f"{cli.model}.source.json",
                    scrape_normalized_json_path=model_root / f"{cli.model}.normalized.json",
                    source_report_json_path=model_root / f"{cli.model}.report.json",
                ),
                requested_at=requested_at,
                started_at=requested_at,
                finished_at=utcnow_iso(),
                error_code=exc.code,
                error_detail=exc.message,
            )
            print(f"Run status: {RunStatus.FAILED.value}")
            print(f"Metadata path: {metadata_path}")
        message = exc.message
        print(message, file=sys.stderr if message != FAIL_MESSAGE else sys.stdout)
        return 3 if "failed" in message.lower() else 4

    resolved_path = str(service_result.details.get("taxonomy_path", "") or "")
    print(f"product name: {service_result.details.get('product_name', '')}")
    print(f"product code: {service_result.details.get('product_code', '')}")
    print(f"brand: {service_result.details.get('brand', '')}")
    print(f"resolved taxonomy path: {resolved_path}")
    print(
        "schema match id / score: "
        f"{service_result.details.get('matched_schema_id', '')} / {float(service_result.details.get('schema_score', 0.0)):.4f}"
    )
    print(f"CSV written path: {Path(cli.out) / cli.model / f'{cli.model}.csv'}")
    print(f"warnings count: {int(service_result.details.get('warnings_count', 0))}")
    print(f"Run status: {RunStatus.COMPLETED.value}")
    print(f"Metadata path: {metadata_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
