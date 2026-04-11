from __future__ import annotations

import threading
import time
from pathlib import Path

from pipeline.api.job_models import JobRecord, JobStatus, JobType
from pipeline.api.job_runner import LogCallback, SequentialJobRunner
from pipeline.api.job_store import JobStore


def test_runner_executes_jobs_sequentially(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    events: list[tuple[str, str]] = []
    active_count = 0
    max_active_count = 0
    lock = threading.Lock()

    def callback(record: JobRecord, log: LogCallback) -> None:
        nonlocal active_count, max_active_count
        with lock:
            active_count += 1
            max_active_count = max(max_active_count, active_count)
            events.append(("start", record.job_id))
        log(f"callback {record.job_id}")
        time.sleep(0.02)
        with lock:
            events.append(("end", record.job_id))
            active_count -= 1

    runner = SequentialJobRunner(store, callback)
    first = store.enqueue(JobType.PREPARE, {"model": "111111"}, job_id="job-1")
    second = store.enqueue(JobType.RENDER, {"model": "222222"}, job_id="job-2")

    try:
        runner.enqueue(first.job_id)
        runner.enqueue(second.job_id)

        assert runner.wait_until_idle(timeout=2.0)
    finally:
        runner.stop()

    assert max_active_count == 1
    assert events == [
        ("start", "job-1"),
        ("end", "job-1"),
        ("start", "job-2"),
        ("end", "job-2"),
    ]
    assert store.get_job(first.job_id).status == JobStatus.SUCCEEDED
    assert store.get_job(second.job_id).status == JobStatus.SUCCEEDED
    assert "callback job-1" in store.read_logs(first.job_id)
    assert "callback job-2" in store.read_logs(second.job_id)


def test_runner_marks_job_failed_when_callback_raises(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")

    def callback(record: JobRecord, log: LogCallback) -> None:
        log(f"failing {record.job_id}")
        raise RuntimeError("boom")

    runner = SequentialJobRunner(store, callback)
    record = store.enqueue(JobType.PUBLISH, {"model": "233541"}, job_id="job-1")

    try:
        runner.enqueue(record.job_id)

        assert runner.wait_until_idle(timeout=2.0)
    finally:
        runner.stop()

    failed = store.get_job(record.job_id)
    logs = store.read_logs(record.job_id)
    assert failed.status == JobStatus.FAILED
    assert failed.error == "boom"
    assert "failing job-1" in logs
    assert "Failed publish job: boom" in logs
