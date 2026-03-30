from __future__ import annotations

from .errors import ServiceError
from .models import FullRunRequest, ServiceResult
from .run_execution import execute_run_workflow


def run_product(request: FullRunRequest) -> ServiceResult:
    try:
        return execute_run_workflow(request)
    except Exception as exc:
        raise ServiceError(type(exc).__name__, str(exc), cause=exc) from exc
