"""Summarize JSONL sessions and render a latency/timeline plot.

Interaction metrics (counts, rates, carry times) are reproducible from a
recorded session; latency numbers depend on the machine that ran it.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

TERMINAL_EVENTS = {"dropped", "cancelled"}


def load_session(path: str | Path) -> tuple[list[dict], list[dict]]:
    """Return (frames, events) from a JSONL session file."""
    frames: list[dict] = []
    events: list[dict] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            (frames if record.get("type") == "frame" else events).append(record)
    return frames, events


def _percentile(values: list[float], q: float) -> float:
    return float(np.percentile(values, q)) if values else 0.0


def summarize(frames: list[dict], events: list[dict]) -> dict:
    grabs = [event for event in events if event["event"] == "grabbed"]
    drops = [event for event in events if event["event"] == "dropped"]
    cancels = [event for event in events if event["event"] == "cancelled"]
    scored = [event for event in drops if event.get("zone")]

    carry_times: list[float] = []
    grab_start: float | None = None
    for event in events:
        if event["event"] == "grabbed":
            grab_start = event["t"]
        elif event["event"] in TERMINAL_EVENTS and grab_start is not None:
            if event["event"] == "dropped":
                carry_times.append(event["t"] - grab_start)
            grab_start = None

    drag_frames = [frame for frame in frames if frame.get("state") == "DRAG"]
    occluded = [frame for frame in drag_frames if frame.get("linked", 0) == 0]
    hand_ms = [frame.get("hand_ms", 0.0) for frame in frames]
    detect_ms = [frame.get("detect_ms", 0.0) for frame in frames]

    return {
        "frames": len(frames),
        "duration_s": round(frames[-1]["t"] - frames[0]["t"], 3) if frames else 0.0,
        "grabs": len(grabs),
        "drops": len(drops),
        "scored": len(scored),
        "cancels": len(cancels),
        "grab_success_rate": len(drops) / len(grabs) if grabs else 0.0,
        "drop_accuracy": len(scored) / len(drops) if drops else 0.0,
        "carry_median_s": round(float(np.median(carry_times)), 3) if carry_times else 0.0,
        "drag_frames": len(drag_frames),
        "occlusion_rate": len(occluded) / len(drag_frames) if drag_frames else 0.0,
        "hand_p50_ms": _percentile(hand_ms, 50),
        "hand_p95_ms": _percentile(hand_ms, 95),
        "detect_p50_ms": _percentile(detect_ms, 50),
        "detect_p95_ms": _percentile(detect_ms, 95),
    }


def render_plot(frames: list[dict], events: list[dict], path: str | Path) -> Path:
    """Draw hand/detect latency over frames plus event ticks. Returns the path."""
    width, height, margin = 960, 420, 50
    canvas = np.full((height, width, 3), 25, dtype=np.uint8)
    path = Path(path)

    if not frames:
        cv2.imwrite(str(path), canvas)
        return path

    hand = np.array([frame.get("hand_ms", 0.0) for frame in frames])
    detect = np.array([frame.get("detect_ms", 0.0) for frame in frames])
    peak = max(float(hand.max()) if hand.size else 0.0,
               float(detect.max()) if detect.size else 0.0, 1.0)

    def to_points(values: np.ndarray) -> np.ndarray:
        count = len(values)
        xs = margin + np.arange(count) * (width - 2 * margin) / max(count - 1, 1)
        ys = height - margin - values / peak * (height - 2 * margin)
        return np.stack([xs, ys], axis=1).astype(np.int32)

    cv2.polylines(canvas, [to_points(hand)], False, (0, 200, 0), 2)
    cv2.polylines(canvas, [to_points(detect)], False, (0, 200, 255), 2)
    cv2.line(canvas, (margin, height - margin), (width - margin, height - margin), (120, 120, 120), 1)
    cv2.putText(canvas, f"peak {peak:.1f} ms", (margin, margin - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    cv2.putText(canvas, "hand ms", (width - 260, margin - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1)
    cv2.putText(canvas, "detect ms", (width - 150, margin - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

    event_colors = {"grabbed": (255, 128, 0), "cancelled": (0, 0, 255)}
    last_frame = max(len(frames) - 1, 1)
    for event in events:
        x = int(margin + event["frame"] / last_frame * (width - 2 * margin))
        color = event_colors.get(event["event"], (0, 255, 0))
        cv2.line(canvas, (x, height - margin), (x, height - margin + 12), color, 2)

    cv2.imwrite(str(path), canvas)
    return path
