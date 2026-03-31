from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ..utils import write_json
from .models import RunArtifacts, RunMetadata, RunStatus, RunType, ServiceResult

_METADATA_FILENAMES = {
    RunType.PREPARE: "prepare.run.json",
    RunType.RENDER: "render.run.json",
    RunType.PUBLISH: "publish.run.json",
    RunType.FULL: "full.run.json",
}


def metadata_path_for(model_root: Path, run_type: RunType) -> Path:
    return model_root / _METADATA_FILENAMES[run_type]


def _serialize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def write_run_metadata(result: ServiceResult) -> Path:
    metadata_path = result.artifacts.metadata_path
    if metadata_path is None:
        raise ValueError("Run metadata path is required")
    write_json(metadata_path, _serialize(result))
    return metadata_path


def maybe_write_run_metadata(
    *,
    model: str,
    run_type: RunType,
    status: RunStatus,
    model_root: Path,
    artifacts: RunArtifacts,
    requested_at: str,
    started_at: str,
    finished_at: str,
    warnings: list[str] | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    details: dict[str, str | int | float | bool | None] | None = None,
) -> Path:
    metadata_path = metadata_path_for(model_root, run_type)
    artifacts.metadata_path = metadata_path
    payload = ServiceResult(
        run=RunMetadata(
            model=model,
            run_type=run_type,
            status=status,
            requested_at=requested_at,
            started_at=started_at,
            finished_at=finished_at,
            warnings=list(warnings or []),
            error_code=error_code,
            error_detail=error_detail,
        ),
        artifacts=artifacts,
        details=details or {},
    )
    try:
        write_run_metadata(payload)
    except Exception:
        pass
    return metadata_path
