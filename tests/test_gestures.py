import pytest

from visiondrop.config import PinchConfig
from visiondrop.gestures import PinchEventKind, PinchFSM, is_idle_pose
from visiondrop.features import HandFeatures
from tests.helpers import make_hand

FRAME_MS = 1000.0 / 30.0


def feed(fsm: PinchFSM, ratios: list[float], start_ms: float = 0.0, positions=None):
    states = []
    for index, ratio in enumerate(ratios):
        position = (100.0, 100.0) if positions is None else positions[index]
        states.append(fsm.update(ratio, position, start_ms + index * FRAME_MS))
    return states


def events_for(states) -> list[PinchEventKind]:
    return [event for state in states for event in state.events]


def test_press_and_click_with_hysteresis():
    fsm = PinchFSM()
    ratios = [1.2, 1.2, 0.8, 0.6, 0.4, 0.4, 0.4, 0.6, 0.7, 0.7, 1.2]
    events = events_for(feed(fsm, ratios))
    assert events == [PinchEventKind.PRESS, PinchEventKind.CLICK]


def test_single_frame_dip_does_not_trigger_press():
    fsm = PinchFSM()
    ratios = [1.2, 0.4, 1.2, 1.2, 1.2, 1.2]
    events = events_for(feed(fsm, ratios))
    assert events == []


def test_chatter_around_threshold_does_not_flicker():
    fsm = PinchFSM()
    ratios = [1.2, 0.4, 0.4, 0.7, 0.4, 0.7, 0.4, 1.2, 1.2]
    events = events_for(feed(fsm, ratios))
    assert events == [PinchEventKind.PRESS, PinchEventKind.CLICK]


def test_drag_disambiguated_from_click():
    fsm = PinchFSM()
    ratios = [1.2, 0.4, 0.4, 0.4, 0.4, 1.2, 1.2]
    positions = [(100.0, 100.0)] * 3 + [(130.0, 100.0), (140.0, 100.0)] + [(140.0, 100.0)] * 2
    states = feed(fsm, ratios, positions=positions)
    events = events_for(states)
    assert PinchEventKind.DRAG_START in events
    assert PinchEventKind.DRAG_END in events
    assert PinchEventKind.CLICK not in events


def test_small_movement_still_clicks():
    fsm = PinchFSM(config=PinchConfig(drag_move_px=10.0))
    ratios = [1.2, 0.4, 0.4, 0.4, 1.2, 1.2]
    positions = [(100.0, 100.0), (100.0, 100.0), (104.0, 100.0), (105.0, 100.0), (105.0, 100.0), (105.0, 100.0)]
    events = events_for(feed(fsm, ratios, positions=positions))
    assert PinchEventKind.CLICK in events
    assert PinchEventKind.DRAG_START not in events


def test_double_click_within_window():
    fsm = PinchFSM()
    ratios = [1.2, 0.4, 0.4, 1.2, 1.2, 1.2, 1.2, 0.4, 0.4, 0.4, 1.2, 1.2]
    events = events_for(feed(fsm, ratios))
    assert events.count(PinchEventKind.DOUBLE_CLICK) == 1
    assert events.count(PinchEventKind.CLICK) == 1


def test_two_slow_clicks_are_not_a_double_click():
    fsm = PinchFSM()
    ratios = [1.2, 0.4, 0.4, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 0.4, 0.4, 1.2, 1.2]
    events = events_for(feed(fsm, ratios))
    assert events.count(PinchEventKind.CLICK) == 2
    assert PinchEventKind.DOUBLE_CLICK not in events


def test_reset_clears_state():
    fsm = PinchFSM()
    feed(fsm, [1.2, 0.4, 0.4])
    assert fsm.closed
    fsm.reset()
    assert not fsm.closed
    assert not fsm.dragging
    assert events_for(feed(fsm, [0.4, 0.4])) == [PinchEventKind.PRESS]


def test_idle_pose_detection():
    open_features = HandFeatures.from_landmarks(make_hand("open"))
    point_features = HandFeatures.from_landmarks(make_hand("point"))
    pinch_features = HandFeatures.from_landmarks(make_hand("pinch"))
    assert is_idle_pose(open_features, speed=0.1)
    assert not is_idle_pose(open_features, speed=5.0)
    assert not is_idle_pose(point_features, speed=0.1)
    assert not is_idle_pose(pinch_features, speed=0.1)
