from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
from scipy.signal import stft

from app.schemas import ChordSpan
from app.services.chord_engine import BaselineChordEngine, ChordWindow


PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR_TEMPLATE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_TEMPLATE = np.array([6.33, 2.68, 3.52, 5.38, 2.6, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

def clean_progression(chords: list[str]) -> list[str]:
    if not chords:
        return []

    cleaned = []

    # 1. Remove immediate duplicates
    for chord in chords:
        if not cleaned or chord != cleaned[-1]:
            cleaned.append(chord)

    # 2. Remove flicker (A → B → A)
    smoothed = []
    for i in range(len(cleaned)):
        if 0 < i < len(cleaned) - 1:
            if cleaned[i - 1] == cleaned[i + 1]:
                continue
        smoothed.append(cleaned[i])

    # 3. Keep it short/readable
    return smoothed[:12]

@dataclass
class AudioAnalysis:
    bpm: float
    bpm_confidence: float
    time_signature: str
    key: str
    key_confidence: float
    chords: list[ChordSpan]
    progression_summary: list[str]
    chart_bars: list[list[str]]
    theory_notes: list[str]
    tuning_suggestion: str
    tuning_confidence: float
    capo_suggestion: str


def load_audio(audio_path: Path, target_sample_rate: int = 22050, max_duration_sec: float = 180.0) -> tuple[np.ndarray, int]:
    audio, sample_rate = librosa.load(
        audio_path,
        sr=target_sample_rate,
        mono=True,
        duration=max_duration_sec,
    )
    return audio, sample_rate


def analyze(audio_path: Path) -> AudioAnalysis:
    audio, sample_rate = load_audio(audio_path)
    bpm, bpm_confidence = detect_bpm(audio, sample_rate)
    time_signature = detect_time_signature(audio, sample_rate, bpm)
    chords = detect_chords(audio, sample_rate)
    raw_progression = summarize_progression(chords)

    # Step 1: compress aggressively
    compressed = compress_chords(raw_progression)

    # Step 2: remove weak first chord noise (B before Bm)
    if len(compressed) > 1:
        if compressed[0].rstrip("m") == compressed[1].rstrip("m"):
            compressed = compressed[1:]

    # Step 3: HARD LIMIT to first 8 meaningful chords
    progression_summary = compressed[:8]

    chart_bars = build_chord_chart_bars(chords, progression_summary, bpm, time_signature, len(audio) / sample_rate)
    key, key_confidence, theory_notes = detect_key(audio, sample_rate, chords, progression_summary)
    tuning_suggestion, tuning_confidence = suggest_tuning(chords, progression_summary, key)
    capo_suggestion = suggest_capo(progression_summary)
    return AudioAnalysis(
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
    )


def detect_bpm(audio: np.ndarray, sample_rate: int, hop_length: int = 512) -> tuple[float, float]:
    onset_env = librosa.onset.onset_strength(y=audio, sr=sample_rate, hop_length=hop_length)
    raw_tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=sample_rate, hop_length=hop_length)
    raw_tempo = float(np.squeeze(raw_tempo))

    candidates = {round(raw_tempo, 2)}
    for factor in (0.5, 2.0):
        value = raw_tempo * factor
        if 45.0 <= value <= 190.0:
            candidates.add(round(value, 2))
    if raw_tempo > 110.0:
        halved = raw_tempo / 2.0
        if 45.0 <= halved <= 190.0:
            candidates.add(round(halved, 2))

    autocorr = librosa.autocorrelate(onset_env, max_size=len(onset_env))
    scores: list[tuple[float, float]] = []
    for tempo in sorted(candidates):
        lag = max(1, int(round(60.0 * sample_rate / (hop_length * tempo))))
        if lag >= len(autocorr):
            continue
        score = float(autocorr[lag])
        if 60.0 <= tempo <= 100.0:
            score *= 1.18
        elif tempo > 120.0:
            score *= 0.87
        scores.append((tempo, score))

    if not scores:
        return raw_tempo, 0.35

    scores.sort(key=lambda item: item[1], reverse=True)
    top_tempo, top_score = scores[0]
    runner_up = scores[1][1] if len(scores) > 1 else top_score * 0.5
    confidence = max(0.2, min(0.99, top_score / (top_score + runner_up + 1e-6)))
    if raw_tempo > 120.0 and abs(top_tempo - raw_tempo / 2.0) < 2.5 and 60.0 <= top_tempo <= 100.0:
        confidence = max(confidence, 0.82)
    return top_tempo, confidence


def detect_key(
    audio: np.ndarray,
    sample_rate: int,
    chords: list[ChordSpan],
    progression_summary: list[str],
) -> tuple[str, float, list[str]]:
    chroma = compute_chroma(audio, sample_rate, frame_size=4096, hop_length=2048)
    profile = chroma.mean(axis=1)

    chroma_candidates: list[tuple[str, str, float]] = []
    for shift, tonic in enumerate(PITCH_CLASSES):
        major_score = float(np.corrcoef(profile, np.roll(MAJOR_TEMPLATE, shift))[0, 1])
        minor_score = float(np.corrcoef(profile, np.roll(MINOR_TEMPLATE, shift))[0, 1])
        chroma_candidates.append((tonic, "major", major_score))
        chroma_candidates.append((tonic, "minor", minor_score))
    chroma_candidates.sort(key=lambda item: item[2], reverse=True)

    chord_candidates = score_keys_from_chords(chords, progression_summary)
    sorted_chord_candidates = sorted(chord_candidates.items(), key=lambda item: item[1], reverse=True)
    combined_candidates: list[tuple[str, str, float]] = []
    for tonic in PITCH_CLASSES:
        for mode in ("major", "minor"):
            chroma_score = next(score for cand_tonic, cand_mode, score in chroma_candidates if cand_tonic == tonic and cand_mode == mode)
            chord_score = chord_candidates.get((tonic, mode), 0.0)
            combined_score = 0.35 * chroma_score + 0.65 * chord_score
            combined_candidates.append((tonic, mode, combined_score))
    combined_candidates.sort(key=lambda item: item[2], reverse=True)

    top_tonic, top_mode, top_score = combined_candidates[0]
    runner_up = combined_candidates[1][2] if len(combined_candidates) > 1 else top_score * 0.7
    chord_best_score = sorted_chord_candidates[0][1] if sorted_chord_candidates else 0.0
    chord_runner_up = sorted_chord_candidates[1][1] if len(sorted_chord_candidates) > 1 else chord_best_score * 0.6
    confidence = max(
        0.4,
        min(
            0.99,
            0.55 + (top_score - runner_up) * 0.45 + max(0.0, chord_best_score - chord_runner_up) * 0.9,
        ),
    )
    top_root_names = {parse_chord(name)[0] for name in progression_summary[:8] if parse_chord(name)[0] is not None}
    dominant_name = PITCH_CLASSES[(PITCH_CLASSES.index(top_tonic) + 7) % 12]
    subdominant_name = PITCH_CLASSES[(PITCH_CLASSES.index(top_tonic) + 5) % 12]
    if {top_tonic, dominant_name, subdominant_name}.issubset(top_root_names):
        confidence = max(confidence, 0.84)

    chroma_best = chroma_candidates[0]
    theory_notes = [
        f"Chord progression evidence favors {format_key_label(top_tonic, top_mode)}.",
    ]
    if (top_tonic, top_mode) != (chroma_best[0], chroma_best[1]):
        theory_notes.append(
            f"Raw pitch profile suggested {format_key_label(chroma_best[0], chroma_best[1])}, "
            f"but chord-function validation overrode it."
        )
    return format_key_label(top_tonic, top_mode), confidence, theory_notes


def detect_time_signature(audio: np.ndarray, sample_rate: int, bpm: float) -> str:
    del audio, sample_rate, bpm
    return "4/4"


def detect_chords(
    audio: np.ndarray,
    sample_rate: int,
    hop_length: int = 2048,
    window_seconds: float = 2.0,
) -> list[ChordSpan]:
    chroma = compute_chroma(audio, sample_rate, frame_size=4096, hop_length=hop_length)
    frames_per_window = max(1, int(window_seconds * sample_rate / hop_length))
    windows: list[ChordWindow] = []

    for start_frame in range(0, chroma.shape[1], frames_per_window):
        end_frame = min(chroma.shape[1], start_frame + frames_per_window)
        window = chroma[:, start_frame:end_frame]
        start_sec = librosa.frames_to_time(start_frame, sr=sample_rate, hop_length=hop_length)
        end_sec = librosa.frames_to_time(end_frame, sr=sample_rate, hop_length=hop_length)
        windows.append(
            ChordWindow(
                start_sec=float(start_sec),
                end_sec=float(end_sec),
                chroma_vector=window.mean(axis=1),
            )
        )

    engine = BaselineChordEngine()
    spans = engine.detect(windows)
    for span in spans:
        span.confidence = max(0.45, min(0.92, span.confidence * 0.88))
    return spans


def summarize_progression(chords: list[ChordSpan]) -> list[str]:
    summary: list[str] = []
    for chord in chords:
        if chord.chord == "N":
            continue
        if not summary or summary[-1] != chord.chord:
            summary.append(chord.chord)
    return summary[:16]

def compress_chords(chords: list[str]) -> list[str]:
    """Collapse consecutive duplicates (stronger version)"""
    if not chords:
        return []

    result = [chords[0]]

    for chord in chords[1:]:
        if chord != result[-1]:
            result.append(chord)

    return result

def clean_progression(chords: list[str]) -> list[str]:
    if not chords:
        return []

    # 1. Remove immediate duplicates
    deduped = []
    for chord in chords:
        if not deduped or chord != deduped[-1]:
            deduped.append(chord)

    # 2. Normalize major/minor flicker (B vs Bm → Bm)
    normalized = []
    for chord in deduped:
        if normalized:
            prev = normalized[-1]
            if chord.rstrip("m") == prev.rstrip("m"):
                chord = chord.rstrip("m") + "m"
        normalized.append(chord)

    # 3. Collapse long repeats (Bm Bm Bm → Bm)
    collapsed = []
    for chord in normalized:
        if not collapsed or chord != collapsed[-1]:
            collapsed.append(chord)

    # 4. Remove weak starting noise (like stray B before Bm)
    if len(collapsed) >= 2:
        first, second = collapsed[0], collapsed[1]
        if first.rstrip("m") == second.rstrip("m"):
            collapsed = collapsed[1:]

    return collapsed[:8]

def extract_core_loop(chords: list[str]) -> list[str]:
    if len(chords) < 4:
        return chords

    best_pattern = chords
    best_score = 0

    # Try loop sizes from 3 to 6 (IMPORTANT: skip size=2)
    for size in range(3, 7):
        pattern = chords[:size]

        matches = 0
        total = 0

        for i in range(0, len(chords) - size, size):
            segment = chords[i:i+size]
            if segment == pattern:
                matches += 1
            total += 1

        if total > 0:
            score = matches / total

            # Prefer longer patterns slightly
            score += size * 0.05

            if score > best_score:
                best_score = score
                best_pattern = pattern

    return best_pattern

def build_chord_chart_bars(
    chords: list[ChordSpan],
    progression_summary: list[str],
    bpm: float,
    time_signature: str,
    duration_sec: float,
) -> list[list[str]]:
    beats_per_bar = int(time_signature.split("/")[0]) if "/" in time_signature else 4
    seconds_per_bar = (60.0 / max(bpm, 1.0)) * beats_per_bar
    total_bars = max(1, int(round(duration_sec / seconds_per_bar)))

    repeating_cycle = detect_repeating_cycle(progression_summary)
    if repeating_cycle:
        pattern_bars = cycle_to_bars(repeating_cycle)
        if pattern_bars:
            return [pattern_bars[index % len(pattern_bars)] for index in range(total_bars)]

    bars: list[list[str]] = []

    for bar_index in range(total_bars):
        start_sec = bar_index * seconds_per_bar
        end_sec = start_sec + seconds_per_bar
        overlapping = []
        for chord in chords:
            overlap_start = max(start_sec, chord.start_sec)
            overlap_end = min(end_sec, chord.end_sec)
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > 0.0 and chord.chord != "N":
                overlapping.append((overlap_start, overlap, chord.chord))
        if not overlapping:
            if bars:
                bars.append(bars[-1][:])
            else:
                bars.append(["N"])
            continue

        overlapping.sort(key=lambda item: item[0])
        bar_chords: list[str] = []
        for _, _, chord_name in overlapping:
            if not bar_chords or bar_chords[-1] != chord_name:
                bar_chords.append(chord_name)
        bars.append(bar_chords[:2] if bar_chords else ["N"])

    return bars


def detect_repeating_cycle(progression_summary: list[str]) -> list[str]:
    sequence = [chord for chord in progression_summary if chord != "N"]
    if len(sequence) in {4, 6, 8}:
        return sequence
    if len(sequence) < 8:
        return []

    best_cycle: list[str] = []
    best_score = 0.0
    max_length = min(8, len(sequence) // 2)
    for length in range(4, max_length + 1):
        cycle = sequence[:length]
        comparisons = 0
        matches = 0
        for index, chord in enumerate(sequence[length:length * 3], start=length):
            comparisons += 1
            if chord == cycle[index % length]:
                matches += 1
        if comparisons == 0:
            continue
        score = matches / comparisons
        if score > best_score:
            best_score = score
            best_cycle = cycle

    return best_cycle if best_score >= 0.72 else []


def cycle_to_bars(cycle: list[str]) -> list[list[str]]:
    if len(cycle) == 4:
        return [[cycle[0]], [cycle[1]], [cycle[2]], [cycle[3]]]
    if len(cycle) == 6:
        return [[cycle[0], cycle[1]], [cycle[2]], [cycle[3], cycle[4]], [cycle[5]]]
    if len(cycle) == 8:
        return [[cycle[0], cycle[1]], [cycle[2], cycle[3]], [cycle[4], cycle[5]], [cycle[6], cycle[7]]]
    return []


def compute_chroma(
    audio: np.ndarray,
    sample_rate: int,
    frame_size: int = 4096,
    hop_length: int = 2048,
) -> np.ndarray:
    freqs, _, spectrum = stft(
        audio,
        fs=sample_rate,
        window="hann",
        nperseg=frame_size,
        noverlap=frame_size - hop_length,
        boundary=None,
        padded=False,
    )
    magnitude = np.abs(spectrum)
    chroma = np.zeros((12, magnitude.shape[1]), dtype=np.float32)

    valid = freqs >= 27.5
    valid_freqs = freqs[valid]
    valid_magnitude = magnitude[valid]
    if valid_freqs.size == 0:
        return chroma

    midi = np.rint(69 + 12 * np.log2(valid_freqs / 440.0)).astype(int)
    pitch_classes = np.mod(midi, 12)

    for bin_index, pitch_class in enumerate(pitch_classes):
        chroma[pitch_class] += valid_magnitude[bin_index]

    chroma /= np.maximum(chroma.sum(axis=0, keepdims=True), 1e-6)
    return chroma


def score_keys_from_chords(
    chords: list[ChordSpan],
    progression_summary: list[str],
) -> dict[tuple[str, str], float]:
    chord_labels = [chord.chord for chord in chords if chord.chord != "N"]
    summary = progression_summary or chord_labels
    scores: dict[tuple[str, str], float] = {}

    for tonic in PITCH_CLASSES:
        major_scale = scale_pitch_classes(tonic, "major")
        minor_scale = scale_pitch_classes(tonic, "minor")
        scores[(tonic, "major")] = score_key_candidate(summary, tonic, "major", major_scale)
        scores[(tonic, "minor")] = score_key_candidate(summary, tonic, "minor", minor_scale)

    return scores


def scale_pitch_classes(tonic: str, mode: str) -> list[int]:
    intervals = [0, 2, 4, 5, 7, 9, 11] if mode == "major" else [0, 2, 3, 5, 7, 8, 10]
    tonic_index = PITCH_CLASSES.index(tonic)
    return [(tonic_index + interval) % 12 for interval in intervals]


def score_key_candidate(summary: list[str], tonic: str, mode: str, scale: list[int]) -> float:
    tonic_index = PITCH_CLASSES.index(tonic)
    dominant_index = (tonic_index + 7) % 12
    subdominant_index = (tonic_index + 5) % 12
    score = 0.0

    for index, chord_name in enumerate(summary):
        root, quality = parse_chord(chord_name)
        if root is None:
            continue
        root_index = PITCH_CLASSES.index(root)
        if root_index not in scale:
            score -= 0.4
            continue
        score += 0.8
        if root_index == tonic_index:
            score += 0.45 if index == 0 else 0.3
        if root_index == dominant_index:
            score += 0.2
        if root_index == subdominant_index:
            score += 0.15
        if mode == "major" and quality == "major" and root_index in {tonic_index, dominant_index, subdominant_index}:
            score += 0.1
        if mode == "minor" and quality == "minor" and root_index == tonic_index:
            score += 0.2
    return score / max(len(summary), 1)


def parse_chord(chord_name: str) -> tuple[str | None, str]:
    if chord_name == "N":
        return None, "unknown"
    if chord_name.endswith("m"):
        return chord_name[:-1], "minor"
    return chord_name, "major"


def format_key_label(tonic: str, mode: str) -> str:
    return tonic if mode == "major" else f"{tonic}m"


def build_lyrics_guide(lyrics_text: str, progression_summary: list[str]) -> tuple[str, str]:
    cleaned_sections = [section.strip() for section in lyrics_text.strip().split("\n\n") if section.strip()]
    if not cleaned_sections:
        return "", "No lyrics text was supplied."

    progression_line = "  ".join(progression_summary[:8] or ["No stable progression detected"])
    blocks = []
    for section in cleaned_sections:
        blocks.append(f"{progression_line}\n{section}")
    guide = "\n\n".join(blocks)
    note = (
        "This is a rough practice guide using the detected progression above each lyric section. "
        "It is not line-accurate or syllable-aligned. For exact lyric/chord overlays, we should add a licensed lyrics source."
    )
    return guide, note


def suggest_tuning(chords: list[ChordSpan], progression_summary: list[str], key_label: str) -> tuple[str, float]:
    roots = {parse_chord(chord_name)[0] for chord_name in progression_summary if parse_chord(chord_name)[0] is not None}
    if roots.intersection({"F#", "C#", "G#", "D#", "A#"}):
        return "Standard tuning (E A D G B E) is still likely, but this song may benefit from a capo rather than retuning.", 0.63
    if key_label in {"G", "D", "A", "E", "C", "Am", "Em"}:
        return "Standard tuning (E A D G B E)", 0.9
    if roots.issubset({"G", "D", "Am", "C", "Em", "Bm"}):
        return "Standard tuning (E A D G B E)", 0.92
    return "Standard tuning (E A D G B E) is the default recommendation.", 0.78


OPEN_CHORD_SHAPES = {
    "C", "D", "E", "G", "A", "Am", "Em", "Dm", "D7", "A7", "E7", "Cadd9", "Gsus4", "Dsus4"
}


def suggest_capo(progression_summary: list[str]) -> str:
    filtered = [chord for chord in progression_summary if chord != "N"]
    if not filtered:
        return "No capo suggestion available."
    if all(chord in OPEN_CHORD_SHAPES for chord in filtered[:8]):
        return "No capo needed. The detected progression already sits well in open-position shapes."

    best_capo = 0
    best_score = -1
    best_shapes: list[str] = filtered
    for capo in range(0, 8):
        transposed = [transpose_chord_name(chord, capo) for chord in filtered]
        score = sum(1 for chord in transposed if chord in OPEN_CHORD_SHAPES)
        if capo == 0:
            score += 1.5
        if score > best_score:
            best_score = score
            best_capo = capo
            best_shapes = transposed

    if best_capo == 0:
        return "No capo needed. The detected progression already sits well in open-position shapes."
    shown_shapes = " - ".join(best_shapes[:4])
    return f"Try capo {best_capo} if you want easier open shapes. Relative chord shapes start like: {shown_shapes}."


def transpose_chord_name(chord_name: str, capo: int) -> str:
    root, quality = parse_chord(chord_name)
    if root is None:
        return chord_name
    root_index = PITCH_CLASSES.index(root)
    transposed_root = PITCH_CLASSES[(root_index - capo) % 12]
    return transposed_root if quality == "major" else f"{transposed_root}m"
