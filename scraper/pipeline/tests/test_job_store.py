from __future__ import annotations

import json
from pathlib import Path

from pipeline.api.job_models import JobStatus, JobType
from pipeline.api.job_store import JobStore


def test_enqueue_persists_job_metadata_and_log_file(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")

    record = store.enqueue(
        JobType.PREPARE,
        {
            "model": "233541",
            "url": "https://www.electronet.gr/example",
            "photos": 6,
        },
        job_id="job-1",
    )

    metadata_path = tmp_path / "jobs" / "job-1.json"
    log_path = tmp_path / "jobs" / "job-1.log"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert record.job_id == "job-1"
    assert record.status == JobStatus.QUEUED
    assert metadata_path.exists()
    assert log_path.exists()
    assert payload["job_id"] == "job-1"
    assert payload["job_type"] == "prepare"
    assert payload["status"] == "queued"
    assert payload["model"] == "233541"
    assert payload["payload"]["photos"] == 6
    assert payload["log_path"] == str(log_path)


def test_store_lists_and_gets_jobs_from_disk(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    first = store.enqueue(JobType.PREPARE, {"model": "111111"}, job_id="job-1")
    second = store.enqueue(JobType.RENDER, {"model": "222222"}, job_id="job-2")

    jobs = store.list_jobs()

    assert [job.job_id for job in jobs] == [first.job_id, second.job_id]
    assert store.get_job("job-1") == first
    assert store.get_job("missing") is None


def test_store_updates_statuses_and_reads_logs(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    record = store.enqueue(JobType.PUBLISH, {"model": "233541"}, job_id="job-1")

    running = store.mark_running(record.job_id, message="started")
    store.append_log(record.job_id, "line one")
    store.append_log(record.job_id, "line two")
    succeeded = store.mark_succeeded(record.job_id, message="done")

    loaded = store.get_job(record.job_id)
    assert running.status == JobStatus.RUNNING
    assert running.started_at is not None
    assert succeeded.status == JobStatus.SUCCEEDED
    assert succeeded.finished_at is not None
    assert loaded == succeeded
    assert store.read_logs(record.job_id) == ["line one", "line two"]


def test_store_marks_failed_with_error_detail(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    record = store.enqueue(JobType.RENDER, {"model": "233541"}, job_id="job-1")

    failed = store.mark_failed(record.job_id, "boom", message="failed")

    assert failed.status == JobStatus.FAILED
    assert failed.error == "boom"
    assert failed.message == "failed"
    assert failed.finished_at is not None
