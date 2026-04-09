from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.config import SUPPORTED_INSTRUMENTS


JobStatus = Literal["queued", "running", "completed", "failed"]
JobMode = Literal["analysis", "backing_track"]
InstrumentName = Literal["guitar", "vocals", "bass", "drums"]


class CreateJobRequest(BaseModel):
    youtube_url: HttpUrl
    job_mode: JobMode = "analysis"
    instruments_to_suppress: List[InstrumentName] = Field(default_factory=lambda: ["guitar"])

    @model_validator(mode="after")
    def validate_request(self) -> "CreateJobRequest":
        unique = list(dict.fromkeys(self.instruments_to_suppress))
        self.instruments_to_suppress = unique
        if len(unique) > 2:
            raise ValueError("You can suppress at most two stems in this MVP.")
        unsupported = [instrument for instrument in unique if instrument not in SUPPORTED_INSTRUMENTS]
        if unsupported:
            raise ValueError(f"Unsupported instruments: {', '.join(unsupported)}.")
        if self.job_mode == "backing_track" and not unique:
            raise ValueError("Backing-track jobs must suppress at least one instrument.")
        return self


class ChordSpan(BaseModel):
    start_sec: float
    end_sec: float
    chord: str
    confidence: float


class AnalysisResult(BaseModel):
    source_title: str
    mode: JobMode
    bpm: Optional[float] = None
    bpm_confidence: Optional[float] = None
    time_signature: Optional[str] = None
    key: Optional[str] = None
    key_confidence: Optional[float] = None
    chords: List[ChordSpan] = Field(default_factory=list)
    progression_summary: List[str] = Field(default_factory=list)
    chart_bars: List[List[str]] = Field(default_factory=list)
    theory_notes: List[str] = Field(default_factory=list)
    tuning_suggestion: Optional[str] = None
    tuning_confidence: Optional[float] = None
    capo_suggestion: Optional[str] = None
    backing_track_url: Optional[str] = None
    backing_track_confidence: Optional[float] = None
    suppressed_instruments: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    request: CreateJobRequest
    created_at: datetime
    updated_at: datetime
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    supported_instruments: tuple[str, ...] = SUPPORTED_INSTRUMENTS
