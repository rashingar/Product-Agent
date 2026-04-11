from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from .job_models import JobType
from .job_runner import SequentialJobRunner
from .job_store import JobStore
from .schemas import (
    ErrorResponse,
    JobArtifactsResponse,
    JobListResponse,
    JobLogsResponse,
    JobResponse,
    PrepareJobRequest,
    PublishJobRequest,
    RenderJobRequest,
)


router = APIRouter(prefix="/jobs", tags=["jobs"])

_NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "Job not found.",
    }
}


def _request_payload(schema: Any) -> dict[str, Any]:
    if hasattr(schema, "model_dump"):
        return schema.model_dump()
    return schema.dict()


def _job_store(api_request: Request) -> JobStore:
    return api_request.app.state.job_store


def _job_runner(api_request: Request) -> SequentialJobRunner:
    return api_request.app.state.job_runner


def _enqueue_job(api_request: Request, job_type: JobType, payload: dict[str, Any]) -> JobResponse:
    record = _job_store(api_request).enqueue(job_type, payload)
    _job_runner(api_request).enqueue(record.job_id)
    return JobResponse.from_record(record)


def _get_job_response(api_request: Request, job_id: str) -> JobResponse:
    try:
        record = _job_store(api_request).get_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.") from exc
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobResponse.from_record(record)


@router.post(
    "/prepare",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def prepare_job(request: PrepareJobRequest, api_request: Request) -> JobResponse:
    return _enqueue_job(api_request, JobType.PREPARE, _request_payload(request))


@router.post(
    "/render",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def render_job(request: RenderJobRequest, api_request: Request) -> JobResponse:
    return _enqueue_job(api_request, JobType.RENDER, _request_payload(request))


@router.post(
    "/publish",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def publish_job(request: PublishJobRequest, api_request: Request) -> JobResponse:
    return _enqueue_job(api_request, JobType.PUBLISH, _request_payload(request))


@router.get("", response_model=JobListResponse)
def list_jobs(api_request: Request) -> JobListResponse:
    return JobListResponse(
        jobs=[JobResponse.from_record(record) for record in _job_store(api_request).list_jobs()]
    )


@router.get("/{job_id}", response_model=JobResponse, responses=_NOT_FOUND_RESPONSE)
def get_job(job_id: str, api_request: Request) -> JobResponse:
    return _get_job_response(api_request, job_id)


@router.get("/{job_id}/logs", response_model=JobLogsResponse, responses=_NOT_FOUND_RESPONSE)
def get_job_logs(job_id: str, api_request: Request) -> JobLogsResponse:
    _get_job_response(api_request, job_id)
    return JobLogsResponse(job_id=job_id, lines=_job_store(api_request).read_logs(job_id))


@router.get("/{job_id}/artifacts", response_model=JobArtifactsResponse, responses=_NOT_FOUND_RESPONSE)
def get_job_artifacts(job_id: str, api_request: Request) -> JobArtifactsResponse:
    _get_job_response(api_request, job_id)
    return JobArtifactsResponse(job_id=job_id, artifacts=[])
