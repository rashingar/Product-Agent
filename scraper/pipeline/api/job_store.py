from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from ..repo_paths import REPO_ROOT
from .job_models import JobRecord, JobStatus, JobType, coerce_job_type, utc_now_iso


DEFAULT_JOBS_DIR = REPO_ROOT / "work" / "api" / "jobs"
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class JobStore:
    def __init__(self, jobs_dir: Path | str = DEFAULT_JOBS_DIR) -> None:
        self.jobs_dir = Path(jobs_dir)
        self._lock = RLock()

    def enqueue(
        self,
        job_type: JobType | str,
        payload: Mapping[str, Any],
        *,
        job_id: str | None = None,
    ) -> JobRecord:
        job_id = job_id or uuid.uuid4().hex
        self._validate_job_id(job_id)
        now = utc_now_iso()
        record = JobRecord(
            job_id=job_id,
            job_type=coerce_job_type(job_type),
            status=JobStatus.QUEUED,
            model=str(payload.get("model", "")),
            payload=dict(payload),
            created_at=now,
            updated_at=now,
            log_path=str(self.log_path(job_id)),
        )
        with self._lock:
            self._ensure_jobs_dir()
            self._write_record(record)
            self.log_path(job_id).touch(exist_ok=True)
        return record

    def list_jobs(self) -> list[JobRecord]:
        with self._lock:
            if not self.jobs_dir.exists():
                return []
            records = [self._read_record_path(path) for path in self.jobs_dir.glob("*.json")]
        return sorted(records, key=lambda record: (record.created_at, record.job_id))

    def get_job(self, job_id: str) -> JobRecord | None:
        self._validate_job_id(job_id)
        path = self.metadata_path(job_id)
        with self._lock:
            if not path.exists():
                return None
            return self._read_record_path(path)

    def mark_running(self, job_id: str, *, message: str | None = None) -> JobRecord:
        now = utc_now_iso()
        with self._lock:
            record = self._require_job(job_id)
            record.status = JobStatus.RUNNING
            record.started_at = record.started_at or now
            record.updated_at = now
            record.message = message
            self._write_record(record)
            return record

    def mark_succeeded(
        self,
        job_id: str,
        *,
        message: str | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> JobRecord:
        now = utc_now_iso()
        with self._lock:
            record = self._require_job(job_id)
            record.status = JobStatus.SUCCEEDED
            record.finished_at = now
            record.updated_at = now
            record.message = message
            record.error = error
            record.error_code = error_code
            self._write_record(record)
            return record

    def mark_failed(
        self,
        job_id: str,
        error: str,
        *,
        message: str | None = None,
        error_code: str | None = None,
    ) -> JobRecord:
        now = utc_now_iso()
        with self._lock:
            record = self._require_job(job_id)
            record.status = JobStatus.FAILED
            record.finished_at = now
            record.updated_at = now
            record.message = message
            record.error = error
            record.error_code = error_code
            self._write_record(record)
            return record

    def update_artifacts(self, job_id: str, artifacts: Mapping[str, object | None]) -> JobRecord:
        with self._lock:
            record = self._require_job(job_id)
            record.artifacts = {
                str(name): str(path)
                for name, path in artifacts.items()
                if path is not None
            }
            record.updated_at = utc_now_iso()
            self._write_record(record)
            return record

    def append_log(self, job_id: str, line: str) -> None:
        self._validate_job_id(job_id)
        with self._lock:
            self._ensure_jobs_dir()
            with self.log_path(job_id).open("a", encoding="utf-8") as handle:
                handle.write(f"{line.rstrip()}\n")

    def read_logs(self, job_id: str) -> list[str]:
        self._validate_job_id(job_id)
        path = self.log_path(job_id)
        with self._lock:
            if not path.exists():
                return []
            return path.read_text(encoding="utf-8").splitlines()

    def metadata_path(self, job_id: str) -> Path:
        self._validate_job_id(job_id)
        return self.jobs_dir / f"{job_id}.json"

    def log_path(self, job_id: str) -> Path:
        self._validate_job_id(job_id)
        return self.jobs_dir / f"{job_id}.log"

    def _ensure_jobs_dir(self) -> None:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _require_job(self, job_id: str) -> JobRecord:
        record = self.get_job(job_id)
        if record is None:
            raise KeyError(job_id)
        return record

    def _read_record_path(self, path: Path) -> JobRecord:
        return JobRecord.from_mapping(json.loads(path.read_text(encoding="utf-8")))

    def _write_record(self, record: JobRecord) -> None:
        path = self.metadata_path(record.job_id)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)

    @staticmethod
    def _validate_job_id(job_id: str) -> None:
        if not job_id or not _JOB_ID_RE.fullmatch(job_id):
            raise ValueError(f"Invalid job id: {job_id!r}")
