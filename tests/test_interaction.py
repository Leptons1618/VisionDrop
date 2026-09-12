import random

from visiondrop.association import Association
from visiondrop.config import InteractionConfig
from visiondrop.hands import INDEX_TIP, MIDDLE_FINGER_MCP, THUMB_TIP, WRIST, build_hand
from visiondrop.interaction import InteractionEngine, State


class FakeLandmark:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


def make_hand(cursor=(100, 100), ratio=1.0, span=100, width=640, height=480):
    """Hand whose pinch_ratio is exactly the requested value."""
    half = ratio * (span / height) / 2.0

    def lm(px, py):
        return FakeLandmark(px / width, py / height)

    landmarks = [lm(*cursor) for _ in range(21)]
    landmarks[THUMB_TIP] = lm(cursor[0] - half * width, cursor[1])
    landmarks[INDEX_TIP] = lm(cursor[0] + half * width, cursor[1])
    landmarks[WRIST] = lm(cursor[0], cursor[1] + span)
    landmarks[MIDDLE_FINGER_MCP] = lm(*cursor)
    return build_hand(landmarks, width, height)


def detection(cursor=(100, 100), track_id=1):
    x, y = cursor
    return {
        "type": "cup",
        "bbox": (x - 20, y - 20, 40, 40),
        "center": (x, y),
        "track_id": track_id,
    }


def association_for(cursor=(100, 100)):
    return Association(hand_index=0, detection=detection(cursor), distance=0.0)


def run(engine, hand, association=None, frames=1, start=0.0):
    results = []
    for i in range(frames):
        results.append(engine.update(hand, association, start + i / 30))
    return results


def test_idle_without_objects():
    result = InteractionEngine().update(make_hand(ratio=1.0), None, 0.0)
    assert result.state is State.IDLE
    assert result.event is None


def test_hover_over_object_with_open_hand():
    result = InteractionEngine().update(make_hand(ratio=1.0), association_for(), 0.0)
    assert result.state is State.HOVER


def test_partially_open_hand_never_grabs():
    engine = InteractionEngine()
    results = run(engine, make_hand(ratio=0.35), association_for(), frames=60)
    assert all(result.state is State.HOVER for result in results)
    assert all(result.event is None for result in results)


def test_grab_requires_debounce_frames():
    engine = InteractionEngine()
    hand = make_hand(ratio=0.1)

    first, second = run(engine, hand, association_for(), frames=2)
    assert first.state is State.HOVER
    assert second.state is State.HOVER

    third = engine.update(hand, association_for(), 2 / 30)
    assert third.state is State.DRAG
    assert third.event == "grabbed"
    assert third.held_object["track_id"] == 1


def test_pinch_flicker_does_not_grab():
    engine = InteractionEngine()
    timestamp = 0.0
    for ratio in (0.1, 1.0, 0.1, 1.0, 0.1, 1.0):
        result = engine.update(make_hand(ratio=ratio), association_for(), timestamp)
        assert result.event != "grabbed"
        assert result.state is State.HOVER
        timestamp += 1 / 30


def test_held_object_follows_association():
    engine = InteractionEngine()
    run(engine, make_hand(ratio=0.1), association_for((100, 100)), frames=3)

    moved = association_for((140, 120))
    result = engine.update(make_hand(cursor=(140, 120), ratio=0.1), moved, 3 / 30)

    assert result.state is State.DRAG
    assert result.held_object["bbox"] == moved.detection["bbox"]


def test_drag_survives_brief_association_loss():
    engine = InteractionEngine()
    run(engine, make_hand(ratio=0.1), association_for(), frames=3)

    results = run(engine, make_hand(ratio=0.1), None, frames=10, start=3 / 30)

    assert all(result.state is State.DRAG for result in results)
    assert results[-1].held_object is not None


def test_cancel_on_prolonged_hand_loss():
    engine = InteractionEngine()
    run(engine, make_hand(ratio=0.1), association_for(), frames=3)

    results = [engine.update(None, None, (3 + i) / 30) for i in range(20)]

    cancelled = [result for result in results if result.event == "cancelled"]
    assert len(cancelled) == 1
    assert cancelled[0].state is State.IDLE
    assert cancelled[0].held_object is None


def test_release_requires_debounce():
    engine = InteractionEngine()
    run(engine, make_hand(ratio=0.1), association_for(), frames=3)

    open_hand = make_hand(ratio=1.0)
    first, second = run(engine, open_hand, association_for(), frames=2, start=3 / 30)
    assert first.state is State.DRAG
    assert second.state is State.DRAG

    third = engine.update(open_hand, association_for(), 5 / 30)
    assert third.event == "dropped"
    assert third.state is State.HOVER
    assert third.dropped_object["track_id"] == 1
    assert third.held_object is None


