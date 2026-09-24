import numpy as np

from helpers import make_hand
from test_engine import make_engine
from visiondrop.gestures import PinchEventKind
from visiondrop.telemetry import JsonlRecorder, load_recording
from visiondrop.tracking import FrameObservation, HandObservation


def build_recording() -> list[FrameObservation]:
    observations = []
    poses = ["point"] * 3 + ["pinch"] * 8 + ["point"] * 4
    for index, pose in enumerate(poses):
        timestamp = index / 30.0
        hand = HandObservation(make_hand(pose), None, "Right", 0.9)
        observations.append(FrameObservation(timestamp, (hand,)))
    return observations


def test_recording_round_trip(tmp_path):
    path = tmp_path / "session.jsonl"
    observations = build_recording()

    with JsonlRecorder(path) as recorder:
        for observation in observations:
            recorder.write(observation)

    loaded = load_recording(path)
    assert len(loaded) == len(observations)
    assert loaded[0].timestamp_s == observations[0].timestamp_s
    assert loaded[0].hands[0].landmarks.shape == (21, 3)
    assert np.allclose(loaded[0].hands[0].landmarks, observations[0].hands[0].landmarks)


def test_replay_is_deterministic_and_produces_click(tmp_path):
    path = tmp_path / "session.jsonl"
    with JsonlRecorder(path) as recorder:
        for observation in build_recording():
            recorder.write(observation)

    def run() -> list[PinchEventKind]:
        engine = make_engine()
        events: list[PinchEventKind] = []
        for observation in load_recording(path):
            events.extend(engine.process(observation).events)
        return events

    first = run()
    second = run()
    assert first == second
    assert PinchEventKind.CLICK in first
