import json

import pytest

from visiondrop.analysis import load_session, render_plot, summarize


def make_frames(n=10, state="IDLE", linked=0):
    return [
        {
            "type": "frame",
            "frame": i,
            "t": i / 30,
            "state": state,
            "cursor": [10.0, 20.0],
            "hands": 1,
            "objects": 2,
            "linked": linked,
            "hand_ms": 10.0,
            "detect_ms": 30.0,
            "fps": 30.0,
        }
        for i in range(n)
    ]


def make_events():
    return [
        {"type": "event", "frame": 10, "t": 0.5, "event": "grabbed", "track_id": 1},
        {"type": "event", "frame": 40, "t": 2.0, "event": "dropped", "track_id": 1, "zone": "A"},
        {"type": "event", "frame": 60, "t": 3.0, "event": "grabbed", "track_id": 2},
        {"type": "event", "frame": 75, "t": 3.75, "event": "dropped", "track_id": 2},
        {"type": "event", "frame": 90, "t": 4.5, "event": "grabbed", "track_id": 3},
        {"type": "event", "frame": 100, "t": 5.0, "event": "cancelled", "track_id": 3},
    ]


def test_summarize_counts_and_rates():
    summary = summarize(make_frames(), make_events())
    assert summary["frames"] == 10
    assert summary["grabs"] == 3
    assert summary["drops"] == 2
    assert summary["scored"] == 1
    assert summary["cancels"] == 1
    assert summary["drop_accuracy"] == pytest.approx(0.5)
    assert summary["grab_success_rate"] == pytest.approx(2 / 3)
    assert summary["carry_median_s"] == pytest.approx(1.125)


def test_summarize_occlusion_and_latency():
    frames = make_frames(10, state="DRAG", linked=0) + make_frames(10, state="DRAG", linked=1)
    summary = summarize(frames, [])
    assert summary["drag_frames"] == 20
    assert summary["occlusion_rate"] == pytest.approx(0.5)
    assert summary["hand_p50_ms"] == pytest.approx(10.0)
    assert summary["detect_p95_ms"] == pytest.approx(30.0)


def test_summarize_empty_session():
    summary = summarize([], [])
    assert summary["frames"] == 0
    assert summary["duration_s"] == 0.0
    assert summary["drop_accuracy"] == 0.0


def test_load_session_roundtrip(tmp_path):
    path = tmp_path / "session.jsonl"
    rows = make_frames(3) + make_events()
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    frames, events = load_session(path)

    assert len(frames) == 3
    assert len(events) == 6


def test_render_plot_writes_png(tmp_path):
    path = render_plot(make_frames(30), make_events(), tmp_path / "plot.png")
    assert path.exists()
    assert path.stat().st_size > 1000
