from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.config import RENDERED_DIR
from app.services.separation import SeparationError
from app.services.tools import ffmpeg_binary


def render_backing_track(job_id: str, stem_dir: Path, instruments_to_suppress: list[str]) -> tuple[Path, float]:
    suppressed = set(instruments_to_suppress)
    remaining_stems = []
    removed_found = []
    for stem_file in stem_dir.glob("*.wav"):
        if stem_file.stem in suppressed:
            removed_found.append(stem_file.stem)
            continue
        remaining_stems.append(stem_file)

    missing = sorted(suppressed.difference(removed_found))
    if missing:
        available = ", ".join(sorted(stem.stem for stem in stem_dir.glob("*.wav")))
        raise SeparationError(
            f"No stems were produced for: {', '.join(missing)}. Available stems: {available or 'none'}."
        )
    if not remaining_stems:
        raise SeparationError("Suppressing all available stems would leave an empty backing track.")

    suffix = "-".join(sorted(suppressed))
    output_path = RENDERED_DIR / f"{job_id}-{suffix}-suppressed.wav"
    if len(remaining_stems) == 1:
        shutil.copyfile(remaining_stems[0], output_path)
    else:
        cmd = [ffmpeg_binary(), "-y"]
        for stem_path in remaining_stems:
            cmd.extend(["-i", str(stem_path)])
        cmd.extend(
            [
                "-filter_complex",
                f"amix=inputs={len(remaining_stems)}:normalize=0",
                str(output_path),
            ]
        )
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            message = completed.stderr.strip() or "ffmpeg failed while rendering the backing track."
            raise SeparationError(message)

    confidence = 0.88 - max(0, len(suppressed) - 1) * 0.1
    return output_path, max(0.5, confidence)
