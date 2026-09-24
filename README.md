# VisionDrop

VisionDrop 2.0 is planned as a touchless desktop interface: a webcam tracks your hand and a
transparent overlay will draw a cursor, gestures, and annotations over the real screen. No camera
preview is intended in the product; the camera is a sensor. The current implementation status is below.

**VisionDrop 2.0 is under active Swift implementation.** The current repository contains the package,
headless CLI, camera/Vision sensing, a landmark-only recorder, and a replayable interaction engine. The
menu-bar app, click-through overlay, event injection, Canvas, and Lens are not implemented. The Python
code in `src/visiondrop/` is a runnable prototype, not the product implementation. See
[the documents below](#documentation).

The Python + MediaPipe implementation assumed by the original research plan is superseded by Swift and
Apple frameworks ([ADR 0001](docs/adr/0001-implementation-language.md)).

## Documentation

| Document | Contents |
| --- | --- |
| [docs/SRS.md](docs/SRS.md) | Requirements specification: functional, non-functional, interfaces, verification, release plan |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module layout, concurrency model, coordinate contract, platform hazards, coding standards |
| [docs/adr/0001-implementation-language.md](docs/adr/0001-implementation-language.md) | Why Swift and Apple frameworks rather than Rust, Go, C++ or Python |
| [PLAN.md](PLAN.md) | Interaction research: literature review, gesture vocabulary, evaluation design. Sections 5–8, 11, and 13 are superseded. |

## Status

| Milestone | Current state |
| --- | --- |
| M0 — Skeleton | **Partial.** The Swift package, menu-bar app shell, and headless CI are present. Developer ID signing and notarization are not. |
| M1 — Sensing | **Partial.** AVFoundation capture, Vision tracking, and landmark-only JSONL record/replay are present. Video recording, a real evaluation corpus, and the tracker A/B are not. |
| M2 — Engine | **Partial.** Geometry, features, filtering, pinch/idle state machines, pointer mapping, configuration, and deterministic replay are implemented. The milestone's evaluation exit criteria have not been demonstrated. |
| M3 — Overlay | Not implemented. There is no click-through overlay, cursor renderer, or HUD yet. |
| M4 — Control | Not implemented. The engine emits logical gesture events; it does not inject OS events or enforce the planned injection interlocks. |
| M5–M7 — Canvas, Lens, evaluation | Not implemented. |

Current limitations:

- There is no shipping `.app`, overlay, event injection, Canvas, or Lens.
- CI enforces an 85% line-coverage floor for `VisionDropCore`; this README does not publish a current measured percentage.
- The committed replay fixture is synthetic. The real labelled evaluation corpus, pinch-F1 result, false-click measurement, and Vision-versus-MediaPipe A/B do not exist yet.
- Swift recording format v2 is not backward-compatible with the Python prototype's headerless v1 files.
  Version 1 is rejected; converting retained recordings is a separate, explicit data step and no
  converter is currently implemented.

The Python prototype in `src/visiondrop/` remains runnable. Its pinch detector includes MediaPipe's depth
component in every distance while its test fixtures set depth to zero, so a firmly closed pinch can read
as open in live use. The Swift landmark type excludes depth (SRS CON-5, ADR 0001 §1.2).

### Measured so far

| | |
| --- | --- |
| Engine processing | 10-17 µs/frame against a 1 ms budget (SRS PERF-4) |
| Vision hand pose inference | 8-21 ms, mean ~15 ms |
| Built-in FaceTime camera | **30 fps maximum at every resolution it offers** — no 60 fps mode |

That last one matters: it puts ~33 ms of camera latency into a 60 ms motion-to-photon budget, so
the target is now split by camera capability (SRS PERF-1a/1b) rather than assumed.

## Requirements

- macOS 15 or later, on Apple silicon for the supported configuration
- Swift 6 toolchain
- A webcam for recording/tracking
- [uv](https://docs.astral.sh/uv/) and Python 3.11, for the Python prototype only

macOS permissions (System Settings → Privacy & Security):

| Permission | Needed for | When |
| --- | --- | --- |
| Camera | Hand tracking | Now |
| Accessibility | Injecting clicks and keys | M4 |
| Screen Recording | Magnifier and OCR | M6 |

Permissions are granted per code signature, not per binary. Running from a terminal inherits the
terminal's grant; a future signed app bundle would have its own. `swift run visiondrop-cli info` lists
the engine defaults, permission categories, and cameras it can enumerate; it does not request or change
permissions.

## Build and run (Swift)

Requires macOS 15+ and the Swift 6 toolchain on an Apple silicon Mac.

```bash
swift build
swift test
swift run visiondrop-cli info
swift run visiondrop-app                 # menu-bar app shell; camera access is requested from its menu

# Capture a landmark-only v2 recording. The CLI supports --seconds, --device,
# and --no-mirror; run `visiondrop-cli --help` for the current syntax.
swift run visiondrop-cli record session.jsonl --seconds 20
swift run visiondrop-cli replay session.jsonl --verbose
```

The current CI workflow runs these checks on `macos-15`:

```bash
swift build -Xswiftc -warnings-as-errors
swift format lint --strict --recursive Sources Tests
swift test --enable-code-coverage
python3 Scripts/coverage.py --minimum 85
./Scripts/check-fixtures.sh
```

`record` needs Camera permission. Because macOS binds permissions to a code signature, a binary run from
a terminal inherits the terminal's grant. The planned signed app bundle would have its own identity;
that app has not been implemented.

## The Python prototype

```bash
git clone https://github.com/Leptons1618/VisionDrop.git
cd VisionDrop
uv sync
```

`uv sync` creates `.venv` and installs the prototype plus its test tools. PyObjC is optional for the
prototype's screen-size lookup; when it is absent, the prototype uses a 1920×1080 fallback. There is no
Python overlay implementation, so the optional `macos` extra is not a current product prerequisite:

```bash
uv sync --extra macos
```

### Running the prototype

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

### Prototype tests

```bash
uv run pytest
```

Camera-free, but see the caveat in Status: the fixtures are two-dimensional while the live path is
three-dimensional, so the prototype tests pass over a defect they cannot express.

## Project structure

```
VisionDrop/
├── Package.swift             # Swift package: Core, Kit, CLI, app shell, and tests
├── Sources/
│   ├── VisionDropCore/       # pure engine logic and v2 JSONL codec
│   ├── VisionDropKit/        # AVFoundation capture and Vision hand tracking
│   ├── visiondrop-cli/       # info, landmark-only record, deterministic replay
│   └── visiondrop-app/       # minimal menu-bar shell and camera permission UX
├── Tests/
│   ├── VisionDropCoreTests/  # engine, geometry, recording, synthetic replay
│   ├── VisionDropKitTests/   # Vision joint mapping and handedness geometry
│   └── Fixtures/             # committed v2 JSONL replay fixtures
├── Scripts/                  # coverage and fixture gates
├── .github/workflows/        # headless macOS CI
├── docs/                     # SRS, architecture, ADR
├── tools/lab/                # Python prototype tests and v2 fixture generator
├── src/visiondrop/           # runnable Python/MediaPipe prototype (not Swift product code)
├── legacy/                   # original OpenCV-window demos; unmaintained
├── pyproject.toml            # uv project for the Python prototype
├── GUIDE.md                  # legacy demo guide
└── PLAN.md                   # research plus superseded proposal sections
```
There is no `App/` bundle or click-through overlay, event injection, Canvas, or Lens source yet.
The `visiondrop-app` executable is a minimal menu-bar shell; `docs/ARCHITECTURE.md` distinguishes that
present shell from the planned product layers.

## Legacy demos

The original OpenCV-window demos are historical examples and are not part of the Swift product. They use
their root `requirements.txt` and must run from their own directories because their imports are flat:

```bash
uv python install 3.11
uv venv --python 3.11
uv pip install -r requirements.txt

uv run --no-project --python "$PWD/.venv/bin/python" \
  --directory legacy/visiondrop_project python vision_drag_drop.py
uv run --no-project --python "$PWD/.venv/bin/python" \
  --directory legacy/drag_squares_project python drag_squares.py
uv run --no-project --python "$PWD/.venv/bin/python" \
  --directory legacy/drag_squares_project python gpu_check.py
```

Notes:

- `legacy/visiondrop_project` tracks the hand skeleton and detects yellow objects over a camera feed.
- `legacy/drag_squares_project` drags colored squares with a pinch and draws a motion trail.
- On Apple silicon, `requirements.txt` excludes the NVIDIA-only TensorFlow packages; the demo catches
  unavailable TensorFlow GPU setup and continues on CPU.
- See [GUIDE.md](GUIDE.md) for the legacy user guide.

## Implemented design highlights

- **2D landmarks.** Swift feature computation has no MediaPipe depth component to contaminate distances.
- **Scale-free pinch.** Pinch distance is divided by hand size; tests cover scale, translation, and
  rotation invariance.
- **Hysteresis and debounce.** Two thresholds, frame confirmation, and release cooldown suppress chatter.
- **One Euro filter.** Smooths the pointer using an explicit per-frame timestamp.
- **Freeze on click.** The pointer holds still when a logical click fires.
- **Explicit idle.** A resting open palm suppresses gesture events.
- **Replayable.** The engine accepts explicit timestamps and has no wall-clock dependency. Current CI
  protects one synthetic v2 fixture, not a real evaluation corpus.

## License

MIT. Third-party components keep their own licenses; see PLAN.md section 3 for the licensing notes on the
research and open-source references.
