"""Hand landmark geometry.

Turns the raw 21-point MediaPipe hand skeleton into the handful of scale-free
features the gesture engine needs: pinch ratios, finger extension, hand scale,
and the pinch point.

Everything here is normalized by hand size so that thresholds keep working as
the hand moves closer to or further from the camera.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

WRIST = 0
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_TIP = 20

Landmarks = np.ndarray


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _scale_points(landmarks: Landmarks, aspect: float) -> Landmarks:
    """Make normalized x/y comparable by correcting for frame aspect ratio."""
    if aspect == 1.0:
        return landmarks
    scaled = np.array(landmarks, dtype=float, copy=True)
    scaled[:, 0] *= aspect
    return scaled


def hand_scale(landmarks: Landmarks, aspect: float = 1.0) -> float:
    """Reference length of the hand: wrist to index MCP."""
    points = _scale_points(landmarks, aspect)
    return _distance(points[WRIST], points[INDEX_MCP])


def pinch_ratio(landmarks: Landmarks, aspect: float = 1.0) -> float:
    """Thumb-tip to index-tip distance, as a multiple of hand size."""
    points = _scale_points(landmarks, aspect)
    scale = _distance(points[WRIST], points[INDEX_MCP])
    if scale <= 1e-6:
        return float("inf")
    return _distance(points[THUMB_TIP], points[INDEX_TIP]) / scale


def middle_pinch_ratio(landmarks: Landmarks, aspect: float = 1.0) -> float:
    """Thumb-tip to middle-tip distance, as a multiple of hand size."""
    points = _scale_points(landmarks, aspect)
    scale = _distance(points[WRIST], points[INDEX_MCP])
    if scale <= 1e-6:
        return float("inf")
    return _distance(points[THUMB_TIP], points[MIDDLE_TIP]) / scale


def pinch_point(landmarks: Landmarks) -> tuple[float, float]:
    """Midpoint between thumb tip and index tip, in frame-normalized coords."""
    thumb = landmarks[THUMB_TIP]
    index = landmarks[INDEX_TIP]
    return (float((thumb[0] + index[0]) / 2.0), float((thumb[1] + index[1]) / 2.0))


def _finger_extended(
    points: Landmarks, tip: int, pip: int, mcp: int, margin: float = 0.08
) -> bool:
    """Rotation-invariant extension test using distance from the wrist.

    A straight finger reaches further from the wrist at every joint; a curled
    finger folds back toward the palm.
    """
    wrist = points[WRIST]
    tip_d = _distance(points[tip], wrist)
    pip_d = _distance(points[pip], wrist)
    mcp_d = _distance(points[mcp], wrist)
    return tip_d > pip_d * (1.0 + margin) and pip_d > mcp_d * 0.95


@dataclass(frozen=True)
class HandFeatures:
    """Scale-free, rotation-tolerant description of a single hand."""

    pinch_ratio: float
    middle_pinch_ratio: float
    hand_scale: float
    pinch_point: tuple[float, float]
    index_extended: bool
    middle_extended: bool
    ring_extended: bool
    pinky_extended: bool
    thumb_extended: bool

    @property
    def pointing(self) -> bool:
        """Index extended while the other three long fingers are curled."""
        return (
            self.index_extended
            and not self.middle_extended
            and not self.ring_extended
            and not self.pinky_extended
        )

    @property
    def open_palm(self) -> bool:
        return all(
            (
                self.index_extended,
                self.middle_extended,
                self.ring_extended,
                self.pinky_extended,
            )
        )

    @classmethod
    def from_landmarks(cls, landmarks: Landmarks, aspect: float = 1.0) -> "HandFeatures":
        points = _scale_points(landmarks, aspect)
        scale = _distance(points[WRIST], points[INDEX_MCP])

        def ratio_to_index(tip: int) -> float:
            if scale <= 1e-6:
                return float("inf")
            return _distance(points[THUMB_TIP], points[tip]) / scale

        thumb_extended = _distance(points[THUMB_TIP], points[PINKY_MCP]) > _distance(
            points[THUMB_IP], points[PINKY_MCP]
        )

        return cls(
            pinch_ratio=ratio_to_index(INDEX_TIP),
            middle_pinch_ratio=ratio_to_index(MIDDLE_TIP),
            hand_scale=scale,
            pinch_point=pinch_point(landmarks),
            index_extended=_finger_extended(points, INDEX_TIP, INDEX_PIP, INDEX_MCP),
            middle_extended=_finger_extended(points, MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP),
            ring_extended=_finger_extended(points, RING_TIP, RING_PIP, RING_MCP),
            pinky_extended=_finger_extended(points, PINKY_TIP, PINKY_PIP, PINKY_MCP),
            thumb_extended=thumb_extended,
        )
