import statistics

import pytest

from visiondrop.filters import EMASmoother, OneEuroFilter, OneEuroFilter2D, VelocityTracker, alpha


def test_alpha_is_bounded():
    assert 0.0 < alpha(1.0, 1 / 30) < 1.0
    assert alpha(1000.0, 1 / 30) > alpha(1.0, 1 / 30)


def test_one_euro_reduces_jitter_on_stationary_signal():
    rng = __import__("random").Random(7)
    noisy = [1.0 + rng.gauss(0.0, 0.05) for _ in range(240)]
    filt = OneEuroFilter(min_cutoff=1.4, beta=0.007)
    filtered = [filt(x, i / 30.0) for i, x in enumerate(noisy)]

    settle = len(noisy) // 2
    raw_spread = statistics.pstdev(noisy[settle:])
    filtered_spread = statistics.pstdev(filtered[settle:])
    assert filtered_spread < raw_spread * 0.5


def test_one_euro_tracks_fast_motion():
    filt = OneEuroFilter(min_cutoff=1.0, beta=0.05)
    value = 0.0
    for i in range(60):
        value = filt(10.0 * (i / 30.0), i / 30.0)
    assert value == pytest.approx(10.0 * (59 / 30.0), rel=0.1)


def test_one_euro_2d_smooths_each_axis():
    filt = OneEuroFilter2D(min_cutoff=1.0, beta=0.0)
    out = filt((0.0, 0.0), 0.0)
    assert out == (0.0, 0.0)
    for i in range(1, 30):
        out = filt((100.0, 50.0), i / 30.0)
    assert out[0] > 90.0
    assert out[1] > 45.0


def test_ema_smoother_starts_at_first_value():
    smoother = EMASmoother(factor=0.5)
    assert smoother(2.0) == 2.0
    assert smoother(4.0) == 3.0


def test_velocity_tracker_is_zero_when_still_and_positive_when_moving():
    tracker = VelocityTracker()
    for i in range(10):
        tracker((0.5, 0.5), i / 30.0)
    assert tracker.speed == pytest.approx(0.0)

    for i in range(10):
        tracker((0.5 + i * 0.01, 0.5), 0.3 + i / 30.0)
    assert tracker.speed > 0.0
