from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, HTTPException, status

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

_NOT_IMPLEMENTED_DETAIL = "Job persistence and execution are not implemented yet."
_NOT_IMPLEMENTED_RESPONSE = {
    status.HTTP_501_NOT_IMPLEMENTED: {
        "model": ErrorResponse,
        "description": "Job persistence and execution are not implemented yet.",
    }
}


def _job_api_not_implemented() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_NOT_IMPLEMENTED_DETAIL,
    )


@router.post(
    "/prepare",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_NOT_IMPLEMENTED_RESPONSE,
)
def prepare_job(_request: PrepareJobRequest) -> JobResponse:
    return _job_api_not_implemented()


@router.post(
    "/render",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_NOT_IMPLEMENTED_RESPONSE,
)
def render_job(_request: RenderJobRequest) -> JobResponse:
    return _job_api_not_implemented()


@router.post(
    "/publish",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_NOT_IMPLEMENTED_RESPONSE,
)
def publish_job(_request: PublishJobRequest) -> JobResponse:
    return _job_api_not_implemented()


@router.get("", response_model=JobListResponse, responses=_NOT_IMPLEMENTED_RESPONSE)
def list_jobs() -> JobListResponse:
    return _job_api_not_implemented()


@router.get("/{job_id}", response_model=JobResponse, responses=_NOT_IMPLEMENTED_RESPONSE)
def get_job(job_id: str) -> JobResponse:
    return _job_api_not_implemented()


@router.get("/{job_id}/logs", response_model=JobLogsResponse, responses=_NOT_IMPLEMENTED_RESPONSE)
def get_job_logs(job_id: str) -> JobLogsResponse:
    return _job_api_not_implemented()


@router.get("/{job_id}/artifacts", response_model=JobArtifactsResponse, responses=_NOT_IMPLEMENTED_RESPONSE)
def get_job_artifacts(job_id: str) -> JobArtifactsResponse:
    return _job_api_not_implemented()
