import json

from visiondrop.session import SessionRecorder


def test_recorder_writes_jsonl(tmp_path):
    path = tmp_path / "session.jsonl"
    recorder = SessionRecorder(path)
    recorder.frame(
        0, 1.5, "HOVER", (10.2, 20.8), hands=1, objects=2, linked=1,
        hand_ms=9.87, detect_ms=31.2, fps=29.5,
    )
    recorder.event(0, 1.5, "grabbed", object_type="cup", track_id=3)
    recorder.close()

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[0]["type"] == "frame"
    assert records[0]["t"] == 1.5
    assert records[0]["cursor"] == [10.2, 20.8]
    assert records[1]["type"] == "event"
    assert records[1]["event"] == "grabbed"
    assert records[1]["track_id"] == 3


def test_recorder_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "session.jsonl"
    with SessionRecorder(path) as recorder:
        recorder.event(0, 0.0, "grabbed")
    assert path.exists()


def test_disabled_recorder_is_noop():
    recorder = SessionRecorder(None)
    recorder.frame(0, 0.0, "IDLE", None, 0, 0, 0, 0.0, 0.0, 0.0)
    assert not recorder.enabled
    recorder.close()


def test_none_cursor_is_written_as_null(tmp_path):
    path = tmp_path / "s.jsonl"
    with SessionRecorder(path) as recorder:
        recorder.frame(0, 0.0, "IDLE", None, 0, 0, 0, 0.0, 0.0, 0.0)
    assert json.loads(path.read_text())["cursor"] is None
