from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ..llm_contract import (
    build_intro_text_context,
    build_seo_meta_context,
    build_task_manifest,
)
from ..models import CLIInput
from ..prepare_stage import execute_prepare_stage
from ..repo_paths import INTRO_TEXT_PROMPT_PATH, REPO_ROOT, SEO_META_PROMPT_PATH
from ..utils import ensure_directory, utcnow_iso, write_json, write_text
from .errors import service_error_from_exception
from .metadata import maybe_write_run_metadata
from .models import RunArtifacts, RunStatus, RunType

WORK_ROOT = REPO_ROOT / "work"


def _path_or_none(value: str | Path | None) -> Path | None:
    if value in (None, ""):
        return None
    return Path(value)


def execute_prepare_workflow(
    cli: CLIInput,
    *,
    work_root: Path = WORK_ROOT,
    execute_prepare_stage_fn: Callable[..., dict[str, Any]] = execute_prepare_stage,
) -> dict[str, Any]:
    requested_at = utcnow_iso()
    started_at = requested_at
    model_root = ensure_directory(work_root / cli.model)
    scrape_dir = ensure_directory(model_root / "scrape")
    llm_dir = ensure_directory(model_root / "llm")
    task_manifest_path = llm_dir / "task_manifest.json"
    intro_text_context_path = llm_dir / "intro_text.context.json"
    intro_text_prompt_path = llm_dir / "intro_text.prompt.txt"
    intro_text_output_path = llm_dir / "intro_text.output.txt"
    seo_meta_context_path = llm_dir / "seo_meta.context.json"
    seo_meta_prompt_path = llm_dir / "seo_meta.prompt.txt"
    seo_meta_output_path = llm_dir / "seo_meta.output.json"
    scrape_cli = CLIInput(**{**cli.to_dict(), "out": str(scrape_dir)})
    try:
        result = execute_prepare_stage_fn(scrape_cli, model_dir=scrape_dir)
        deterministic_product = result["normalized"].get("deterministic_product", {})
        intro_text_context = build_intro_text_context(
            cli=scrape_cli,
            parsed=result["parsed"],
            taxonomy=result["taxonomy"],
            deterministic_product=deterministic_product,
        )
        seo_meta_context = build_seo_meta_context(
            cli=scrape_cli,
            parsed=result["parsed"],
            taxonomy=result["taxonomy"],
            deterministic_product=deterministic_product,
        )
        intro_text_prompt = INTRO_TEXT_PROMPT_PATH.read_text(encoding="utf-8").replace(
            "{{LLM_CONTEXT_JSON}}",
            json.dumps(intro_text_context, ensure_ascii=False, indent=2),
        )
        seo_meta_prompt = SEO_META_PROMPT_PATH.read_text(encoding="utf-8").replace(
            "{{LLM_CONTEXT_JSON}}",
            json.dumps(seo_meta_context, ensure_ascii=False, indent=2),
        )
        task_manifest = build_task_manifest(
            llm_dir=str(llm_dir),
            intro_text_context_path=str(intro_text_context_path),
            intro_text_prompt_path=str(intro_text_prompt_path),
            intro_text_output_path=str(intro_text_output_path),
            seo_meta_context_path=str(seo_meta_context_path),
            seo_meta_prompt_path=str(seo_meta_prompt_path),
            seo_meta_output_path=str(seo_meta_output_path),
        )
        write_json(intro_text_context_path, intro_text_context)
        write_text(intro_text_prompt_path, intro_text_prompt)
        write_json(seo_meta_context_path, seo_meta_context)
        write_text(seo_meta_prompt_path, seo_meta_prompt)
        write_json(task_manifest_path, task_manifest)
        finished_at = utcnow_iso()
        metadata_path = maybe_write_run_metadata(
            model=cli.model,
            run_type=RunType.PREPARE,
            status=RunStatus.COMPLETED,
            model_root=model_root,
            artifacts=RunArtifacts(
                model_root=model_root,
                scrape_dir=scrape_dir,
                llm_dir=llm_dir,
                raw_html_path=_path_or_none(result.get("raw_html_path")),
                source_json_path=_path_or_none(result.get("source_json_path")),
                scrape_normalized_json_path=_path_or_none(result.get("normalized_json_path")),
                source_report_json_path=_path_or_none(result.get("report_json_path")),
                llm_task_manifest_path=task_manifest_path,
                intro_text_context_path=intro_text_context_path,
                intro_text_prompt_path=intro_text_prompt_path,
                intro_text_output_path=intro_text_output_path,
                seo_meta_context_path=seo_meta_context_path,
                seo_meta_prompt_path=seo_meta_prompt_path,
                seo_meta_output_path=seo_meta_output_path,
            ),
            requested_at=requested_at,
            started_at=started_at,
            finished_at=finished_at,
            warnings=list(result.get("report", {}).get("warnings", [])),
            details={
                "source": str(result.get("source", "")),
                "llm_prepare_mode": "split_tasks",
                "llm_primary_outputs_dir": str(llm_dir),
            },
        )
        return {
            "model_root": model_root,
            "scrape_dir": scrape_dir,
            "llm_dir": llm_dir,
            "task_manifest_path": task_manifest_path,
            "intro_text_context_path": intro_text_context_path,
            "intro_text_prompt_path": intro_text_prompt_path,
            "intro_text_output_path": intro_text_output_path,
            "seo_meta_context_path": seo_meta_context_path,
            "seo_meta_prompt_path": seo_meta_prompt_path,
            "seo_meta_output_path": seo_meta_output_path,
            "run_status": RunStatus.COMPLETED.value,
            "metadata_path": metadata_path,
            "scrape_result": result,
        }
    except Exception as exc:
        finished_at = utcnow_iso()
        service_error = service_error_from_exception(exc, operation="prepare")
        maybe_write_run_metadata(
            model=cli.model,
            run_type=RunType.PREPARE,
            status=RunStatus.FAILED,
            model_root=model_root,
            artifacts=RunArtifacts(
                model_root=model_root,
                scrape_dir=scrape_dir,
                llm_dir=llm_dir,
                raw_html_path=scrape_dir / f"{cli.model}.raw.html",
                source_json_path=scrape_dir / f"{cli.model}.source.json",
                scrape_normalized_json_path=scrape_dir / f"{cli.model}.normalized.json",
                source_report_json_path=scrape_dir / f"{cli.model}.report.json",
                llm_task_manifest_path=task_manifest_path,
                intro_text_context_path=intro_text_context_path,
                intro_text_prompt_path=intro_text_prompt_path,
                intro_text_output_path=intro_text_output_path,
                seo_meta_context_path=seo_meta_context_path,
                seo_meta_prompt_path=seo_meta_prompt_path,
                seo_meta_output_path=seo_meta_output_path,
            ),
            requested_at=requested_at,
            started_at=started_at,
            finished_at=finished_at,
            error_code=service_error.code,
            error_detail=service_error.message,
        )
        raise
