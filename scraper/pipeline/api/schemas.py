from __future__ import annotations

from pydantic import BaseModel, Field

from .artifact_resolver import ResolvedArtifact
from .job_models import JobRecord, JobStatus, JobType


class HealthResponse(BaseModel):
    status: str = "ok"


class PrepareJobRequest(BaseModel):
    model: str
    url: str
    photos: int = 1
    sections: int = 0
    skroutz_status: int = 0
    boxnow: int = 0
    price: str | float | int = 0


class RenderJobRequest(BaseModel):
    model: str


class PublishJobRequest(BaseModel):
    model: str
    current_job_product_file: str | None = None


class JobResponse(BaseModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    model: str
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    message: str | None = None
    error: str | None = None
    error_code: str | None = None

    @classmethod
    def from_record(cls, record: JobRecord) -> JobResponse:
        return cls(
            job_id=record.job_id,
            job_type=record.job_type,
            status=record.status,
            model=record.model,
            created_at=record.created_at,
            updated_at=record.updated_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            message=record.message,
            error=record.error,
            error_code=record.error_code,
        )


class JobListResponse(BaseModel):
    jobs: list[JobResponse] = Field(default_factory=list)


class JobLogsResponse(BaseModel):
    job_id: str
    lines: list[str] = Field(default_factory=list)


class JobArtifact(BaseModel):
    name: str
    path: str
    kind: str | None = None


class JobArtifactsResponse(BaseModel):
    job_id: str
    artifacts: list[JobArtifact] = Field(default_factory=list)

    @classmethod
    def from_artifacts(cls, job_id: str, artifacts: list[ResolvedArtifact]) -> JobArtifactsResponse:
        return cls(
            job_id=job_id,
            artifacts=[
                JobArtifact(name=artifact.name, path=artifact.path, kind=artifact.kind)
                for artifact in artifacts
            ],
        )


class ErrorResponse(BaseModel):
    detail: str
