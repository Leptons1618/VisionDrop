# VisionDrop

Touchless desktop interaction: a webcam tracks your hand, and a transparent overlay draws a cursor,
gestures, and annotations on top of your real screen. No camera preview is shown — the camera is a sensor.

The project is mid-migration. The new engine lives in `src/visiondrop/`; the two original camera-window
demos have moved to `legacy/`. The full research and roadmap are in [PLAN.md](PLAN.md).

## Status

| Area | State |
| --- | --- |
| Interaction engine (features, filters, pinch FSM, cursor) | Implemented, 36 tests passing |
| CLI (`run`, `replay`, `info`) | Implemented |
| Click-through screen overlay (PyObjC) | Phase 2, not started |
| OS action injection (Quartz) | Phase 3, not started |
| Canvas, shape recognition, zoom/pan, OCR | Phases 4-5, not started |
| Legacy demos | Moved to `legacy/`, unchanged |

## Requirements

- macOS (the overlay, event injection, and OCR layers are macOS-only by design)
- [uv](https://docs.astral.sh/uv/)
- Python 3.11 (uv installs it automatically)
- Webcam

macOS permissions (System Settings → Privacy & Security):

| Permission | Needed for | When |
| --- | --- | --- |
| Camera | Hand tracking | Now |
| Accessibility | Injecting clicks and keys | Phase 3 |
| Screen Recording | Magnifier and OCR | Phase 5 |

Camera access is granted per app. If you run from a terminal, grant the terminal (or your IDE) access to
the camera, or tracking will silently fail to open the device.

## Install

```bash
git clone https://github.com/Leptons1618/VisionDrop.git
cd VisionDrop
uv sync
```

`uv sync` creates `.venv` and installs the engine plus dev tools. The macOS extras (PyObjC, Vision, mss)
are not needed yet; install them when the overlay work starts:

```bash
uv sync --extra macos
```

## Run the engine

```bash
uv run visiondrop run                       # live engine, headless (no camera window)
uv run visiondrop run --debug-window        # opt-in skeleton window with FPS/latency/pinch HUD
uv run visiondrop run --record session.jsonl  # record landmarks for replay
uv run visiondrop info                      # screen size and permission checklist
```

Point with your index finger to move the cursor. Pinch thumb and index to press; hold and move to drag;
a second pinch within 350 ms is a double click. An open, relaxed palm pauses the engine so a resting
hand cannot trigger input. `Ctrl+C` stops.

Replay a recorded session deterministically (used by the tests and for tuning thresholds):

```bash
uv run visiondrop replay session.jsonl --verbose
```

## Tests

```bash
uv run pytest
```

Tests are camera-free. Synthetic hands exercise the feature extraction, and recorded or generated
landmark streams replay through the engine, so gesture logic can be verified in CI.

## Project structure

```
VisionDrop/
├── pyproject.toml            # uv project, console script, extras, dev tools
├── src/visiondrop/
│   ├── app.py                # CLI: run, replay, info
│   ├── engine.py             # landmarks in -> cursor + gesture state out
│   ├── capture.py            # background camera thread, latest-frame handoff
│   ├── tracking.py           # MediaPipe wrapper (2D + world landmarks)
│   ├── features.py           # scale-free hand features (pinch ratio, extension)
│   ├── filters.py            # One Euro filter, EMA, velocity
│   ├── gestures.py           # pinch FSM (hysteresis, debounce, drag, double click)
│   ├── cursor.py             # active-box mapping, gain, freeze-on-click
│   ├── telemetry.py          # FPS, latency, landmark record/replay
│   └── config.py             # tunable thresholds and timings
├── tests/                    # unit + replay tests, synthetic hand helpers
├── legacy/
│   ├── visiondrop_project/   # original demo: hand tracking + yellow object detection
│   └── drag_squares_project/ # original demo: pinch-to-drag squares
├── PLAN.md                   # research synthesis, architecture, roadmap
├── requirements.txt          # dependencies for the legacy demos only
├── GUIDE.md                  # legacy user guide
└── README.md
```

## Legacy demos

The original OpenCV-window demos still work. They use their own dependency file and run from their own
folders (their imports are flat):

```bash
uv python install 3.11
uv venv --python 3.11
uv pip install -r requirements.txt

uv run --no-project --directory legacy/visiondrop_project python vision_drag_drop.py
uv run --no-project --directory legacy/drag_squares_project python drag_squares.py
uv run --no-project --directory legacy/drag_squares_project python gpu_check.py
```

Notes:

- `legacy/visiondrop_project` tracks the hand skeleton and detects yellow objects over a camera feed.
- `legacy/drag_squares_project` drags colored squares with a pinch and draws a motion trail.
- On Apple Silicon, `requirements.txt` marks the NVIDIA-only pins as platform-conditional, so it resolves
  on arm64 macOS. TensorFlow is optional and falls back to CPU.
- See [GUIDE.md](GUIDE.md) for the legacy user guide.

## Design highlights

- **Scale-free gestures.** Pinch distance is divided by hand size (wrist to index MCP), so thresholds do
  not change with camera distance, and finger extension is measured from the wrist so it survives hand
  rotation. The old demo's fixed 0.04 threshold and image-space y-comparison were its two failure modes.
- **Hysteresis and debounce.** Two pinches thresholds plus frame confirmation and a release cooldown
  prevent flicker around the threshold.
- **One Euro filter.** Smooths the cursor while keeping lag low (target under 60 ms), following
  Casiez et al., CHI 2012.
- **Freeze on click.** The cursor holds still when a click fires so a selection lands where you aimed.
- **Explicit idle.** An open palm pauses input, addressing the Midas touch problem.
- **Replayable.** The engine never calls wall-clock time, so every gesture decision can be replayed from
  a recording and regression-tested.

## License

MIT. Third-party components keep their own licenses; see PLAN.md section 3 for the licensing notes on the
research and open-source references.
