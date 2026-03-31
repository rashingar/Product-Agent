from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from ..models import ParsedProduct, SchemaMatchResult, TaxonomyResolution
from .models import RunStatus

_T = TypeVar("_T")


def _as_dict(payload: Mapping[str, object] | None) -> dict[str, object]:
    return dict(payload or {})


def _require_path(payload: Mapping[str, object], field_name: str) -> Path:
    value = payload[field_name]
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    return Path(value)


def _optional_path(value: str | Path | None) -> Path | None:
    if value in (None, ""):
        return None
    return Path(value)


def _coerce_run_status(value: RunStatus | str) -> RunStatus:
    if isinstance(value, RunStatus):
        return value
    return RunStatus(str(value))


def _typed_or_none(value: Any, expected_type: type[_T]) -> _T | None:
    if isinstance(value, expected_type):
        return value
    return None


def _coerce_warnings(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


@dataclass(slots=True)
class PrepareExecutionScrapeResult:
    source: str = ""
    parsed: ParsedProduct | None = None
    taxonomy: TaxonomyResolution | None = None
    schema_match: SchemaMatchResult | None = None
    report_warnings: list[str] = field(default_factory=list)
    payload: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object] | None) -> "PrepareExecutionScrapeResult":
        payload_dict = _as_dict(payload)
        report = payload_dict.get("report")
        report_dict = _as_dict(report) if isinstance(report, Mapping) else {}
        return cls(
            source=str(payload_dict.get("source", "") or ""),
            parsed=_typed_or_none(payload_dict.get("parsed"), ParsedProduct),
            taxonomy=_typed_or_none(payload_dict.get("taxonomy"), TaxonomyResolution),
            schema_match=_typed_or_none(payload_dict.get("schema_match"), SchemaMatchResult),
            report_warnings=_coerce_warnings(report_dict.get("warnings")),
            payload=payload_dict,
        )


@dataclass(slots=True)
class PrepareExecutionResult:
    model_root: Path
    scrape_dir: Path
    llm_dir: Path
    task_manifest_path: Path
    intro_text_context_path: Path
    intro_text_prompt_path: Path
    intro_text_output_path: Path
    seo_meta_context_path: Path
    seo_meta_prompt_path: Path
    seo_meta_output_path: Path
    run_status: RunStatus
    metadata_path: Path
    scrape_result: PrepareExecutionScrapeResult = field(default_factory=PrepareExecutionScrapeResult)
    payload: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "PrepareExecutionResult":
        payload_dict = _as_dict(payload)
        return cls(
            model_root=_require_path(payload_dict, "model_root"),
            scrape_dir=_require_path(payload_dict, "scrape_dir"),
            llm_dir=_require_path(payload_dict, "llm_dir"),
            task_manifest_path=_require_path(payload_dict, "task_manifest_path"),
            intro_text_context_path=_require_path(payload_dict, "intro_text_context_path"),
            intro_text_prompt_path=_require_path(payload_dict, "intro_text_prompt_path"),
            intro_text_output_path=_require_path(payload_dict, "intro_text_output_path"),
            seo_meta_context_path=_require_path(payload_dict, "seo_meta_context_path"),
            seo_meta_prompt_path=_require_path(payload_dict, "seo_meta_prompt_path"),
            seo_meta_output_path=_require_path(payload_dict, "seo_meta_output_path"),
            run_status=_coerce_run_status(payload_dict["run_status"]),
            metadata_path=_require_path(payload_dict, "metadata_path"),
            scrape_result=PrepareExecutionScrapeResult.from_mapping(payload_dict.get("scrape_result")),
            payload=payload_dict,
        )


@dataclass(slots=True)
class RenderExecutionValidationReport:
    ok: bool = False
    warnings: list[str] = field(default_factory=list)
    payload: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object] | None) -> "RenderExecutionValidationReport":
        payload_dict = _as_dict(payload)
        return cls(
            ok=bool(payload_dict.get("ok", False)),
            warnings=_coerce_warnings(payload_dict.get("warnings")),
            payload=payload_dict,
        )


@dataclass(slots=True)
class RenderExecutionResult:
    candidate_dir: Path
    candidate_csv_path: Path
    published_csv_path: Path | None
    description_path: Path
    characteristics_path: Path
    validation_report_path: Path
    run_status: RunStatus
    metadata_path: Path
    validation_report: RenderExecutionValidationReport = field(default_factory=RenderExecutionValidationReport)
    payload: dict[str, object] = field(default_factory=dict)

    @property
    def model_root(self) -> Path:
        return self.candidate_dir.parent

    @property
    def scrape_dir(self) -> Path:
        return self.model_root / "scrape"

    @property
    def llm_dir(self) -> Path:
        return self.model_root / "llm"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "RenderExecutionResult":
        payload_dict = _as_dict(payload)
        return cls(
            candidate_dir=_require_path(payload_dict, "candidate_dir"),
            candidate_csv_path=_require_path(payload_dict, "candidate_csv_path"),
            published_csv_path=_optional_path(payload_dict.get("published_csv_path")),
            description_path=_require_path(payload_dict, "description_path"),
            characteristics_path=_require_path(payload_dict, "characteristics_path"),
            validation_report_path=_require_path(payload_dict, "validation_report_path"),
            run_status=_coerce_run_status(payload_dict["run_status"]),
            metadata_path=_require_path(payload_dict, "metadata_path"),
            validation_report=RenderExecutionValidationReport.from_mapping(payload_dict.get("validation_report")),
            payload=payload_dict,
        )
