from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class JobType(str, Enum):
    PREPARE = "prepare"
    RENDER = "render"
    PUBLISH = "publish"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def coerce_job_type(value: JobType | str) -> JobType:
    return value if isinstance(value, JobType) else JobType(str(value))


def coerce_job_status(value: JobStatus | str) -> JobStatus:
    return value if isinstance(value, JobStatus) else JobStatus(str(value))


@dataclass(slots=True)
class JobRecord:
    job_id: str
    job_type: JobType
    status: JobStatus
    model: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    message: str | None = None
    error: str | None = None
    log_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "model": self.model,
            "payload": self.payload,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "message": self.message,
            "error": self.error,
            "log_path": self.log_path,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> JobRecord:
        job_payload = payload.get("payload", {})
        if not isinstance(job_payload, dict):
            job_payload = {}
        return cls(
            job_id=str(payload["job_id"]),
            job_type=coerce_job_type(payload["job_type"]),
            status=coerce_job_status(payload["status"]),
            model=str(payload.get("model", "")),
            payload=dict(job_payload),
            created_at=str(payload.get("created_at") or utc_now_iso()),
            updated_at=str(payload.get("updated_at") or utc_now_iso()),
            started_at=_optional_str(payload.get("started_at")),
            finished_at=_optional_str(payload.get("finished_at")),
            message=_optional_str(payload.get("message")),
            error=_optional_str(payload.get("error")),
            log_path=_optional_str(payload.get("log_path")),
        )


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)
