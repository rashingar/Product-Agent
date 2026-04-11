from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.api.artifact_resolver import resolve_job_artifacts
from pipeline.api.job_models import JobRecord, JobStatus, JobType
from pipeline.api.job_runner import LogCallback, SequentialJobRunner
from pipeline.api.job_store import JobStore


def test_prepare_route_enqueues_job_and_exposes_logs_and_artifacts(tmp_path: Path) -> None:
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from pipeline.api.app import create_app

    store = JobStore(tmp_path / "jobs")

    def fake_callback(record: JobRecord, log: LogCallback) -> None:
        log(f"fake callback for {record.job_id}")
        store.update_artifacts(
            record.job_id,
            {"source_json_path": tmp_path / "work" / record.model / "scrape" / f"{record.model}.source.json"},
        )

    runner = SequentialJobRunner(store, fake_callback)
    app = create_app(job_store=store, job_runner=runner)
    client = fastapi_testclient.TestClient(app)

    try:
        response = client.post(
            "/api/jobs/prepare",
            json={
                "model": "233541",
                "url": "https://www.electronet.gr/example",
                "photos": 6,
                "sections": 2,
                "skroutz_status": 1,
                "boxnow": 0,
                "price": "2099",
            },
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        assert runner.wait_until_idle(timeout=2.0)

        job_response = client.get(f"/api/jobs/{job_id}")
        logs_response = client.get(f"/api/jobs/{job_id}/logs")
        artifacts_response = client.get(f"/api/jobs/{job_id}/artifacts")
    finally:
        runner.stop()

    assert job_response.status_code == 200
    assert job_response.json()["status"] == JobStatus.SUCCEEDED.value
    assert logs_response.status_code == 200
    assert f"fake callback for {job_id}" in logs_response.json()["lines"]
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()["artifacts"] == [
        {
            "name": "source_json_path",
            "path": str(tmp_path / "work" / "233541" / "scrape" / "233541.source.json"),
            "kind": None,
        }
    ]


def test_artifact_resolver_returns_existing_render_compatibility_paths(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "work" / "233541" / "candidate"
    candidate_dir.mkdir(parents=True)
    csv_path = candidate_dir / "233541.csv"
    csv_path.write_text("csv\n", encoding="utf-8")
    validation_path = candidate_dir / "233541.validation.json"
    validation_path.write_text("{}\n", encoding="utf-8")

    record = JobRecord(
        job_id="job-1",
        job_type=JobType.RENDER,
        status=JobStatus.SUCCEEDED,
        model="233541",
    )

    artifacts = resolve_job_artifacts(record, repo_root=tmp_path)

    assert {artifact.name: artifact.kind for artifact in artifacts} == {
        "candidate_csv_path": "file",
        "candidate_dir": "directory",
        "model_root": "directory",
        "validation_report_path": "file",
    }


def test_artifact_resolver_includes_stored_publish_detail_paths(tmp_path: Path) -> None:
    record = JobRecord(
        job_id="job-1",
        job_type=JobType.PUBLISH,
        status=JobStatus.SUCCEEDED,
        model="233541",
        artifacts={
            "upload_report_path": str(tmp_path / "work" / "233541" / "upload.opencart.json"),
            "import_report_path": str(tmp_path / "work" / "233541" / "import.opencart.json"),
        },
    )

    artifacts = resolve_job_artifacts(record, repo_root=tmp_path)

    assert [(artifact.name, artifact.path, artifact.kind) for artifact in artifacts] == [
        ("import_report_path", str(tmp_path / "work" / "233541" / "import.opencart.json"), None),
        ("upload_report_path", str(tmp_path / "work" / "233541" / "upload.opencart.json"), None),
    ]
