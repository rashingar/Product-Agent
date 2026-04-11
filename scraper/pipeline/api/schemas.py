from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class JobType(str, Enum):
    PREPARE = "prepare"
    RENDER = "render"
    PUBLISH = "publish"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


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
    started_at: str | None = None
    finished_at: str | None = None
    message: str | None = None


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


class ErrorResponse(BaseModel):
    detail: str
