"""Multimodal feedback: audio tones, drop flashes, and the onboarding hint.

Pseudo-haptic cues (Kim & Xiong 2021) are the protrusion on hover and the hit
effect on drop, rendered by the app; this module owns the sounds and the
expanding flash rings. Audio degrades to silence when no device is available
(CI, headless), and one failed playback disables audio for the session.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import cv2
import numpy as np

SAMPLE_RATE = 44100
AMPLITUDE = 0.4

SOUNDS: dict[str, list[tuple[float, float]]] = {
    "grab": [(880.0, 0.06)],
    "success": [(523.25, 0.06), (783.99, 0.1)],
    "miss": [(220.0, 0.12)],
}

Color = tuple[int, int, int]
Point = tuple[int, int]


def tone_samples(
    freq: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE,
    amplitude: float = AMPLITUDE,
) -> np.ndarray:
    """One sine note with 5 ms fades so playback has no clicks."""
    count = int(sample_rate * duration)
    t = np.arange(count) / sample_rate
    wave = np.sin(2.0 * math.pi * freq * t) * amplitude
    fade = min(count // 10, int(0.005 * sample_rate))
    if fade > 0:
        wave[:fade] *= np.linspace(0.0, 1.0, fade)
        wave[-fade:] *= np.linspace(1.0, 0.0, fade)
    return wave.astype(np.float32)


def tone_sequence(notes: list[tuple[float, float]], sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    if not notes:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate([tone_samples(freq, duration, sample_rate) for freq, duration in notes])


@dataclass
class Flash:
    point: Point
    color: Color
    started: float
    duration: float = 0.45


class Feedback:
    def __init__(self, audio: bool = True, sample_rate: int = SAMPLE_RATE):
        self.onboarding = True
        self._sample_rate = sample_rate
        self._flashes: list[Flash] = []
        self._sd = None
        if audio:
            try:
                import sounddevice as sd

                self._sd = sd
            except Exception:
                self._sd = None

    @property
    def audio_available(self) -> bool:
        return self._sd is not None

    def play(self, name: str) -> None:
        if self._sd is None:
            return
        try:
            self._sd.play(tone_sequence(SOUNDS[name], self._sample_rate), self._sample_rate)
        except Exception:
            self._sd = None  # ponytail: a dead audio device disables sound for the session

    def flash(self, point: Point, color: Color, now: float | None = None, duration: float = 0.45) -> None:
        self._flashes.append(
            Flash(point, color, time.perf_counter() if now is None else now, duration)
        )

    def mark_onboarded(self) -> None:
        self.onboarding = False

    def draw_flashes(self, frame: np.ndarray, now: float) -> np.ndarray:
        self._flashes = [f for f in self._flashes if now - f.started < f.duration]
        for flash in self._flashes:
            progress = (now - flash.started) / flash.duration
            radius = int(8 + 70 * progress)
            thickness = max(1, int(4 - 3 * progress))
            cv2.circle(frame, flash.point, radius, flash.color, thickness)
        return frame

    def draw_onboarding(self, frame: np.ndarray, now: float) -> np.ndarray:
        if not self.onboarding:
            return frame
        height, width = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (width // 2 - 280, 12), (width // 2 + 280, 108), (25, 25, 25), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        pulse = 0.5 + 0.5 * math.sin(now * 3.0)
        accent = (0, int(180 + 75 * pulse), 255)
        lines = (
            "Pinch to grab",
            "Open your hand to drop",
            "Carry objects into a zone to score",
        )
        for i, text in enumerate(lines):
            cv2.putText(
                frame, text, (width // 2 - 260, 44 + i * 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, accent, 2,
            )
        return frame
