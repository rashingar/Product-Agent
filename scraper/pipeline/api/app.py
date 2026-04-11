from __future__ import annotations

from fastapi import FastAPI

from .job_runner import SequentialJobRunner
from .job_store import JobStore
from .routes_health import router as health_router
from .routes_jobs import router as jobs_router


def create_app(
    *,
    job_store: JobStore | None = None,
    job_runner: SequentialJobRunner | None = None,
) -> FastAPI:
    app = FastAPI(title="Product-Agent Local Jobs API")
    app.state.job_store = job_store or JobStore()
    app.state.job_runner = job_runner or SequentialJobRunner(app.state.job_store)
    app.include_router(health_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    return app


app = create_app()
