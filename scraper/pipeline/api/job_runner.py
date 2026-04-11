from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
import queue
import threading
import time
from collections.abc import Callable

from ..services import (
    PrepareRequest,
    PublishRequest,
    RenderRequest,
    ServiceError,
    ServiceResult,
    prepare_product,
    publish_product,
    render_product,
)
from ..services.models import RunStatus
from .job_models import JobRecord, JobStatus, JobType
from .job_store import JobStore


LogCallback = Callable[[str], None]
JobRunnerCallback = Callable[[JobRecord, LogCallback], "JobRunResult | None"]


@dataclass(slots=True)
class JobRunResult:
    status: JobStatus = JobStatus.SUCCEEDED
    message: str | None = None
    error: str | None = None
    error_code: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)


def stub_runner_callback(record: JobRecord, log: LogCallback) -> None:
    log(f"Stub runner accepted {record.job_type.value} job; pipeline services were not invoked.")


def service_runner_callback(record: JobRecord, log: LogCallback) -> JobRunResult | None:
    if record.job_type == JobType.PREPARE:
        return run_prepare_job(record, log)
    if record.job_type == JobType.RENDER:
        return run_render_job(record, log)
    if record.job_type == JobType.PUBLISH:
        return run_publish_job(record, log)
    return stub_runner_callback(record, log)


def run_prepare_job(
    record: JobRecord,
    log: LogCallback,
    *,
    prepare_product_fn: Callable[[PrepareRequest], ServiceResult] | None = None,
) -> JobRunResult:
    prepare_product_fn = prepare_product_fn or prepare_product
    request = PrepareRequest(
        model=str(record.payload["model"]),
        url=str(record.payload["url"]),
        photos=record.payload.get("photos", 1),
        sections=record.payload.get("sections", 0),
        skroutz_status=record.payload.get("skroutz_status", 0),
        boxnow=record.payload.get("boxnow", 0),
        price=record.payload.get("price", 0),
    )
    log("Calling prepare service.")
    result = prepare_product_fn(request)
    return _job_result_from_service_result(
        "prepare",
        result,
        log,
        success_message="Prepare job succeeded.",
        failure_message="Prepare job failed.",
    )


def run_render_job(
    record: JobRecord,
    log: LogCallback,
    *,
    render_product_fn: Callable[[RenderRequest], ServiceResult] | None = None,
) -> JobRunResult:
    render_product_fn = render_product_fn or render_product
    request = RenderRequest(model=str(record.payload["model"]))
    log("Calling render service.")
    result = render_product_fn(request)
    return _job_result_from_service_result(
        "render",
        result,
        log,
        success_message="Render job succeeded.",
        failure_message="Render job failed.",
    )


def run_publish_job(
    record: JobRecord,
    log: LogCallback,
    *,
    publish_product_fn: Callable[[PublishRequest], ServiceResult] | None = None,
) -> JobRunResult:
    publish_product_fn = publish_product_fn or publish_product
    current_job_product_file = record.payload.get("current_job_product_file")
    request = PublishRequest(
        model=str(record.payload["model"]),
        current_job_product_file=Path(str(current_job_product_file)) if current_job_product_file else None,
    )
    log("Calling publish service.")
    result = publish_product_fn(request)
    return _job_result_from_service_result(
        "publish",
        result,
        log,
        success_message="Publish job succeeded.",
        failure_message="Publish job failed.",
    )


