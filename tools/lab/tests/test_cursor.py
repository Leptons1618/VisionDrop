import pytest

from visiondrop.config import CursorConfig
from visiondrop.cursor import Cursor


def make_cursor(gain: float = 1.0) -> Cursor:
    return Cursor(
        screen_size=(1000, 1000),
        config=CursorConfig(gain=gain),
    )


def test_active_box_corners_map_to_screen_corners():
    cursor = make_cursor()
    assert cursor.map_to_screen((0.20, 0.15)) == (0.0, 0.0)
    assert cursor.map_to_screen((0.80, 0.90)) == pytest.approx((1000.0, 1000.0))


def test_out_of_box_positions_are_clamped():
    cursor = make_cursor()
    assert cursor.map_to_screen((-1.0, -1.0)) == (0.0, 0.0)
    assert cursor.map_to_screen((2.0, 2.0)) == pytest.approx((1000.0, 1000.0))


def test_gain_amplifies_movement_around_center():
    base = make_cursor(gain=1.0)
    amplified = make_cursor(gain=2.0)
    point = (0.35, 0.525)

    base_pos = base.map_to_screen(point)
    amplified_pos = amplified.map_to_screen(point)
    assert base_pos[0] > 100.0
    assert amplified_pos[0] < base_pos[0]


def test_cursor_is_centered_before_first_update():
    cursor = make_cursor()
    assert cursor.position == (500, 500)


def test_freeze_holds_position_then_resumes():
    cursor = make_cursor()
    cursor.update((0.30, 0.30), ts_s=0.0, ts_ms=0.0)
    cursor.freeze(0.0, duration_ms=200.0)

    held = cursor.position
    for index in range(1, 5):
        cursor.update((0.75, 0.85), ts_s=index / 30.0, ts_ms=index * 33.0)
    assert cursor.position == held

    for index in range(6, 40):
        cursor.update((0.75, 0.85), ts_s=index / 30.0, ts_ms=index * 33.0)
    assert cursor.position != held
    assert cursor.position[0] > 500


def test_unfreeze_allows_immediate_movement():
    cursor = make_cursor()
    cursor.update((0.30, 0.30), ts_s=0.0, ts_ms=0.0)
    cursor.freeze(0.0, duration_ms=1000.0)
    held = cursor.position

    cursor.unfreeze()
    for index in range(1, 40):
        cursor.update((0.75, 0.85), ts_s=index / 30.0, ts_ms=index * 33.0)
    assert cursor.position != held


def test_reset_recenters_cursor():
    cursor = make_cursor()
    for index in range(1, 20):
        cursor.update((0.75, 0.85), ts_s=index / 30.0, ts_ms=index * 33.0)
    cursor.reset()
    assert cursor.position == (500, 500)
