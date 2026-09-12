"""Hand tracking built on the MediaPipe Tasks Gesture Recognizer.

The Gesture Recognizer task bundles the hand landmark model, so a single
inference per frame yields landmarks, handedness, and a canned gesture label
(None, Closed_Fist, Open_Palm, Pointing_Up, Thumb_Down, Thumb_Up, Victory,
ILoveYou). MediaPipe is imported lazily so pure geometry helpers stay testable
without the runtime installed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from visiondrop.config import HandTrackingConfig
from visiondrop.models import ensure_model

logger = logging.getLogger(__name__)

WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
MIDDLE_FINGER_MCP = 9

HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


@dataclass(frozen=True)
class Hand:
    """One detected hand with landmarks, handedness, and gesture label."""

    landmarks: tuple[tuple[float, float, float], ...]
    pixel_landmarks: tuple[tuple[int, int], ...]
    handedness: str = "Unknown"
    gesture: str = "None"
    gesture_score: float = 0.0

    def point(self, index: int) -> tuple[int, int]:
        return self.pixel_landmarks[index]

    @property
    def pinch_point(self) -> tuple[int, int]:
        """Midpoint between thumb tip and index tip: the interaction cursor."""
        tx, ty = self.pixel_landmarks[THUMB_TIP]
        ix, iy = self.pixel_landmarks[INDEX_TIP]
        return (tx + ix) // 2, (ty + iy) // 2

    @property
    def pinch_distance(self) -> float:
        """Normalized thumb-tip to index-tip distance (0.0 = touching)."""
        tx, ty, _ = self.landmarks[THUMB_TIP]
        ix, iy, _ = self.landmarks[INDEX_TIP]
        return float(np.hypot(tx - ix, ty - iy))

    @property
    def pinch_ratio(self) -> float:
        """Pinch distance relative to hand size: scale invariant.

        Near 0 when the fingers touch, near 1 (or more) when the hand is open.
        Returns 1.0 for degenerate hands so a zero span cannot trigger a grab.
        """
        wx, wy, _ = self.landmarks[WRIST]
        mx, my, _ = self.landmarks[MIDDLE_FINGER_MCP]
        span = float(np.hypot(mx - wx, my - wy))
        if span <= 0.0:
            return 1.0
        return self.pinch_distance / span


def build_hand(
    landmarks,
    width: int,
    height: int,
    handedness: str = "Unknown",
    gesture: str = "None",
    gesture_score: float = 0.0,
) -> Hand:
    """Convert MediaPipe normalized landmarks into a Hand."""
    return Hand(
        landmarks=tuple((lm.x, lm.y, lm.z) for lm in landmarks),
        pixel_landmarks=tuple((int(lm.x * width), int(lm.y * height)) for lm in landmarks),
        handedness=handedness,
        gesture=gesture,
        gesture_score=gesture_score,
    )


class HandTracker:
    """Runs the MediaPipe Gesture Recognizer in VIDEO mode on BGR frames."""

    def __init__(
        self,
        config: HandTrackingConfig | None = None,
        model_dir: str | Path | None = None,
    ) -> None:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = __import__("mediapipe")
        self.config = config or HandTrackingConfig()
        self._last_timestamp_ms = -1

        model_path = ensure_model("gesture_recognizer", model_dir)
        options = vision.GestureRecognizerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=self.config.num_hands,
            min_hand_detection_confidence=self.config.min_detection_confidence,
            min_hand_presence_confidence=self.config.min_hand_presence_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)
        logger.info("HandTracker ready (gesture recognizer, %d hand(s))", self.config.num_hands)

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int | None = None) -> list[Hand]:
        """Detect hands in a BGR frame. Timestamps must be monotonically increasing."""
        if timestamp_ms is None:
            timestamp_ms = int(time.perf_counter() * 1000)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._recognizer.recognize_for_video(image, timestamp_ms)

        height, width = frame_bgr.shape[:2]
        hands: list[Hand] = []
        for i, landmarks in enumerate(result.hand_landmarks):
            handedness = "Unknown"
            if i < len(result.handedness) and result.handedness[i]:
                handedness = result.handedness[i][0].category_name
            gesture, score = "None", 0.0
            if i < len(result.gestures) and result.gestures[i]:
                top = result.gestures[i][0]
                gesture, score = top.category_name, float(top.score)
            hands.append(build_hand(landmarks, width, height, handedness, gesture, score))
        return hands

    def close(self) -> None:
        self._recognizer.close()

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def draw_hands(
    frame: np.ndarray,
    hands: list[Hand],
    color: tuple[int, int, int] = (0, 255, 0),
) -> np.ndarray:
    """Draw hand skeletons and pinch points on a BGR frame in place."""
    for hand in hands:
        for start, end in HAND_CONNECTIONS:
            cv2.line(frame, hand.point(start), hand.point(end), color, 2)
        for point in hand.pixel_landmarks:
            cv2.circle(frame, point, 3, (255, 255, 255), -1)
        cv2.circle(frame, hand.pinch_point, 6, (0, 0, 255), -1)
    return frame
