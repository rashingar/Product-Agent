from __future__ import annotations

from fastapi import FastAPI

from .routes_health import router as health_router
from .routes_jobs import router as jobs_router


def create_app() -> FastAPI:
    app = FastAPI(title="Product-Agent Local Jobs API")
    app.include_router(health_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    return app


app = create_app()