def _job_result_from_service_result(
    operation: str,
    result: ServiceResult,
    log: LogCallback,
    *,
    success_message: str,
    failure_message: str,
) -> JobRunResult:
    log(f"{operation.capitalize()} service returned status: {result.run.status.value}")
    for warning in result.run.warnings:
        log(f"{operation.capitalize()} warning: {warning}")
    if result.run.error_code:
        log(f"{operation.capitalize()} service error code: {result.run.error_code}")
    if result.run.error_detail:
        log(f"{operation.capitalize()} service error detail: {result.run.error_detail}")

    artifacts = _artifact_paths(result)
    if result.run.status == RunStatus.FAILED:
        return JobRunResult(
            status=JobStatus.FAILED,
            message=failure_message,
            error=result.run.error_detail or f"{operation.capitalize()} service returned failed status.",
            error_code=result.run.error_code,
            artifacts=artifacts,
        )
    return JobRunResult(
        status=JobStatus.SUCCEEDED,
        message=success_message,
        error=result.run.error_detail,
        error_code=result.run.error_code,
        artifacts=artifacts,
    )


def _artifact_paths(result: ServiceResult) -> dict[str, str]:
    paths: dict[str, str] = {}
    for field in fields(result.artifacts):
        value = getattr(result.artifacts, field.name)
        if value is not None:
            paths[field.name] = str(value)
    for name, value in result.details.items():
        if name.endswith("_path") and value is not None:
            paths[name] = str(value)
    return paths


class SequentialJobRunner:
    def __init__(self, store: JobStore, callback: JobRunnerCallback | None = None) -> None:
        self._store = store
        self._callback = callback or service_runner_callback
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._condition = threading.Condition(threading.RLock())
        self._thread: threading.Thread | None = None
        self._active_job_id: str | None = None
        self._pending_count = 0
        self._stopping = False

    @property
    def active_job_id(self) -> str | None:
        with self._condition:
            return self._active_job_id

    def enqueue(self, job_id: str) -> None:
        with self._condition:
            if self._stopping:
                raise RuntimeError("Job runner is stopping.")
            self._ensure_worker_started_locked()
            self._pending_count += 1
            self._queue.put(job_id)
            self._condition.notify_all()

    def wait_until_idle(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._is_idle_locked():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def stop(self, timeout: float = 5.0) -> None:
        with self._condition:
            self._stopping = True
            thread = self._thread
            if thread is None:
                return
            self._queue.put(None)
            self._condition.notify_all()
        thread.join(timeout)

    def _ensure_worker_started_locked(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, name="product-agent-api-job-runner", daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                if job_id is None:
                    return
                with self._condition:
                    self._active_job_id = job_id
                    self._condition.notify_all()
                self._run_job(job_id)
            finally:
                with self._condition:
                    if self._active_job_id == job_id:
                        self._active_job_id = None
                    if job_id is not None:
                        self._pending_count -= 1
                    self._condition.notify_all()
                self._queue.task_done()

    def _run_job(self, job_id: str) -> None:
        record = self._store.get_job(job_id)
        if record is None or record.status != JobStatus.QUEUED:
            return
        record = self._store.mark_running(job_id, message="Job started.")

        def log(line: str) -> None:
            self._store.append_log(job_id, line)

        try:
            log(f"Started {record.job_type.value} job.")
            result = self._callback(record, log) or JobRunResult()
            if result.artifacts:
                self._store.update_artifacts(job_id, result.artifacts)
        except ServiceError as exc:
            log(f"Failed {record.job_type.value} job [{exc.code}]: {exc.message}")
            self._store.mark_failed(
                job_id,
                exc.message,
                message="Job failed.",
                error_code=exc.code,
            )
        except Exception as exc:
            log(f"Failed {record.job_type.value} job: {exc}")
            self._store.mark_failed(job_id, str(exc), message="Job failed.")
        else:
            if result.status == JobStatus.FAILED:
                log(f"Failed {record.job_type.value} job: {result.error}")
                self._store.mark_failed(
                    job_id,
                    result.error or "Job failed.",
                    message=result.message or "Job failed.",
                    error_code=result.error_code,
                )
                return
            log(f"Finished {record.job_type.value} job.")
            self._store.mark_succeeded(
                job_id,
                message=result.message or "Job succeeded.",
                error=result.error,
                error_code=result.error_code,
            )

    def _is_idle_locked(self) -> bool:
        return self._pending_count == 0 and self._active_job_id is None
