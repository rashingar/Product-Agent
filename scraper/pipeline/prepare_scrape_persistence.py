from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .utils import ensure_directory, write_json, write_text


@dataclass(slots=True)
class PrepareScrapePersistenceInput:
    model: str
    scrape_dir: Path
    raw_html: str | None = None
    source_payload: Mapping[str, Any] | None = None
    normalized_payload: Mapping[str, Any] | None = None
    report_payload: Mapping[str, Any] | None = None
    bescos_raw_payload: Mapping[str, Any] | None = None


@dataclass(slots=True)
class PrepareScrapePersistenceResult:
    scrape_dir: Path
    raw_html_path: Path
    source_json_path: Path
    normalized_json_path: Path
    report_json_path: Path
    bescos_raw_path: Path
    files_written: list[Path] = field(default_factory=list)
    cleaned_paths: list[Path] = field(default_factory=list)


def persist_prepare_scrape_artifacts(
    persistence_input: PrepareScrapePersistenceInput,
) -> PrepareScrapePersistenceResult:
    scrape_dir = ensure_directory(persistence_input.scrape_dir)
    raw_html_path = scrape_dir / f"{persistence_input.model}.raw.html"
    source_json_path = scrape_dir / f"{persistence_input.model}.source.json"
    normalized_json_path = scrape_dir / f"{persistence_input.model}.normalized.json"
    report_json_path = scrape_dir / f"{persistence_input.model}.report.json"
    bescos_raw_path = scrape_dir / "bescos_raw.json"

    cleaned_paths: list[Path] = []
    if bescos_raw_path.exists():
        bescos_raw_path.unlink()
        cleaned_paths.append(bescos_raw_path)

    files_written: list[Path] = []
    if persistence_input.raw_html is not None:
        write_text(raw_html_path, persistence_input.raw_html)
        files_written.append(raw_html_path)
    if persistence_input.source_payload is not None:
        write_json(source_json_path, persistence_input.source_payload)
        files_written.append(source_json_path)
    if persistence_input.normalized_payload is not None:
        write_json(normalized_json_path, persistence_input.normalized_payload)
        files_written.append(normalized_json_path)
    if persistence_input.report_payload is not None:
        write_json(report_json_path, persistence_input.report_payload)
        files_written.append(report_json_path)

    if persistence_input.bescos_raw_payload is not None:
        write_json(bescos_raw_path, persistence_input.bescos_raw_payload)
        files_written.append(bescos_raw_path)

    return PrepareScrapePersistenceResult(
        scrape_dir=scrape_dir,
        raw_html_path=raw_html_path,
        source_json_path=source_json_path,
        normalized_json_path=normalized_json_path,
        report_json_path=report_json_path,
        bescos_raw_path=bescos_raw_path,
        files_written=files_written,
        cleaned_paths=cleaned_paths,
    )
