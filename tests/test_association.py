import math

from visiondrop.association import associate_hands, hand_span, point_to_bbox_distance
from visiondrop.hands import INDEX_TIP, MIDDLE_FINGER_MCP, THUMB_TIP, WRIST, build_hand


class FakeLandmark:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


def make_hand(cursor=(100, 100), span=100, width=640, height=480):
    def lm(px, py):
        return FakeLandmark(px / width, py / height)

    landmarks = [lm(*cursor) for _ in range(21)]
    landmarks[THUMB_TIP] = lm(cursor[0] - 10, cursor[1])
    landmarks[INDEX_TIP] = lm(cursor[0] + 10, cursor[1])
    landmarks[WRIST] = lm(cursor[0], cursor[1] + span)
    landmarks[MIDDLE_FINGER_MCP] = lm(*cursor)
    return build_hand(landmarks, width, height)


def detection(bbox, track_id=None, kind="cup"):
    x, y, w, h = bbox
    return {"type": kind, "bbox": bbox, "center": (x + w // 2, y + h // 2), "track_id": track_id}


def test_point_to_bbox_distance_inside_is_zero():
    assert point_to_bbox_distance((50, 50), (0, 0, 100, 100)) == 0.0


def test_point_to_bbox_distance_outside():
    assert point_to_bbox_distance((-3, -4), (0, 0, 10, 10)) == 5.0
    assert point_to_bbox_distance((15, 5), (0, 0, 10, 10)) == 5.0
    assert point_to_bbox_distance((50, 50), (0, 0, 10, 10)) == math.hypot(40, 40)


def test_hand_span_is_wrist_to_middle_mcp():
    hand = make_hand(cursor=(100, 100), span=120)
    assert hand_span(hand) == 120.0


def test_associates_nearest_object_within_radius():
    hand = make_hand(cursor=(100, 100), span=200)
    near = detection((90, 90, 40, 40), track_id=1)
    far = detection((300, 300, 40, 40), track_id=2)

    associations = associate_hands([hand], [far, near])

    assert len(associations) == 1
    assert associations[0].hand_index == 0
    assert associations[0].detection["track_id"] == 1
    assert associations[0].distance == 0.0


def test_ignores_objects_beyond_radius():
    hand = make_hand(cursor=(100, 100), span=40)
    far = detection((500, 500, 10, 10))
    assert associate_hands([hand], [far]) == []


def test_radius_scales_with_hand_size():
    edge = detection((320, 80, 20, 20))
    big_hand = make_hand(cursor=(100, 100), span=300)
    small_hand = make_hand(cursor=(100, 100), span=30)

    assert len(associate_hands([big_hand], [edge])) == 1
    assert associate_hands([small_hand], [edge]) == []


def test_empty_inputs():
    assert associate_hands([], [detection((0, 0, 10, 10))]) == []
    assert associate_hands([make_hand()], []) == []


def test_association_survives_occlusion_gap():
    hand = make_hand(cursor=(100, 100), span=200)
    cup = detection((90, 90, 40, 40), track_id=7)

    before = associate_hands([hand], [cup])
    during_gap = associate_hands([hand], [])
    after = associate_hands([hand], [cup])

    assert before[0].detection["track_id"] == 7
    assert during_gap == []
    assert after[0].detection["track_id"] == 7
