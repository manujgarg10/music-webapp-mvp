from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from app.schemas import CreateJobRequest, JobRecord
from app.services.pipeline import run_job


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create(self, request: CreateJobRequest) -> JobRecord:
        now = datetime.now(timezone.utc)
        job = JobRecord(
            job_id=str(uuid.uuid4()),
            status="queued",
            request=request,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes: object) -> JobRecord:
        with self._lock:
            job = self._jobs[job_id]
            updated = job.model_copy(update={**changes, "updated_at": datetime.now(timezone.utc)})
            self._jobs[job_id] = updated
            return updated

    def start_background_run(self, job_id: str) -> None:
        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        thread.start()

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        self.update(job_id, status="running")
        try:
            result = run_job(job_id, job.request)
            self.update(job_id, status="completed", result=result)
        except Exception as exc:  # noqa: BLE001
            self.update(job_id, status="failed", error=str(exc))


job_store = JobStore()

