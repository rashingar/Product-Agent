from __future__ import annotations

from .errors import service_error_from_exception
from .models import FullRunRequest, ServiceResult
from .run_execution import execute_run_workflow


def run_product(request: FullRunRequest) -> ServiceResult:
    try:
        return execute_run_workflow(request)
    except Exception as exc:
        raise service_error_from_exception(exc, operation="full") from exc
