"""Lightweight telemetry: FPS, latency, and landmark record/replay.

Recording landmark streams makes the whole gesture pipeline reproducible: a
session can be replayed in tests to catch regressions in filters or FSM logic
without a camera, and it is the dataset used to calibrate thresholds.
"""

from __future__ import annotations

import json
import statistics
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .tracking import FrameObservation, HandObservation


class FPSCounter:
    def __init__(self, window: int = 30) -> None:
        self._times: deque[float] = deque(maxlen=window)

    def tick(self, timestamp_s: float) -> float:
        self._times.append(timestamp_s)
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / span if span > 0 else 0.0


@dataclass
class LatencyStats:
    mean_ms: float
    p95_ms: float
    samples: int


class LatencyMeter:
    def __init__(self, window: int = 120) -> None:
        self._values: deque[float] = deque(maxlen=window)

    def record(self, milliseconds: float) -> None:
        self._values.append(milliseconds)

    def stats(self) -> LatencyStats:
        if not self._values:
            return LatencyStats(0.0, 0.0, 0)
        ordered = sorted(self._values)
        index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
        return LatencyStats(
            mean_ms=statistics.fmean(ordered),
            p95_ms=ordered[index],
            samples=len(ordered),
        )


class JsonlRecorder:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._file = None

    def __enter__(self) -> "JsonlRecorder":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8")
        return self

    def write(self, observation: FrameObservation) -> None:
        assert self._file is not None
        record = {
            "t": observation.timestamp_s,
            "hands": [
                {
                    "landmarks": hand.landmarks.tolist(),
                    "world": hand.world_landmarks.tolist()
                    if hand.world_landmarks is not None
                    else None,
                    "handedness": hand.handedness,
                    "score": hand.score,
                }
                for hand in observation.hands
            ],
        }
        self._file.write(json.dumps(record) + "\n")

    def __exit__(self, *exc: object) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


def load_recording(path: str | Path) -> list[FrameObservation]:
    observations: list[FrameObservation] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            hands = tuple(
                HandObservation(
                    landmarks=np.array(entry["landmarks"], dtype=float),
                    world_landmarks=(
                        np.array(entry["world"], dtype=float)
                        if entry.get("world") is not None
                        else None
                    ),
                    handedness=entry.get("handedness", "Unknown"),
                    score=float(entry.get("score", 0.0)),
                )
                for entry in record.get("hands", [])
            )
            observations.append(
                FrameObservation(timestamp_s=float(record["t"]), hands=hands)
            )
    return observations
