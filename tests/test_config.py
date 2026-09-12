from visiondrop.config import DropZone, YoloConfig, find_zone, is_in_any_zone


def test_find_zone_returns_matching_zone():
    zones = (DropZone(0, 0, 10, 10, label="A"), DropZone(20, 20, 30, 30, label="B"))
    assert find_zone((25, 25), zones).label == "B"
    assert find_zone((5, 5), zones).label == "A"


def test_find_zone_none_outside():
    zones = (DropZone(0, 0, 10, 10, label="A"),)
    assert find_zone((15, 15), zones) is None



def test_yolo_config_defaults():
    config = YoloConfig()
    assert config.model == "yolo11n.pt"
    assert config.track is True
    assert config.classes is None
    assert config.image_size == 640



def test_contains_inside_and_on_edges():
    zone = DropZone(10, 20, 110, 220, label="A")
    assert zone.contains((10, 20))
    assert zone.contains((110, 220))
    assert zone.contains((50, 100))


def test_contains_outside():
    zone = DropZone(10, 20, 110, 220)
    assert not zone.contains((9, 100))
    assert not zone.contains((111, 100))
    assert not zone.contains((50, 19))
    assert not zone.contains((50, 221))


def test_is_in_any_zone():
    zones = (DropZone(0, 0, 10, 10), DropZone(20, 20, 30, 30, label="B"))
    assert is_in_any_zone((5, 5), zones)
    assert is_in_any_zone((25, 25), zones)
    assert not is_in_any_zone((15, 15), zones)
