from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.schemas import ChordSpan


PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class ChordWindow:
    start_sec: float
    end_sec: float
    chroma_vector: np.ndarray


class ChordEngine:
    def detect(self, windows: list[ChordWindow]) -> list[ChordSpan]:
        raise NotImplementedError


class BaselineChordEngine(ChordEngine):
    def detect(self, windows: list[ChordWindow]) -> list[ChordSpan]:
        spans: list[ChordSpan] = []
        current_label = None
        current_confidence = 0.0
        current_start = 0.0
        current_end = 0.0

        for window in windows:
            chord_label, confidence = self._classify(window.chroma_vector)
            if current_label is None:
                current_label = chord_label
                current_confidence = confidence
                current_start = window.start_sec
                current_end = window.end_sec
                continue

            if chord_label == current_label:
                current_end = window.end_sec
                current_confidence = max(current_confidence, confidence)
                continue

            spans.append(
                ChordSpan(
                    start_sec=current_start,
                    end_sec=current_end,
                    chord=current_label,
                    confidence=current_confidence,
                )
            )
            current_label = chord_label
            current_confidence = confidence
            current_start = window.start_sec
            current_end = window.end_sec

        if current_label is not None:
            spans.append(
                ChordSpan(
                    start_sec=current_start,
                    end_sec=current_end,
                    chord=current_label,
                    confidence=current_confidence,
                )
            )

        return spans

    def _classify(self, chroma_vector: np.ndarray) -> tuple[str, float]:
        if np.allclose(chroma_vector.sum(), 0.0):
            return "N", 0.0

        norm = chroma_vector / (np.linalg.norm(chroma_vector) + 1e-6)
        best_label = "N"
        best_score = -1.0

        major_template = np.zeros(12)
        major_template[[0, 4, 7]] = 1.0
        minor_template = np.zeros(12)
        minor_template[[0, 3, 7]] = 1.0

        for idx, note in enumerate(PITCH_CLASSES):
            maj_score = float(np.dot(norm, np.roll(major_template, idx)))
            min_score = float(np.dot(norm, np.roll(minor_template, idx)))
            if maj_score > best_score:
                best_label = note
                best_score = maj_score
            if min_score > best_score:
                best_label = f"{note}m"
                best_score = min_score

        confidence = max(0.0, min(1.0, best_score))
        if confidence < 0.45:
            return "N", confidence
        return best_label, confidence

