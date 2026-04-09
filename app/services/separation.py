from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.config import SEPARATED_DIR


class SeparationError(RuntimeError):
    pass


MODEL_NAME = "htdemucs_6s"
SUPPORTED_STEMS = {"vocals", "bass", "drums", "guitar", "other", "piano"}


def separate_sources(job_id: str, normalized_audio_path: Path) -> Path:
    normalized_audio_path = Path(normalized_audio_path)
    output_root = SEPARATED_DIR / job_id
    output_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "demucs.separate",
        "-n",
        MODEL_NAME,
        "-o",
        str(output_root),
        str(normalized_audio_path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Demucs separation failed."
        raise SeparationError(message)

    track_dir = output_root / MODEL_NAME / normalized_audio_path.stem
    if not track_dir.exists():
        raise SeparationError("Demucs finished but no separated stem directory was produced.")
    return track_dir
