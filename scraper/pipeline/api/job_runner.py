from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable

from .job_models import JobRecord, JobStatus
from .job_store import JobStore


LogCallback = Callable[[str], None]
JobRunnerCallback = Callable[[JobRecord, LogCallback], None]


def stub_runner_callback(record: JobRecord, log: LogCallback) -> None:
    log(f"Stub runner accepted {record.job_type.value} job; pipeline services were not invoked.")


class SequentialJobRunner:
    def __init__(self, store: JobStore, callback: JobRunnerCallback | None = None) -> None:
        self._store = store
        self._callback = callback or stub_runner_callback
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
            self._callback(record, log)
        except Exception as exc:
            log(f"Failed {record.job_type.value} job: {exc}")
            self._store.mark_failed(job_id, str(exc), message="Job failed.")
        else:
            log(f"Finished {record.job_type.value} job.")
            self._store.mark_succeeded(job_id, message="Job succeeded.")

    def _is_idle_locked(self) -> bool:
        return self._pending_count == 0 and self._active_job_id is None
