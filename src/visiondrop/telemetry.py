"""Lightweight telemetry: FPS, latency, and landmark record/replay.

Recording landmark streams makes the whole gesture pipeline reproducible: a
session can be replayed in tests to catch regressions in filters or FSM logic
without a camera, and it is the dataset used to calibrate thresholds.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

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


class V2Writer:
    """Streams the Swift engine's v2 session format, one flushed line per frame.

    This is how the Swift engine runs live off macOS, where Apple Vision does
    not exist: ``visiondrop run --emit-v2 | visiondrop-cli replay - --verbose``.
    Everything that differs between the two trackers is converted here and
    nowhere else: y flips to Vision's bottom-left origin, MediaPipe's depth is
    dropped (SRS CON-5), and the hand score stands in for per-joint confidence,
    which MediaPipe does not report.
    """

    TRACKER = "mediapipe.hands.python"

    def __init__(
        self,
        stream: TextIO,
        *,
        camera_size: tuple[int, int],
        fps: float,
        mirrored: bool,
        screen_size: tuple[int, int],
        camera_id: str = "opencv",
        started: datetime | None = None,
    ) -> None:
        self._stream = stream
        self._t0: float | None = None
        self._last_t = 0.0
        # Swift's ISO-8601 decoder rejects fractional seconds.
        started = (started or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._emit(
            {
                "type": "header",
                "version": 2,
                "tracker": self.TRACKER,
                "camera": {
                    "id": camera_id,
                    "width": int(camera_size[0]),
                    "height": int(camera_size[1]),
                    "fps": float(fps),
                    "mirrored": bool(mirrored),
                },
                "displays": [
                    {
                        "id": 1,
                        "bounds": [0, 0, int(screen_size[0]), int(screen_size[1])],
                        "scale": 1.0,
                        "primary": True,
                    }
                ],
                "started": started,
                "video": None,
            }
        )

    def write(self, observation: FrameObservation) -> None:
        if self._t0 is None:
            self._t0 = observation.timestamp_s
        # The reader rejects a frame that goes back in time and stops. The camera
        # clock is monotonic, so this only keeps one bad stamp from ending a session.
        t = max(self._last_t, round(observation.timestamp_s - self._t0, 6))
        self._last_t = t
        self._emit({"type": "frame", "t": t, "hands": [v2_hand(hand) for hand in observation.hands]})

    def _emit(self, record: dict) -> None:
        self._stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        self._stream.flush()


def v2_hand(hand: HandObservation) -> dict:
    """One MediaPipe hand as a v2 hand: 21 ``[x, y, confidence]`` points in Vision space."""
    landmarks = np.asarray(hand.landmarks, dtype=float)
    if landmarks.ndim != 2 or landmarks.shape[0] != 21 or landmarks.shape[1] < 2:
        raise ValueError(f"expected 21 landmarks, got shape {landmarks.shape}")
    score = float(hand.score)
    confidence = min(max(score, 0.0), 1.0) if math.isfinite(score) else 0.0
    label = str(hand.handedness).lower()
    return {
        "handedness": label if label in ("left", "right") else "unknown",
        "score": confidence,
        # A non-finite coordinate is a joint the tracker did not really see:
        # report it missing rather than as a point (SRS DAT-5).
        "points": [
            [round(float(x), 6), round(1.0 - float(y), 6), confidence]
            if math.isfinite(x) and math.isfinite(y)
            else None
            for x, y in landmarks[:, :2]
        ],
    }


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
