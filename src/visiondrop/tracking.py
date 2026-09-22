"""MediaPipe hand tracking wrapper.

Keeps MediaPipe behind a small, testable interface and exposes both the
image-normalized landmarks (for on-screen positions) and the metric world
landmarks (for scale-free gesture features).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config as _config


@dataclass(frozen=True)
class HandObservation:
    landmarks: np.ndarray
    world_landmarks: np.ndarray | None
    handedness: str
    score: float


@dataclass(frozen=True)
class FrameObservation:
    timestamp_s: float
    hands: tuple[HandObservation, ...]


class HandTracker:
    """Thin wrapper around ``mediapipe.solutions.hands``.

    The Tasks API (``HandLandmarker``) is the planned successor; this wrapper
    isolates that swap to a single class.
    """

    def __init__(self, config: _config.EngineConfig | None = None) -> None:
        self.config = config or _config.DEFAULT_CONFIG
        self._mp = None
        self._hands = None
        self._drawing = None

    def _ensure_loaded(self) -> None:
        if self._hands is not None:
            return
        import absl.logging as absl_logging
        import mediapipe as mp
        from mediapipe.framework.formats import landmark_pb2

        absl_logging.set_verbosity(absl_logging.ERROR)
        self._mp = mp
        self._landmark_pb2 = landmark_pb2
        self._drawing = mp.solutions.drawing_utils
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=self.config.max_num_hands,
            model_complexity=self.config.model_complexity,
            min_detection_confidence=self.config.min_detection_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
        )

    def process(self, frame_bgr: np.ndarray, timestamp_s: float) -> FrameObservation:
        import cv2

        self._ensure_loaded()
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        results = self._hands.process(frame_rgb)
        frame_rgb.flags.writeable = True

        hands: list[HandObservation] = []
        if results.multi_hand_landmarks:
            world = results.multi_hand_world_landmarks or [None] * len(
                results.multi_hand_landmarks
            )
            handedness = results.multi_handedness or [None] * len(
                results.multi_hand_landmarks
            )
            for image_landmarks, world_landmarks, handed in zip(
                results.multi_hand_landmarks, world, handedness
            ):
                label = "Unknown"
                score = 0.0
                if handed and handed.classification:
                    label = handed.classification[0].label
                    score = float(handed.classification[0].score)
                hands.append(
                    HandObservation(
                        landmarks=np.array(
                            [[lm.x, lm.y, lm.z] for lm in image_landmarks.landmark],
                            dtype=float,
                        ),
                        world_landmarks=(
                            np.array(
                                [[lm.x, lm.y, lm.z] for lm in world_landmarks.landmark],
                                dtype=float,
                            )
                            if world_landmarks is not None
                            else None
                        ),
                        handedness=label,
                        score=score,
                    )
                )

        return FrameObservation(timestamp_s=timestamp_s, hands=tuple(hands))

    def draw(self, frame_bgr: np.ndarray, observation: FrameObservation) -> np.ndarray:
        """Debug-only skeleton overlay. Never used in normal operation."""
        self._ensure_loaded()
        if not observation.hands:
            return frame_bgr
        connections = self._mp.solutions.hands.HAND_CONNECTIONS
        for hand in observation.hands:
            proto = self._landmark_pb2.NormalizedLandmarkList()
            for x, y, z in hand.landmarks:
                landmark = proto.landmark.add()
                landmark.x = float(x)
                landmark.y = float(y)
                landmark.z = float(z)
            self._drawing.draw_landmarks(frame_bgr, proto, connections)
        return frame_bgr

    def close(self) -> None:
        if self._hands is not None:
            self._hands.close()
            self._hands = None
