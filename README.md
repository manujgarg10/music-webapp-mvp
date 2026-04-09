# AI Music Practice MVP

Local-first FastAPI app for guitar learners. Paste a public YouTube URL, choose an instrument to reduce/remove, and get:

- BPM with confidence
- key with confidence
- chords over time
- simplified chord progression summary
- downloadable backing track

The UI now separates lightweight song analysis from heavier backing-track generation:

- `Analyze Song`: key, BPM, chords, progression, theory notes
- `Create Backing Track`: render a practice mix with one or two stems suppressed

The MVP no longer attempts automatic lyric/chord overlays. Accurate lyrics require a licensed source or manual authoring, and the rough generated version was not good enough to keep.

## Current machine prerequisites

This workspace was started on a Mac that does **not** currently have the required machine tools installed. Before the app can run end-to-end, install:

1. Apple Command Line Tools
2. A package manager such as Homebrew
3. Apple Command Line Tools-compatible Python build support

## Suggested setup

```bash
/usr/bin/python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Tests

```bash
pytest
```

## Notes on backing tracks

The app uses Python-packaged `yt-dlp` and `imageio-ffmpeg`, so you do not need separate global installs for those tools. The backing-track workflow uses source separation internally but does not expose full stems in the UI. The first implementation is optimized for `guitar` removal. If Demucs or the selected model is unavailable, the job will fail with a clear error instead of silently returning a fake result.
