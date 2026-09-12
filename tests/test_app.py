from visiondrop.app import parse_args, parse_classes, parse_source


def test_parse_source_numeric_becomes_index():
    assert parse_source("0") == 0
    assert parse_source("2") == 2


def test_parse_source_path_stays_string():
    assert parse_source("clip.mp4") == "clip.mp4"
    assert parse_source("/dev/video0") == "/dev/video0"


def test_parse_classes_splits_and_trims():
    assert parse_classes("cup, bottle ,cell phone") == ("cup", "bottle", "cell phone")


def test_parse_classes_empty_values():
    assert parse_classes(None) is None
    assert parse_classes("") is None
    assert parse_classes(" , ") is None


def test_default_args():
    args = parse_args([])
    assert args.source == "0"
    assert args.model_dir is None
    assert args.log is None
    assert args.detector == "yolo"
    assert args.condition == "pinch"
    assert args.classes is None
    assert args.imgsz is None
    assert args.no_objects is False
    assert args.debug is False
    assert args.log_level == "INFO"


def test_overrides():
    args = parse_args([
        "--source", "1",
        "--width", "640",
        "--detector", "color",
        "--classes", "cup,bottle",
        "--imgsz", "480",
        "--no-objects",
        "--debug",
        "--log-level", "DEBUG",
    ])
    assert args.source == "1"
    assert args.width == 640
    assert args.detector == "color"
    assert args.classes == "cup,bottle"
    assert args.imgsz == 480
    assert args.no_objects is True
    assert args.debug is True
    assert args.log_level == "DEBUG"
