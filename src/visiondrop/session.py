"""JSONL session recorder for evaluation runs.

One JSON object per line: `{"type": "frame", ...}` for per-frame state and
latencies, `{"type": "event", ...}` for interaction events (grabbed, dropped,
cancelled). Replay runs use video-time timestamps, so re-running the same file
reproduces the same `t` values and interaction metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

Point = tuple[float, float]


class SessionRecorder:
    def __init__(self, path: str | Path | None):
        self.path = Path(path).expanduser() if path else None
        self._handle = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.path.open("w", encoding="utf-8")

    @property
    def enabled(self) -> bool:
        return self._handle is not None

    def _write(self, record: dict) -> None:
        if self._handle is not None:
            self._handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    def frame(
        self,
        index: int,
        timestamp: float,
        state: str,
        cursor: Point | None,
        hands: int,
        objects: int,
        linked: int,
        hand_ms: float,
        detect_ms: float,
        fps: float,
    ) -> None:
        self._write(
            {
                "type": "frame",
                "frame": index,
                "t": round(timestamp, 4),
                "state": state,
                "cursor": [round(float(v), 1) for v in cursor] if cursor else None,
                "hands": hands,
                "objects": objects,
                "linked": linked,
                "hand_ms": round(hand_ms, 2),
                "detect_ms": round(detect_ms, 2),
                "fps": round(fps, 1),
            }
        )

    def event(self, index: int, timestamp: float, name: str, **details) -> None:
        self._write(
            {"type": "event", "frame": index, "t": round(timestamp, 4), "event": name, **details}
        )

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "SessionRecorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
