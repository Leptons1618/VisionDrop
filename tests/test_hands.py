import numpy as np
import pytest

from visiondrop.hands import (
    HAND_CONNECTIONS,
    INDEX_TIP,
    MIDDLE_FINGER_MCP,
    THUMB_TIP,
    WRIST,
    build_hand,
    draw_hands,
)


class FakeLandmark:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


def make_landmarks():
    landmarks = [FakeLandmark(0.5, 0.5) for _ in range(21)]
    landmarks[THUMB_TIP] = FakeLandmark(0.2, 0.3)
    landmarks[INDEX_TIP] = FakeLandmark(0.4, 0.5)
    return landmarks


def test_connections_reference_valid_landmarks():
    assert len(HAND_CONNECTIONS) == 21
    for start, end in HAND_CONNECTIONS:
        assert 0 <= start < 21 and 0 <= end < 21


def test_build_hand_converts_to_pixels():
    hand = build_hand(make_landmarks(), width=100, height=200)
    assert hand.point(THUMB_TIP) == (20, 60)
    assert hand.point(INDEX_TIP) == (40, 100)


def test_build_hand_keeps_metadata():
    hand = build_hand(make_landmarks(), 100, 200, "Right", "Victory", 0.9)
    assert hand.handedness == "Right"
    assert hand.gesture == "Victory"
    assert hand.gesture_score == 0.9


def test_pinch_point_is_thumb_index_midpoint():
    hand = build_hand(make_landmarks(), width=100, height=200)
    assert hand.pinch_point == (30, 80)


def test_pinch_distance_is_normalized():
    hand = build_hand(make_landmarks(), width=100, height=200)
    assert hand.pinch_distance == pytest.approx(np.hypot(0.2, 0.2))


def test_draw_hands_marks_pinch_point():
    frame = np.zeros((200, 100, 3), dtype=np.uint8)
    hand = build_hand(make_landmarks(), width=100, height=200)

    draw_hands(frame, [hand])

    assert frame.max() > 0
    px, py = hand.pinch_point
    assert tuple(int(v) for v in frame[py, px]) == (0, 0, 255)


def make_hand_with(thumb, index, wrist, mcp, width=100, height=200):
    landmarks = [FakeLandmark(0.5, 0.5) for _ in range(21)]
    landmarks[THUMB_TIP] = FakeLandmark(*thumb)
    landmarks[INDEX_TIP] = FakeLandmark(*index)
    landmarks[WRIST] = FakeLandmark(*wrist)
    landmarks[MIDDLE_FINGER_MCP] = FakeLandmark(*mcp)
    return build_hand(landmarks, width, height)


def test_pinch_ratio_is_scale_invariant():
    small = make_hand_with(
        thumb=(0.4, 0.5), index=(0.5, 0.5), wrist=(0.5, 0.5), mcp=(0.5, 0.3)
    )
    large = make_hand_with(
        thumb=(0.3, 0.5), index=(0.5, 0.5), wrist=(0.5, 0.5), mcp=(0.5, 0.1)
    )
    assert small.pinch_ratio == pytest.approx(0.5)
    assert large.pinch_ratio == pytest.approx(0.5)


def test_pinch_ratio_zero_span_is_open():
    hand = make_hand_with(
        thumb=(0.4, 0.5), index=(0.5, 0.5), wrist=(0.5, 0.5), mcp=(0.5, 0.5)
    )
    assert hand.pinch_ratio == 1.0
