"""Integration checks against real sample media (run scripts/fetch_samples.py)."""

from pathlib import Path

import cv2
import pytest

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def sample(name):
    path = SAMPLES / name
    if not path.exists():
        pytest.skip(f"missing {name}; run: python scripts/fetch_samples.py")
    return cv2.imread(str(path))


def test_hand_tracker_finds_hands():
    from visiondrop.hands import HandTracker

    with HandTracker() as tracker:
        hands = tracker.process(sample("woman_hands.jpg"))

    assert hands
    assert all(0.0 <= hand.pinch_ratio <= 2.0 for hand in hands)


def test_gesture_recognizer_labels_thumb_up():
    from visiondrop.hands import HandTracker

    with HandTracker() as tracker:
        hands = tracker.process(sample("thumb_up.jpg"))

    assert hands
    assert any(hand.gesture == "Thumb_Up" for hand in hands)


def test_yolo_detects_bus():
    from visiondrop.config import YoloConfig
    from visiondrop.objects import YoloDetector

    detector = YoloDetector(YoloConfig(classes=("bus",)))
    detections = detector.detect_objects(sample("bus.jpg"))

    assert any(detection["type"] == "bus" for detection in detections)


def test_replay_reproduces_interaction_metrics(tmp_path):
    from unittest import mock

    from visiondrop.analysis import load_session, summarize
    from visiondrop.app import run
    from visiondrop.config import AppConfig

    frame = sample("bus.jpg")
    height, width = frame.shape[:2]
    video = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (width, height))
    for _ in range(6):
        writer.write(frame)
    writer.release()

    logs = [tmp_path / "run_a.jsonl", tmp_path / "run_b.jsonl"]
    for log in logs:
        config = AppConfig(source=str(video), log_path=str(log))
        with mock.patch("visiondrop.app.cv2.imshow"), \
             mock.patch("visiondrop.app.cv2.waitKey", return_value=-1), \
             mock.patch("visiondrop.app.cv2.destroyAllWindows"):
            assert run(config) == 0

    frames_a, events_a = load_session(logs[0])
    frames_b, events_b = load_session(logs[1])

    assert [f["t"] for f in frames_a] == [f["t"] for f in frames_b]
    assert [f["state"] for f in frames_a] == [f["state"] for f in frames_b]
    assert [e["event"] for e in events_a] == [e["event"] for e in events_b]

    summary_a = summarize(frames_a, events_a)
    summary_b = summarize(frames_b, events_b)
    for key in (
        "frames", "duration_s", "grabs", "drops", "scored", "cancels",
        "grab_success_rate", "drop_accuracy", "carry_median_s",
        "drag_frames", "occlusion_rate",
    ):
        assert summary_a[key] == summary_b[key]
