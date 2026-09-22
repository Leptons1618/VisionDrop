from tests.helpers import make_hand
from visiondrop.config import EngineConfig
from visiondrop.engine import Engine
from visiondrop.gestures import PinchEventKind
from visiondrop.tracking import FrameObservation, HandObservation


def observation(pose: str, timestamp_s: float) -> FrameObservation:
    hand = HandObservation(
        landmarks=make_hand(pose),
        world_landmarks=None,
        handedness="Right",
        score=0.95,
    )
    return FrameObservation(timestamp_s=timestamp_s, hands=(hand,))


def empty(timestamp_s: float) -> FrameObservation:
    return FrameObservation(timestamp_s=timestamp_s, hands=())


def make_engine() -> Engine:
    return Engine(EngineConfig(), screen_size=(1000, 1000), frame_aspect=1.0)


def test_click_sequence_produces_press_and_click():
    engine = make_engine()
    events = []
    timestamp = 0.0
    for pose in ["point"] * 3 + ["pinch"] * 6 + ["point"] * 4:
        state = engine.process(observation(pose, timestamp))
        events.extend(state.events)
        timestamp += 1 / 30.0

    assert PinchEventKind.PRESS in events
    assert PinchEventKind.CLICK in events
    assert PinchEventKind.DRAG_START not in events


def test_cursor_freezes_when_click_fires():
    engine = make_engine()
    timestamp = 0.0
    frozen_after_click = False
    for pose in ["point"] * 3 + ["pinch"] * 6 + ["point"] * 4:
        engine.process(observation(pose, timestamp))
        timestamp += 1 / 30.0
        if engine.cursor.is_frozen(timestamp * 1000.0):
            frozen_after_click = True
    assert frozen_after_click


def test_cursor_does_not_move_on_open_palm():
    engine = make_engine()
    state = engine.process(observation("open", 0.0))
    assert state.hand_present
    assert state.idle
    assert not state.active
    assert state.cursor == (500, 500)


def test_hand_loss_resets_pinch_and_reports_idle():
    engine = make_engine()
    engine.process(observation("pinch", 0.0))
    engine.process(observation("pinch", 1 / 30.0))
    state = engine.process(empty(2 / 30.0))

    assert not state.hand_present
    assert state.idle
    assert not engine.pinch.closed


def test_second_hand_with_lower_score_is_ignored():
    engine = make_engine()
    primary = HandObservation(make_hand("pinch"), None, "Right", 0.99)
    noise = HandObservation(make_hand("open"), None, "Left", 0.10)
    state = engine.process(FrameObservation(1.0, (noise, primary)))
    assert state.features is not None
    assert state.features.pinch_ratio < 0.2
