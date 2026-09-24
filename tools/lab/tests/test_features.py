import numpy as np
import pytest

from helpers import make_hand
from visiondrop.features import HandFeatures, hand_scale, pinch_ratio


def test_pinch_ratio_separates_open_from_pinched():
    open_features = HandFeatures.from_landmarks(make_hand("open"))
    pinched = HandFeatures.from_landmarks(make_hand("pinch"))

    assert open_features.pinch_ratio > 1.0
    assert pinched.pinch_ratio < 0.2
    assert pinched.pinch_ratio < open_features.pinch_ratio / 5.0


def test_pinch_ratio_is_rotation_invariant():
    base = HandFeatures.from_landmarks(make_hand("pinch"))
    rotated = HandFeatures.from_landmarks(make_hand("pinch", rotation_deg=35.0))
    assert rotated.pinch_ratio == pytest.approx(base.pinch_ratio, rel=0.02)


def test_extension_flags_for_open_and_curled_hands():
    open_features = HandFeatures.from_landmarks(make_hand("open"))
    assert open_features.index_extended
    assert open_features.middle_extended
    assert open_features.ring_extended
    assert open_features.pinky_extended
    assert open_features.open_palm
    assert not open_features.pointing

    point = HandFeatures.from_landmarks(make_hand("point"))
    assert point.index_extended
    assert not point.middle_extended
    assert not point.ring_extended
    assert not point.pinky_extended
    assert point.pointing


def test_extension_flags_survive_rotation():
    for pose in ("open", "point"):
        straight = HandFeatures.from_landmarks(make_hand(pose))
        rotated = HandFeatures.from_landmarks(make_hand(pose, rotation_deg=-40.0))
        assert straight.pointing == rotated.pointing
        assert straight.open_palm == rotated.open_palm


def test_hand_scale_and_pinch_ratio_are_positive():
    landmarks = make_hand("open")
    assert hand_scale(landmarks) > 0
    assert pinch_ratio(landmarks) > 0


def test_pinch_point_is_between_the_two_fingertips():
    features = HandFeatures.from_landmarks(make_hand("pinch"))
    x, y = features.pinch_point
    assert 0.5 < x < 0.55
    assert 0.5 < y < 0.58


def test_middle_pinch_ratio_lower_for_middle_pinch_pose():
    middle = HandFeatures.from_landmarks(make_hand("middle_pinch"))
    open_features = HandFeatures.from_landmarks(make_hand("open"))
    assert middle.middle_pinch_ratio < open_features.middle_pinch_ratio / 5.0
    assert np.isfinite(middle.pinch_ratio)
