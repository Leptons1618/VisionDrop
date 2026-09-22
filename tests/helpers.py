"""Deterministic synthetic hand landmarks for tests.

A hand is defined by a few anchor points; the remaining MediaPipe landmarks are
interpolated. Poses are rigid transforms of the same hand, so extension and
pinch features must be invariant under rotation.
"""

from __future__ import annotations

import numpy as np

WRIST = (0.50, 0.88)

THUMB = {
    "cmc": (0.47, 0.82),
    "mcp": (0.45, 0.78),
    "ip": (0.40, 0.74),
    "tip_open": (0.34, 0.70),
    "tip_pinch": (0.525, 0.535),
    "tip_middle_pinch": (0.505, 0.545),
}

FINGERS = {
    "index": {
        "mcp": (0.53, 0.70),
        "pip": (0.53, 0.62),
        "tip": (0.53, 0.54),
        "tip_curled": (0.53, 0.68),
    },
    "middle": {
        "mcp": (0.50, 0.69),
        "pip": (0.50, 0.60),
        "tip": (0.50, 0.51),
        "tip_curled": (0.50, 0.66),
    },
    "ring": {
        "mcp": (0.47, 0.70),
        "pip": (0.47, 0.62),
        "tip": (0.47, 0.54),
        "tip_curled": (0.47, 0.68),
    },
    "pinky": {
        "mcp": (0.44, 0.72),
        "pip": (0.44, 0.65),
        "tip": (0.44, 0.58),
        "tip_curled": (0.44, 0.72),
    },
}

POSES = ("open", "point", "pinch", "middle_pinch", "fist")


def _midpoint(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _finger_points(mcp, pip, tip) -> list[tuple[float, float]]:
    dip = _midpoint(pip, tip)
    return [mcp, pip, dip, tip]


def make_hand(pose: str = "open", rotation_deg: float = 0.0) -> np.ndarray:
    """Return a (21, 3) landmark array for the requested pose."""
    if pose not in POSES:
        raise ValueError(f"unknown pose {pose!r}")

    curled = pose in ("point", "fist", "middle_pinch")
    points: list[tuple[float, float]] = [(0.0, 0.0)] * 21

    points[0] = WRIST

    thumb_tip = THUMB["tip_open"]
    if pose == "pinch":
        thumb_tip = THUMB["tip_pinch"]
    elif pose == "middle_pinch":
        thumb_tip = THUMB["tip_middle_pinch"]
    elif pose == "fist":
        thumb_tip = (0.46, 0.72)
    points[1] = THUMB["cmc"]
    points[2] = THUMB["mcp"]
    points[3] = THUMB["ip"]
    points[4] = thumb_tip

    index = FINGERS["index"]
    index_tip = index["tip_curled"] if pose in ("fist", "middle_pinch") else index["tip"]
    points[5:9] = _finger_points(index["mcp"], index["pip"], index_tip)

    for offset, name in ((9, "middle"), (13, "ring"), (17, "pinky")):
        finger = FINGERS[name]
        tip = finger["tip_curled"] if curled else finger["tip"]
        points[offset : offset + 4] = _finger_points(finger["mcp"], finger["pip"], tip)

    if pose == "middle_pinch":
        middle_tip = (0.512, 0.552)
        points[12] = middle_tip
        points[11] = _midpoint(points[10], middle_tip)

    array = np.array([(x, y, 0.0) for x, y in points], dtype=float)

    if rotation_deg:
        angle = np.deg2rad(rotation_deg)
        rotation = np.array(
            [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
        )
        wrist = array[0, :2]
        array[:, :2] = (array[:, :2] - wrist) @ rotation.T + wrist

    return array
