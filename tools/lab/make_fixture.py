#!/usr/bin/env python3
"""Emit a v2 JSONL session fixture for the Swift engine's replay tests.

Written independently of the Swift synthetic-hand generator on purpose: if the
Swift engine produces the expected events from a file this script wrote, the
format, the coordinate convention and the feature pipeline all agree across the
two implementations. That agreement is the cross-language contract that makes
the port verifiable (ARCHITECTURE.md section 5.3).

Coordinates are in Vision space: origin bottom-left, y growing upward.

    python3 tools/lab/make_fixture.py Tests/Fixtures/pinch-click.jsonl
"""

import json
import sys

WRIST = (0.50, 0.12)
THUMB = {"cmc": (0.47, 0.18), "mcp": (0.45, 0.22), "ip": (0.40, 0.26),
         "tip_open": (0.34, 0.30), "tip_pinch": (0.525, 0.465)}
FINGERS = {
    "index":  {"mcp": (0.53, 0.30), "pip": (0.53, 0.38), "tip": (0.53, 0.46), "curled": (0.53, 0.32)},
    "middle": {"mcp": (0.50, 0.31), "pip": (0.50, 0.40), "tip": (0.50, 0.49), "curled": (0.50, 0.34)},
    "ring":   {"mcp": (0.47, 0.30), "pip": (0.47, 0.38), "tip": (0.47, 0.46), "curled": (0.47, 0.32)},
    "little": {"mcp": (0.44, 0.28), "pip": (0.44, 0.35), "tip": (0.44, 0.42), "curled": (0.44, 0.28)},
}
ORDER = ["index", "middle", "ring", "little"]
CONFIDENCE = 0.87


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def hand(pose, dx=0.0):
    """21 points in HandJoint order: wrist, thumb x4, then four fingers x4."""
    curled = pose == "point"
    points = [WRIST, THUMB["cmc"], THUMB["mcp"], THUMB["ip"],
              THUMB["tip_pinch"] if pose == "pinch" else THUMB["tip_open"]]
    for name in ORDER:
        f = FINGERS[name]
        # The index stays extended for a pinch; the thumb comes to meet it.
        tip = f["curled"] if (curled and name != "index") else f["tip"]
        points += [f["mcp"], f["pip"], mid(f["pip"], tip), tip]
    return [[round(x + dx, 6), round(y, 6), CONFIDENCE] for x, y in points]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "Tests/Fixtures/pinch-click.jsonl"
    header = {
        "type": "header", "version": 2, "tracker": "synthetic.fixture.v1",
        "camera": {"id": "synthetic", "width": 1280, "height": 720, "fps": 60, "mirrored": True},
        "displays": [{"id": 1, "bounds": [0, 0, 1920, 1080], "scale": 2.0, "primary": True}],
        "started": "2026-09-22T12:00:00Z", "video": None,
    }

    # Point, pinch, release: the canonical click. Held still through the pinch
    # so it stays a click rather than becoming a drag.
    poses = ["point"] * 3 + ["pinch"] * 6 + ["point"] * 6
    lines = [json.dumps(header, sort_keys=True)]
    for index, pose in enumerate(poses):
        lines.append(json.dumps({
            "type": "frame",
            "t": round(index / 60.0, 6),
            "hands": [{"handedness": "right", "score": 0.94, "points": hand(pose)}],
        }, sort_keys=True))

    with open(out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"wrote {out}: {len(poses)} frames")


if __name__ == "__main__":
    main()
