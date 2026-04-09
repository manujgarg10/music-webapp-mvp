from __future__ import annotations

import shutil

import imageio_ffmpeg


def ffmpeg_binary() -> str:
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

