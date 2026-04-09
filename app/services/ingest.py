from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from app.config import DOWNLOADS_DIR, NORMALIZED_DIR
from app.services.tools import ffmpeg_binary


class IngestError(RuntimeError):
    pass


def validate_youtube_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise IngestError("YouTube URL must start with http or https.")
    if not parsed.netloc:
        raise IngestError("YouTube URL is missing a host.")
    if "youtube.com" not in parsed.netloc and "youtu.be" not in parsed.netloc:
        raise IngestError("Only public YouTube URLs are supported in this MVP.")


def download_audio(job_id: str, youtube_url: str) -> tuple[Path, str]:
    validate_youtube_url(youtube_url)

    output_template = str(DOWNLOADS_DIR / f"{job_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best/18",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "sleep_interval_requests": 1.0,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
    except Exception as exc:  # noqa: BLE001
        raise IngestError(str(exc)) from exc

    title = info.get("title") or "Unknown Title"
    requested = info.get("requested_downloads") or []
    downloaded = None
    for item in requested:
        filepath = item.get("filepath")
        if filepath:
            candidate = Path(filepath)
            if candidate.exists():
                downloaded = candidate
                break

    if downloaded is None:
        downloaded = next(DOWNLOADS_DIR.glob(f"{job_id}.*"), None)
    if downloaded is None:
        raise IngestError(
            "Audio download finished but no output file was found in data/downloads. "
            "This usually means yt-dlp could fetch metadata but could not write or post-process the audio."
        )
    return downloaded, title


def normalize_audio(job_id: str, input_path: Path, sample_rate: int = 44100) -> Path:
    output_path = NORMALIZED_DIR / f"{job_id}.wav"
    cmd = [
        ffmpeg_binary(),
        "-y",
        "-i",
        str(input_path),
        "-ar",
        str(sample_rate),
        "-ac",
        "2",
        str(output_path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        message = completed.stderr.strip() or "ffmpeg failed while normalizing audio."
        raise IngestError(message)
    return output_path