def test_hysteresis_between_grab_and_release():
    engine = InteractionEngine()
    run(engine, make_hand(ratio=0.1), association_for(), frames=3)

    midway = make_hand(ratio=0.35)  # above grab threshold, below release threshold
    results = run(engine, midway, association_for(), frames=10, start=3 / 30)

    assert all(result.state is State.DRAG for result in results)
    assert all(result.event != "dropped" for result in results)


def test_cooldown_blocks_immediate_regrab():
    engine = InteractionEngine()
    run(engine, make_hand(ratio=0.1), association_for(), frames=3)
    open_hand = make_hand(ratio=1.0)
    dropped = run(engine, open_hand, association_for(), frames=3, start=3 / 30)[-1]
    assert dropped.event == "dropped"

    closed = make_hand(ratio=0.1)
    events = [
        engine.update(closed, association_for(), (6 + i) / 30).event for i in range(9)
    ]
    assert "grabbed" not in events

    assert engine.update(closed, association_for(), 15 / 30).event == "grabbed"


def test_idle_jitter_never_grabs():
    """Five minutes of jittery open-hand motion over an object: zero grabs."""
    rng = random.Random(42)
    engine = InteractionEngine()
    target = association_for((300, 200))
    timestamp = 0.0
    events = []

    for _ in range(9000):  # 5 minutes at 30 FPS
        cursor = (300 + rng.uniform(-4, 4), 200 + rng.uniform(-4, 4))
        hand = make_hand(cursor=cursor, ratio=rng.uniform(0.4, 0.6))
        result = engine.update(hand, target, timestamp)
        if result.event:
            events.append(result.event)
        timestamp += 1 / 30

    assert events == []


def dwell_config(**overrides):
    settings = {"grab_mode": "dwell", "dwell_s": 0.5, "dwell_exit_px": 80.0}
    settings.update(overrides)
    return InteractionConfig(**settings)


def test_dwell_waits_full_duration():
    engine = InteractionEngine(dwell_config())
    results = run(engine, make_hand(ratio=1.0), association_for(), frames=14)
    assert all(result.state is State.HOVER for result in results)
    assert all(result.event is None for result in results)


def test_dwell_grabs_after_dwell_time():
    engine = InteractionEngine(dwell_config())
    results = run(engine, make_hand(ratio=1.0), association_for(), frames=16)
    assert results[-1].state is State.DRAG
    assert results[-1].event == "grabbed"
    assert results[-1].held_object["track_id"] == 1


def test_dwell_timer_resets_when_leaving_object():
    engine = InteractionEngine(dwell_config())
    run(engine, make_hand(ratio=1.0), association_for(), frames=10)
    run(engine, make_hand(ratio=1.0), None, frames=2, start=10 / 30)
    results = run(engine, make_hand(ratio=1.0), association_for(), frames=10, start=12 / 30)
    assert all(result.state is State.HOVER for result in results)


def test_dwell_stays_grabbed_near_grab_point():
    engine = InteractionEngine(dwell_config())
    run(engine, make_hand(ratio=1.0), association_for((100, 100)), frames=16)
    results = run(
        engine, make_hand(cursor=(110, 100), ratio=1.0), association_for((110, 100)),
        frames=30, start=16 / 30,
    )
    assert all(result.state is State.DRAG for result in results)
    assert all(result.event is None for result in results)


def test_dwell_drops_after_dwelling_far_from_grab_point():
    engine = InteractionEngine(dwell_config())
    run(engine, make_hand(ratio=1.0), association_for((100, 100)), frames=16)
    far = association_for((400, 100))
    results = run(
        engine, make_hand(cursor=(400, 100), ratio=1.0), far, frames=90, start=16 / 30,
    )
    dropped = [result for result in results if result.event == "dropped"]
    assert len(dropped) == 1
    assert dropped[0].state is State.HOVER
    assert dropped[0].dropped_object["track_id"] == 1


def test_dwell_returning_to_grab_point_cancels_drop():
    engine = InteractionEngine(dwell_config())
    run(engine, make_hand(ratio=1.0), association_for((100, 100)), frames=16)
    run(
        engine, make_hand(cursor=(400, 100), ratio=1.0), association_for((400, 100)),
        frames=9, start=16 / 30,
    )
    results = run(
        engine, make_hand(cursor=(105, 100), ratio=1.0), association_for((105, 100)),
        frames=60, start=25 / 30,
    )
    assert all(result.state is State.DRAG for result in results)
    assert all(result.event != "dropped" for result in results)
