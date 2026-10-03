"""The prototype's v2 stream: what the Swift engine reads live off macOS.

The committed fixture ``Tests/Fixtures/prototype-pinch-click.jsonl`` is this
writer's output for the prototype's own synthetic hands. CI replays it through
the Swift CLI and expects ``press click``, so a change on either side of the
bridge that breaks the other fails there. Regenerate it deliberately with
``UPDATE_FIXTURES=1 uv run pytest tools/lab/tests/test_v2_stream.py``.
"""

import io
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from helpers import make_hand
from visiondrop.telemetry import V2Writer, v2_hand
from visiondrop.tracking import FrameObservation, HandObservation

FIXTURE = Path(__file__).resolve().parents[3] / "Tests/Fixtures/prototype-pinch-click.jsonl"
STARTED = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)


class Recording(io.StringIO):
    flushes = 0

    def flush(self):
        self.flushes += 1
        super().flush()


def writer(stream=None, **overrides):
    options = dict(
        camera_size=(1280, 720), fps=60.0, mirrored=True, screen_size=(1920, 1080), started=STARTED
    )
    options.update(overrides)
    return V2Writer(stream if stream is not None else Recording(), **options)


def hand(pose="point", handedness="Right", score=0.9, landmarks=None):
    return HandObservation(make_hand(pose) if landmarks is None else landmarks, None, handedness, score)


def lines(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def pinch_click_stream():
    stream = Recording()
    out = writer(stream)
    poses = ["point"] * 3 + ["pinch"] * 6 + ["point"] * 6
    for index, pose in enumerate(poses):
        out.write(FrameObservation(100.0 + index / 60.0, (hand(pose, score=0.94),)))
    return stream


# ── good input


def test_header_is_a_valid_v2_header():
    header = lines(writer()._stream)[0]
    assert header["type"] == "header" and header["version"] == 2
    assert header["tracker"] == V2Writer.TRACKER
    assert header["camera"] == {"id": "opencv", "width": 1280, "height": 720, "fps": 60.0, "mirrored": True}
    assert header["displays"] == [{"id": 1, "bounds": [0, 0, 1920, 1080], "scale": 1.0, "primary": True}]
    # Swift's .iso8601 decoder rejects fractional seconds and offsets other than Z.
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", header["started"])


def test_default_start_time_has_no_fraction():
    out = V2Writer(Recording(), camera_size=(640, 480), fps=0.0, mirrored=False, screen_size=(800, 600))
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", lines(out._stream)[0]["started"])


def test_points_flip_y_and_drop_depth():
    landmarks = make_hand("point")
    landmarks[:, 2] = 0.37  # MediaPipe depth must not leak into the stream (SRS CON-5)
    converted = v2_hand(hand(landmarks=landmarks))
    assert len(converted["points"]) == 21
    for (x, y, _), point in zip(landmarks, converted["points"]):
        assert point == [pytest.approx(x), pytest.approx(1.0 - y), 0.9]


@pytest.mark.parametrize(
    ("label", "want"), [("Right", "right"), ("Left", "left"), ("left", "left"), ("Unknown", "unknown"), ("", "unknown")]
)
def test_handedness(label, want):
    assert v2_hand(hand(handedness=label))["handedness"] == want


def test_timestamps_start_at_zero():
    stream = pinch_click_stream()
    times = [line["t"] for line in lines(stream)[1:]]
    assert times[0] == 0.0
    assert times == sorted(times)
    assert times[-1] == pytest.approx(14 / 60.0, abs=1e-6)  # stamped to the microsecond


def test_every_line_is_flushed_for_a_live_reader():
    stream = pinch_click_stream()
    assert stream.flushes == len(stream.getvalue().splitlines())


def test_frame_without_hands():
    stream = Recording()
    writer(stream).write(FrameObservation(1.0, ()))
    assert lines(stream)[1] == {"type": "frame", "t": 0.0, "hands": []}


# ── bad input


@pytest.mark.parametrize(("score", "want"), [(1.7, 1.0), (-0.2, 0.0), (math.nan, 0.0), (math.inf, 0.0)])
def test_out_of_range_score_is_clamped_to_a_valid_confidence(score, want):
    converted = v2_hand(hand(score=score))
    assert converted["score"] == want
    assert all(point[2] == want for point in converted["points"])


def test_non_finite_joint_is_reported_missing():
    landmarks = make_hand("point")
    landmarks[8, 0] = math.nan
    landmarks[4, 1] = math.inf
    points = v2_hand(hand(landmarks=landmarks))["points"]
    assert points[8] is None and points[4] is None
    assert sum(point is None for point in points) == 2


@pytest.mark.parametrize("shape", [(20, 3), (22, 3), (21, 1), (21,), (0, 3)])
def test_wrong_landmark_shape_is_rejected(shape):
    with pytest.raises(ValueError, match="21 landmarks"):
        v2_hand(hand(landmarks=np.zeros(shape)))


def test_timestamp_going_backwards_is_held_not_emitted():
    stream = Recording()
    out = writer(stream)
    for t in (5.0, 5.1, 5.05, 5.2):
        out.write(FrameObservation(t, ()))
    times = [line["t"] for line in lines(stream)[1:]]
    assert times == sorted(times)
    assert times[2] == times[1]


def test_output_never_contains_nan():
    landmarks = make_hand("pinch")
    landmarks[:] = math.nan
    stream = Recording()
    writer(stream).write(FrameObservation(0.0, (hand(landmarks=landmarks, score=math.nan),)))
    assert "NaN" not in stream.getvalue()


# ── the bridge contract


def test_committed_cross_language_fixture_is_current():
    text = pinch_click_stream().getvalue()
    if os.environ.get("UPDATE_FIXTURES"):
        FIXTURE.write_text(text, encoding="utf-8")
    assert FIXTURE.read_text(encoding="utf-8") == text, "regenerate with UPDATE_FIXTURES=1"
