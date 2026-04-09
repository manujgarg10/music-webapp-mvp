from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import AnalysisResult, ChordSpan, CreateJobRequest
from app.services import ingest
from app.services.analysis import build_chord_chart_bars, detect_repeating_cycle, format_key_label, suggest_capo
from app.services.jobs import job_store


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "guitar" in payload["supported_instruments"]


def test_create_analysis_job_enqueues_work(monkeypatch) -> None:
    captured = {}

    def fake_start(job_id: str) -> None:
        captured["job_id"] = job_id

    monkeypatch.setattr(job_store, "start_background_run", fake_start)

    response = client.post(
        "/api/jobs",
        json={
            "youtube_url": "https://www.youtube.com/watch?v=test123",
            "job_mode": "analysis",
            "instruments_to_suppress": ["guitar"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["request"]["job_mode"] == "analysis"
    assert captured["job_id"] == payload["job_id"]


def test_request_rejects_more_than_two_suppressed_stems() -> None:
    response = client.post(
        "/api/jobs",
        json={
            "youtube_url": "https://www.youtube.com/watch?v=test123",
            "job_mode": "backing_track",
            "instruments_to_suppress": ["guitar", "vocals", "bass"],
        },
    )
    assert response.status_code == 422


def test_get_artifact_returns_file(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "example.wav"
    artifact.write_bytes(b"wav-data")
    monkeypatch.setattr("app.main.RENDERED_DIR", tmp_path)

    response = client.get("/api/artifacts/job-1/example.wav")
    assert response.status_code == 200


def test_completed_analysis_job_shape() -> None:
    job = job_store.create(
        request=CreateJobRequest(
            youtube_url="https://www.youtube.com/watch?v=test123",
            job_mode="analysis",
            instruments_to_suppress=["guitar"],
        )
    )
    result = AnalysisResult(
        source_title="Song",
        mode="analysis",
        bpm=72.0,
        bpm_confidence=0.82,
        time_signature="4/4",
        key="G",
        key_confidence=0.88,
        chords=[ChordSpan(start_sec=0.0, end_sec=2.0, chord="G", confidence=0.82)],
        progression_summary=["G", "D", "Am", "C"],
        chart_bars=[["G"], ["D"], ["Am"], ["C"]],
        theory_notes=["Chord progression evidence favors G."],
        tuning_suggestion="Standard tuning (E A D G B E)",
        tuning_confidence=0.9,
        capo_suggestion="No capo needed.",
        warnings=[],
    )
    job_store.update(job.job_id, status="completed", result=result)

    response = client.get(f"/api/jobs/{job.job_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["key"] == "G"
    assert payload["result"]["progression_summary"] == ["G", "D", "Am", "C"]
    assert payload["result"]["mode"] == "analysis"


def test_download_audio_uses_generated_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ingest, "DOWNLOADS_DIR", tmp_path)

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, youtube_url, download):
            output = tmp_path / "job-123.mp4"
            output.write_bytes(b"audio")
            return {
                "title": "Downloaded Song",
                "requested_downloads": [{"filepath": str(output)}],
            }

    monkeypatch.setattr(ingest, "YoutubeDL", FakeYoutubeDL)

    path, title = ingest.download_audio("job-123", "https://www.youtube.com/watch?v=test123")
    assert path == tmp_path / "job-123.mp4"
    assert title == "Downloaded Song"


def test_format_key_label() -> None:
    assert format_key_label("G", "major") == "G"
    assert format_key_label("E", "minor") == "Em"


def test_suggest_capo_prefers_open_shapes() -> None:
    suggestion = suggest_capo(["G", "D", "Am", "C"])
    assert "No capo needed" in suggestion


def test_build_chord_chart_bars_estimates_full_form() -> None:
    chords = [
        ChordSpan(start_sec=0.0, end_sec=3.3, chord="G", confidence=0.8),
        ChordSpan(start_sec=3.3, end_sec=6.6, chord="D", confidence=0.8),
        ChordSpan(start_sec=6.6, end_sec=9.9, chord="Am", confidence=0.8),
        ChordSpan(start_sec=9.9, end_sec=13.2, chord="C", confidence=0.8),
    ]
    bars = build_chord_chart_bars(chords, ["G", "D", "Am", "G", "D", "C"], bpm=72.0, time_signature="4/4", duration_sec=13.2)
    assert len(bars) == 4
    assert bars[0] == ["G", "D"]
    assert bars[1] == ["Am"]


def test_detect_repeating_cycle_finds_six_chord_loop() -> None:
    cycle = detect_repeating_cycle(["G", "D", "Am", "G", "D", "C", "G", "D", "Am", "G", "D", "C"])
    assert cycle == ["G", "D", "Am", "G", "D", "C"]
