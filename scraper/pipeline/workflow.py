from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .full_run import execute_full_run
from .input_validation import FAIL_MESSAGE, validate_input
from .models import CLIInput
from .repo_paths import REPO_ROOT
from .services.errors import ServiceError
from .services.models import PrepareRequest, RenderRequest
from .services.prepare_execution import execute_prepare_workflow
from .services.prepare_service import prepare_product
from .services.render_execution import execute_render_workflow
from .services.render_service import render_product

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


def prepare_workflow(cli: CLIInput) -> dict[str, Any]:
    return execute_prepare_workflow(cli, work_root=WORK_ROOT, execute_full_run_fn=execute_full_run)


def resolve_model_for_render(args: argparse.Namespace) -> str:
    values = read_template_values(args.template_file, args.stdin)
    model = str(args.model or values.get("model", "")).strip()
    if not model:
        raise ValueError(FAIL_MESSAGE)
    if not model.isdigit() or len(model) != 6:
        raise ValueError(FAIL_MESSAGE)
    return model


def render_workflow(model: str) -> dict[str, Any]:
    return execute_render_workflow(model, work_root=WORK_ROOT, products_root=PRODUCTS_ROOT)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
