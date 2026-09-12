import random
import statistics

import pytest

from visiondrop.filters import OneEuroFilter, PointFilter


def test_first_sample_passes_through():
    assert OneEuroFilter().filter(10.0, 0.0) == 10.0


def test_constant_signal_is_stable():
    filt = OneEuroFilter()
    values = [filt.filter(5.0, t * 0.033) for t in range(30)]
    assert values[-1] == pytest.approx(5.0)


def test_reduces_jitter():
    rng = random.Random(7)
    filt = OneEuroFilter()
    noisy = [10.0 + rng.uniform(-1.0, 1.0) for _ in range(120)]
    filtered = [filt.filter(value, i * 0.033) for i, value in enumerate(noisy)]

    assert statistics.pstdev(filtered[20:]) < statistics.pstdev(noisy[20:]) / 2


def test_ramp_lag_is_bounded():
    filt = OneEuroFilter()
    values = [filt.filter(i * 1.0, i * 0.033) for i in range(60)]  # 30 px/s ramp
    assert values[-1] > 59.0 - 6.0


def test_rejects_non_increasing_timestamps():
    filt = OneEuroFilter()
    filt.filter(0.0, 1.0)
    assert filt.filter(100.0, 1.0) == 0.0


def test_point_filter_filters_both_axes():
    point_filter = PointFilter()
    assert point_filter.filter((10.0, 20.0), 0.0) == (10.0, 20.0)
    x, y = point_filter.filter((12.0, 18.0), 0.033)
    assert 10.0 < x < 12.0
    assert 18.0 < y < 20.0


def test_point_filter_reset_forgets_history():
    point_filter = PointFilter()
    for i in range(10):
        point_filter.filter((100.0, 100.0), i * 0.033)
    point_filter.reset()
    assert point_filter.filter((0.0, 0.0), 10.0) == (0.0, 0.0)
