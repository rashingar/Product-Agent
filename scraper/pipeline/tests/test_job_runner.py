from __future__ import annotations

import threading
import time
from pathlib import Path

from pipeline.api import job_runner
from pipeline.api.job_models import JobRecord, JobStatus, JobType
from pipeline.api.job_runner import LogCallback, SequentialJobRunner
from pipeline.api.job_store import JobStore
from pipeline.services import (
    PrepareRequest,
    PublishRequest,
    RenderRequest,
    RunArtifacts,
    RunMetadata,
    RunStatus,
    RunType,
    ServiceError,
    ServiceErrorCode,
    ServiceResult,
)


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


def test_default_runner_calls_prepare_service_and_captures_artifacts(tmp_path: Path, monkeypatch) -> None:
    store = JobStore(tmp_path / "jobs")
    calls: list[PrepareRequest] = []

    def fake_prepare_product(request: PrepareRequest) -> ServiceResult:
        calls.append(request)
        return ServiceResult(
            run=RunMetadata(
                model=request.model,
                run_type=RunType.PREPARE,
                status=RunStatus.COMPLETED,
                warnings=["prepare warning"],
                error_code=ServiceErrorCode.MISSING_ARTIFACT.value,
                error_detail="metadata missing",
            ),
            artifacts=RunArtifacts(
                scrape_dir=tmp_path / "work" / request.model / "scrape",
                llm_dir=tmp_path / "work" / request.model / "llm",
                source_json_path=tmp_path / "work" / request.model / "scrape" / f"{request.model}.source.json",
                llm_task_manifest_path=tmp_path / "work" / request.model / "llm" / "task_manifest.json",
                metadata_path=tmp_path / "work" / request.model / "prepare.run.json",
            ),
        )

    monkeypatch.setattr(job_runner, "prepare_product", fake_prepare_product)
    runner = SequentialJobRunner(store)
    record = store.enqueue(
        JobType.PREPARE,
        {
            "model": "233541",
            "url": "https://www.electronet.gr/example",
            "photos": 6,
            "sections": 2,
            "skroutz_status": 1,
            "boxnow": 0,
            "price": "2099",
        },
        job_id="job-1",
    )

    try:
        runner.enqueue(record.job_id)

        assert runner.wait_until_idle(timeout=2.0)
    finally:
        runner.stop()

    loaded = store.get_job(record.job_id)
    logs = store.read_logs(record.job_id)
    assert calls == [
        PrepareRequest(
            model="233541",
            url="https://www.electronet.gr/example",
            photos=6,
            sections=2,
            skroutz_status=1,
            boxnow=0,
            price="2099",
        )
    ]
    assert loaded.status == JobStatus.SUCCEEDED
    assert loaded.message == "Prepare job succeeded."
    assert loaded.error == "metadata missing"
    assert loaded.error_code == ServiceErrorCode.MISSING_ARTIFACT.value
    assert loaded.artifacts == {
        "scrape_dir": str(tmp_path / "work" / "233541" / "scrape"),
        "llm_dir": str(tmp_path / "work" / "233541" / "llm"),
        "source_json_path": str(tmp_path / "work" / "233541" / "scrape" / "233541.source.json"),
        "llm_task_manifest_path": str(tmp_path / "work" / "233541" / "llm" / "task_manifest.json"),
        "metadata_path": str(tmp_path / "work" / "233541" / "prepare.run.json"),
    }
    assert "Calling prepare service." in logs
    assert "Prepare service returned status: completed" in logs
    assert "Prepare warning: prepare warning" in logs


def test_default_runner_marks_prepare_service_error_failed(tmp_path: Path, monkeypatch) -> None:
    store = JobStore(tmp_path / "jobs")

    def fake_prepare_product(_request: PrepareRequest) -> ServiceResult:
        raise ServiceError(ServiceErrorCode.PARSE_FAILURE.value, "bad source")

    monkeypatch.setattr(job_runner, "prepare_product", fake_prepare_product)
    runner = SequentialJobRunner(store)
    record = store.enqueue(
        JobType.PREPARE,
        {"model": "233541", "url": "https://www.electronet.gr/example"},
        job_id="job-1",
    )

    try:
        runner.enqueue(record.job_id)

        assert runner.wait_until_idle(timeout=2.0)
    finally:
        runner.stop()

    failed = store.get_job(record.job_id)
    logs = store.read_logs(record.job_id)
    assert failed.status == JobStatus.FAILED
    assert failed.error == "bad source"
    assert failed.error_code == ServiceErrorCode.PARSE_FAILURE.value
    assert "Calling prepare service." in logs
    assert "Failed prepare job [parse_failure]: bad source" in logs


