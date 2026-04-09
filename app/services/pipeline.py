from __future__ import annotations

from app.schemas import AnalysisResult, CreateJobRequest
from app.services.analysis import analyze
from app.services.ingest import download_audio, normalize_audio
from app.services.render import render_backing_track
from app.services.separation import SeparationError, separate_sources


def run_job(job_id: str, request: CreateJobRequest) -> AnalysisResult:
    downloaded_path, title = download_audio(job_id, str(request.youtube_url))
    normalized_path = normalize_audio(job_id, downloaded_path)

    warnings: list[str] = []
    theory_notes: list[str] = []
    bpm = None
    bpm_confidence = None
    time_signature = None
    key = None
    key_confidence = None
    chords = []
    progression_summary = []
    chart_bars = []
    tuning_suggestion = None
    tuning_confidence = None
    capo_suggestion = None
    backing_track_url = None
    backing_track_confidence = None

    if request.job_mode == "analysis":
        analysis = analyze(normalized_path)
        bpm = analysis.bpm
        bpm_confidence = analysis.bpm_confidence
        time_signature = analysis.time_signature
        key = analysis.key
        key_confidence = analysis.key_confidence
        chords = analysis.chords
        progression_summary = analysis.progression_summary
        chart_bars = analysis.chart_bars
        theory_notes = analysis.theory_notes
        tuning_suggestion = analysis.tuning_suggestion
        tuning_confidence = analysis.tuning_confidence
        capo_suggestion = analysis.capo_suggestion
    else:
        try:
            stem_dir = separate_sources(job_id, normalized_path)
            backing_track_path, backing_track_confidence = render_backing_track(
                job_id, stem_dir, request.instruments_to_suppress
            )
            backing_track_url = f"/api/artifacts/{job_id}/{backing_track_path.name}"
        except SeparationError as exc:
            warnings.append(str(exc))

    return AnalysisResult(
        source_title=title,
        mode=request.job_mode,
        bpm=bpm,
        bpm_confidence=bpm_confidence,
        time_signature=time_signature,
        key=key,
        key_confidence=key_confidence,
        chords=chords,
        progression_summary=progression_summary,
        chart_bars=chart_bars,
        theory_notes=theory_notes,
        tuning_suggestion=tuning_suggestion,
        tuning_confidence=tuning_confidence,
        capo_suggestion=capo_suggestion,
        backing_track_url=backing_track_url,
        backing_track_confidence=backing_track_confidence,
        suppressed_instruments=request.instruments_to_suppress,
        warnings=warnings,
    )
