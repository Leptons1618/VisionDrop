import numpy as np
import pytest

from visiondrop.config import ColorDetectionConfig
from visiondrop.objects import ColorObjectDetector, create_object_detector, parse_yolo_results


def yellow_frame():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[60:180, 80:240] = (0, 255, 255)  # BGR yellow
    return frame


def test_color_detector_finds_yellow_blob():
    detections = ColorObjectDetector().detect_objects(yellow_frame())
    assert len(detections) == 1
    detection = detections[0]
    assert detection["type"] == "yellow"
    x, y, w, h = detection["bbox"]
    assert 75 <= x <= 85
    assert 55 <= y <= 65
    assert detection["track_id"] is None


def test_color_detector_ignores_empty_frame():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    assert ColorObjectDetector().detect_objects(frame) == []


def test_color_detector_respects_min_area():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[10:14, 10:14] = (0, 255, 255)
    config = ColorDetectionConfig(min_area=1000)
    assert ColorObjectDetector(config).detect_objects(frame) == []


def test_factory_returns_color_detector():
    assert isinstance(create_object_detector("color"), ColorObjectDetector)


def test_factory_rejects_unknown_kind():
    with pytest.raises(ValueError):
        create_object_detector("magic")


class FakeTensor:
    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value

    def tolist(self):
        return self._value


class FakeBox:
    def __init__(self, cls, conf, xyxy, track_id=None):
        self.cls = FakeTensor(cls)
        self.conf = FakeTensor(conf)
        self.xyxy = [FakeTensor(xyxy)]
        self.id = FakeTensor(track_id) if track_id is not None else None


class FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


NAMES = {0: "person", 1: "bicycle", 2: "cup"}


def test_parse_yolo_results_converts_boxes():
    results = [FakeResult([FakeBox(2, 0.9, [10, 20, 60, 100], track_id=4)])]

    detections = parse_yolo_results(NAMES, results)

    assert len(detections) == 1
    detection = detections[0]
    assert detection["type"] == "cup"
    assert detection["bbox"] == (10, 20, 50, 80)
    assert detection["center"] == (35, 60)
    assert detection["confidence"] == pytest.approx(0.9)
    assert detection["track_id"] == 4


def test_parse_yolo_results_filters_classes():
    results = [
        FakeResult([FakeBox(0, 0.9, [0, 0, 10, 10]), FakeBox(2, 0.8, [20, 20, 40, 40])])
    ]
    detections = parse_yolo_results(NAMES, results, allowed_ids={2})
    assert [d["type"] for d in detections] == ["cup"]


def test_parse_yolo_results_without_tracking():
    results = [FakeResult([FakeBox(2, 0.5, [1, 2, 3, 4])])]
    assert parse_yolo_results(NAMES, results)[0]["track_id"] is None


def test_parse_yolo_results_handles_missing_boxes():
    assert parse_yolo_results(NAMES, [FakeResult(None)]) == []
