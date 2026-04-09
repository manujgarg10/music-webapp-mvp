from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import RENDERED_DIR, STATIC_DIR, ensure_directories
from app.schemas import CreateJobRequest, HealthResponse, JobRecord
from app.services.jobs import job_store


ensure_directories()

app = FastAPI(title="AI Music Practice MVP")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/api/jobs", response_model=JobRecord)
def create_job(payload: CreateJobRequest) -> JobRecord:
    job = job_store.create(payload)
    job_store.start_background_run(job.job_id)
    return job


@app.get("/api/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: str) -> JobRecord:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.get("/api/artifacts/{job_id}/{filename}")
def get_artifact(job_id: str, filename: str) -> FileResponse:
    file_path = RENDERED_DIR / filename
    if file_path.parent != RENDERED_DIR or not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(file_path, filename=filename)