def test_default_runner_calls_render_service_and_captures_artifacts(tmp_path: Path, monkeypatch) -> None:
    store = JobStore(tmp_path / "jobs")
    calls: list[RenderRequest] = []

    def fake_render_product(request: RenderRequest) -> ServiceResult:
        calls.append(request)
        return ServiceResult(
            run=RunMetadata(
                model=request.model,
                run_type=RunType.RENDER,
                status=RunStatus.COMPLETED,
            ),
            artifacts=RunArtifacts(
                candidate_dir=tmp_path / "work" / request.model / "candidate",
                candidate_csv_path=tmp_path / "work" / request.model / "candidate" / f"{request.model}.csv",
                published_csv_path=tmp_path / "products" / f"{request.model}.csv",
                validation_report_path=tmp_path / "work" / request.model / "candidate" / f"{request.model}.validation.json",
                metadata_path=tmp_path / "work" / request.model / "render.run.json",
            ),
            details={"validation_ok": True, "published": True},
        )

    monkeypatch.setattr(job_runner, "render_product", fake_render_product)
    runner = SequentialJobRunner(store)
    record = store.enqueue(JobType.RENDER, {"model": "233541"}, job_id="job-1")

    try:
        runner.enqueue(record.job_id)

        assert runner.wait_until_idle(timeout=2.0)
    finally:
        runner.stop()

    loaded = store.get_job(record.job_id)
    logs = store.read_logs(record.job_id)
    assert calls == [RenderRequest(model="233541")]
    assert loaded.status == JobStatus.SUCCEEDED
    assert loaded.message == "Render job succeeded."
    assert loaded.artifacts == {
        "candidate_dir": str(tmp_path / "work" / "233541" / "candidate"),
        "candidate_csv_path": str(tmp_path / "work" / "233541" / "candidate" / "233541.csv"),
        "published_csv_path": str(tmp_path / "products" / "233541.csv"),
        "validation_report_path": str(tmp_path / "work" / "233541" / "candidate" / "233541.validation.json"),
        "metadata_path": str(tmp_path / "work" / "233541" / "render.run.json"),
    }
    assert "Calling render service." in logs
    assert "Render service returned status: completed" in logs


def test_default_runner_marks_render_service_failed_status_failed(tmp_path: Path, monkeypatch) -> None:
    store = JobStore(tmp_path / "jobs")

    def fake_render_product(request: RenderRequest) -> ServiceResult:
        return ServiceResult(
            run=RunMetadata(
                model=request.model,
                run_type=RunType.RENDER,
                status=RunStatus.FAILED,
                error_code=ServiceErrorCode.VALIDATION_FAILURE.value,
                error_detail="Candidate validation failed",
            ),
            artifacts=RunArtifacts(
                validation_report_path=tmp_path / "work" / request.model / "candidate" / f"{request.model}.validation.json",
            ),
        )

    monkeypatch.setattr(job_runner, "render_product", fake_render_product)
    runner = SequentialJobRunner(store)
    record = store.enqueue(JobType.RENDER, {"model": "233541"}, job_id="job-1")

    try:
        runner.enqueue(record.job_id)

        assert runner.wait_until_idle(timeout=2.0)
    finally:
        runner.stop()

    failed = store.get_job(record.job_id)
    assert failed.status == JobStatus.FAILED
    assert failed.error == "Candidate validation failed"
    assert failed.error_code == ServiceErrorCode.VALIDATION_FAILURE.value
    assert failed.artifacts == {
        "validation_report_path": str(tmp_path / "work" / "233541" / "candidate" / "233541.validation.json")
    }


def test_default_runner_calls_publish_service_and_captures_artifacts(tmp_path: Path, monkeypatch) -> None:
    store = JobStore(tmp_path / "jobs")
    calls: list[PublishRequest] = []

    def fake_publish_product(request: PublishRequest) -> ServiceResult:
        calls.append(request)
        return ServiceResult(
            run=RunMetadata(
                model=request.model,
                run_type=RunType.PUBLISH,
                status=RunStatus.COMPLETED,
            ),
            artifacts=RunArtifacts(
                model_root=tmp_path / "work" / request.model,
                published_csv_path=request.current_job_product_file,
                metadata_path=tmp_path / "work" / request.model / "publish.run.json",
            ),
            details={
                "publish_status": "success",
                "upload_report_path": str(tmp_path / "work" / request.model / "upload.opencart.json"),
                "import_report_path": str(tmp_path / "work" / request.model / "import.opencart.json"),
            },
        )

    monkeypatch.setattr(job_runner, "publish_product", fake_publish_product)
    runner = SequentialJobRunner(store)
    product_file = tmp_path / "products" / "233541.csv"
    record = store.enqueue(
        JobType.PUBLISH,
        {
            "model": "233541",
            "current_job_product_file": str(product_file),
        },
        job_id="job-1",
    )

    try:
        runner.enqueue(record.job_id)

        assert runner.wait_until_idle(timeout=2.0)
    finally:
        runner.stop()

    loaded = store.get_job(record.job_id)
    logs = store.read_logs(record.job_id)
    assert calls == [PublishRequest(model="233541", current_job_product_file=product_file)]
    assert loaded.status == JobStatus.SUCCEEDED
    assert loaded.message == "Publish job succeeded."
    assert loaded.artifacts == {
        "model_root": str(tmp_path / "work" / "233541"),
        "published_csv_path": str(product_file),
        "metadata_path": str(tmp_path / "work" / "233541" / "publish.run.json"),
        "upload_report_path": str(tmp_path / "work" / "233541" / "upload.opencart.json"),
        "import_report_path": str(tmp_path / "work" / "233541" / "import.opencart.json"),
    }
    assert "Calling publish service." in logs
    assert "Publish service returned status: completed" in logs
