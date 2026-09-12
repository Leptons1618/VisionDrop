"""Associate detected hands with detected objects.

The association is intentionally simple and stateless: the pinch point must be
within a grab radius of an object's bounding box, scaled by the apparent size
of the hand. Continuity across occlusion is handled by the object tracker
(ByteTrack keeps its track IDs alive for ~1 s), so a reappearing object keeps
the same ``track_id`` and the next call to :func:`associate_hands` re-links it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from visiondrop.hands import MIDDLE_FINGER_MCP, WRIST, Hand

Box = tuple[int, int, int, int]  # x, y, width, height
Point = tuple[int, int]


@dataclass(frozen=True)
class Association:
    """A hand linked to the detected object it is reaching for."""

    hand_index: int
    detection: dict
    distance: float


def point_to_bbox_distance(point: Point, bbox: Box) -> float:
    """Euclidean distance from a point to a box (0.0 when inside)."""
    x, y = point
    bx, by, bw, bh = bbox
    dx = max(bx - x, 0, x - (bx + bw))
    dy = max(by - y, 0, y - (by + bh))
    return math.hypot(dx, dy)


def hand_span(hand: Hand) -> float:
    """Pixel distance from wrist to middle-finger base: apparent hand size."""
    wx, wy = hand.point(WRIST)
    mx, my = hand.point(MIDDLE_FINGER_MCP)
    return math.hypot(mx - wx, my - wy)


def associate_hands(
    hands: Sequence[Hand],
    detections: Sequence[dict],
    radius_ratio: float = 0.75,
    min_radius: float = 24.0,
) -> list[Association]:
    """Link each hand to the nearest object within its grab radius.

    The grab radius grows with the hand's apparent size so the interaction
    works at different camera distances.
    """
    if not hands or not detections:
        return []

    associations: list[Association] = []
    for hand_index, hand in enumerate(hands):
        radius = max(min_radius, hand_span(hand) * radius_ratio)
        cursor = hand.pinch_point

        best_distance = math.inf
        best_detection = None
        for detection in detections:
            distance = point_to_bbox_distance(cursor, detection["bbox"])
            if distance <= radius and distance < best_distance:
                best_distance = distance
                best_detection = detection

        if best_detection is not None:
            associations.append(Association(hand_index, best_detection, best_distance))
    return associations
