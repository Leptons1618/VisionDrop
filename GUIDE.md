# Legacy VisionDrop Demo Guide

> This guide covers only the historical OpenCV demo in
> `legacy/visiondrop_project/`. It does not describe VisionDrop 2.0 or the Swift
> package. See `README.md` for the current project and `docs/SRS.md` for the
> planned product.

## What the legacy demo does

The demo opens a camera preview, draws MediaPipe hand landmarks, and detects
yellow objects. A red dot marks the hand center. When that center enters one of
the blue drop-zone rectangles, the dot changes to green. Press `q` or `Ctrl+C`
to quit.

## Setup

From the repository root, create a Python 3.11 environment and install the root
legacy dependency file:

```bash
uv python install 3.11
uv venv --python 3.11
uv pip install -r requirements.txt
```

The demo must run from its own directory because its local imports are flat:

```bash
uv run --no-project --directory legacy/visiondrop_project \
  python vision_drag_drop.py
```

## Configuration

Edit `legacy/visiondrop_project/config.py`, not a root-level `config.py`.

- `CAMERA_INDEX` selects the camera input.
- `FRAME_WIDTH` and `FRAME_HEIGHT` request the preview resolution.
- `HAND_DETECTION_CONFIDENCE` and `HAND_TRACKING_CONFIDENCE` tune MediaPipe.
- `DROP_ZONES` uses `(x1, y1, x2, y2)` coordinates in the displayed, mirrored
  frame.
- `COLORS` contains the red hand-center dot, green in-zone dot, and blue zones.

The drop zones are video-frame pixels, not desktop coordinates. Resizing the
window or changing the camera resolution may move their apparent size.

## Troubleshooting

- **No camera feed:** check `CAMERA_INDEX` and close other applications using
  the camera.
- **Poor hand tracking:** improve even lighting, keep the hand visible, and try
  a larger camera frame.
- **Poor object detection:** use well-lit yellow objects and adjust the HSV
  bounds in `legacy/visiondrop_project/object_detector.py`.
- **Drop zones do not align:** remember that the preview is horizontally
  flipped before landmarks and objects are processed.

## Related legacy demo

`legacy/drag_squares_project/` is a separate pinch-to-drag demo and has its own
flat imports. Run it from that directory; it is not covered by this guide.
