# VisionDrop — Architecture and Engineering Standards

| | |
| --- | --- |
| **Status** | Partially implemented, 2026-09-24; the target product architecture remains proposed |
| **Companions** | [SRS.md](SRS.md) (what) · [ADR 0001](adr/0001-implementation-language.md) (why Swift) |
| **Audience** | Whoever implements or reviews VisionDrop 2.0 |

This document covers **how**: module layout, concurrency, the coordinate contract, the platform
hazards discovered during research, testing strategy, and the standards the code is held to.

---

## 1. Module layout

### 1.1 Present source layout

The repository currently has two library targets, two executable targets, and two test targets. This is
the complete Swift source layout; it is not the finished VisionDrop 2.0 module graph:

```
VisionDrop/
├── Package.swift
├── Sources/
│   ├── VisionDropCore/          # platform-independent engine logic and v2 JSONL codec
│   │   ├── Geometry/            # normalized/AppKit/CoreGraphics conversions and displays
│   │   ├── Tracking/            # 2D landmarks, joints, frame observations
│   │   ├── Features/            # scale-free hand features
│   │   ├── Filters/             # One Euro filtering
│   │   ├── Gestures/            # pinch and idle state machines
│   │   ├── Pointer/             # active-box mapping, gain, freeze, clutch
│   │   ├── Recording/           # v2 session model and codec
│   │   ├── Engine.swift
│   │   └── Configuration.swift
│   ├── VisionDropKit/           # Camera/ and Tracking/ only
│   ├── visiondrop-cli/          # info, landmark-only record, deterministic replay
│   └── visiondrop-app/          # menu-bar shell and live camera → Vision → engine loop
├── Tests/
│   ├── VisionDropCoreTests/
│   ├── VisionDropKitTests/      # joint mapping and handedness geometry
│   └── Fixtures/                # one synthetic v2 replay fixture
└── tools/lab/                   # prototype tests and an independent v2 fixture generator
```

The Core/Kit split is present and enforced by target dependencies. Core does not use AppKit, Vision,
file I/O, wall-clock time, or queues. `SessionCodec` implements the present v2 format; v1 Python
recordings are rejected.

### 1.2 Planned product layout

The design in the remainder of this document uses these additional source areas, but they are not
present in the current repository:

```
VisionDropKit/
├── Overlay/       # click-through NSPanel, cursor, feedback, HUD
├── Control/       # safety interlock, event injection, secure-input and AX probes
├── Capture/       # ScreenCaptureKit
├── Recording/     # file-backed recording and video
├── Telemetry/     # signposts and metrics
└── Permissions/   # permission-state degradation matrix

App/              # menu bar, settings, onboarding, Info.plist, entitlements
```

Dwell, swipe, and two-hand gesture machines named in the design are also planned rather than present.
They must not be represented as implemented by the current `Gestures/` directory, which contains only
pinch and idle behavior.

### 1.3 Core types

The present pure-logic core contains:

- `NormalizedPoint`, `ScreenPoint`, `CoordinateSpace`, and `DisplayLayout` for the implemented
  coordinate conversions and display bounds;
- `Landmark`, `HandJoint`, `HandLandmarks`, and `FrameObservation`, with no depth field;
- `HandFeatures`, `OneEuroFilter`, `PinchMachine`, `IdlePose`, and `PointerMap`;
- `Engine`, `EngineConfiguration`, and the v2 `SessionRecording` types.

`HandLandmarks` is where CON-5 is enforced: a landmark is a 2D point and a confidence, so feature
code cannot accidentally consume MediaPipe's depth term. `HandJoint` names the 21 joints rather than
requiring callers to use numeric indexes; the Vision mapping is implemented and tested in Kit.
### 1.4 Kit and the app target

`VisionDropKit` presently contains AVFoundation `CameraSource` and `VisionHandTracker` behind
`HandTracking`. The headless CLI directly sequences capture, inference, recording, and replay. The
`visiondrop-app` target is a `@MainActor` menu-bar shell: it displays camera permission and device
counts, can request camera access, and runs a cancellable camera → Vision → engine loop off the main
actor. The three-context actor/main-actor pipeline described in §2, the overlay, event injector,
settings UI, onboarding, Canvas, and Lens remain planned.
---

## 2. Concurrency model

Three execution contexts. Swift 6 strict concurrency makes the boundaries compile-time errors
rather than intermittent crashes, which is the single largest practical reason for CON-1.

| Context | Runs | Isolation |
| --- | --- | --- |
| **Capture** | AVFoundation delivery callbacks | `AVCaptureVideoDataOutput` queue |
| **Inference** | Vision requests, feature extraction, state machines | `actor TrackingPipeline` |
| **Main** | All AppKit, Core Animation, `CGEvent` posting, menu bar | `@MainActor` |

```
AVCapture queue           actor TrackingPipeline              @MainActor
──────────────────        ──────────────────────────          ──────────────────────
sample buffer      ─────▶ drop if busy (SEN-4)
                          Vision hand pose (ANE)
                          Core.Engine.process(_:)  ─────────▶ overlay update (display link)
                                                              SafetyInterlock.attempt(_:)
                                                                  └─▶ EventInjector
```

Rules, enforced by the compiler wherever possible:

1. **Back-pressure is a drop, never a queue** (SEN-4). The pipeline holds one pending frame. A
   frame arriving while one is in flight replaces it. Stale frames are worse than dropped ones in
   an interactive pointer.
2. **`VisionDropCore` types are `Sendable` value types.** State crosses actor boundaries by copy.
   The engine is the only mutable thing and it lives inside the pipeline actor.
3. **Rendering is pulled, not pushed.** A `CADisplayLink` on the main actor reads the latest
   `EngineState`. Inference and display run at different rates and neither waits on the other.
4. **Nothing blocking on the main actor.** In particular `ElementProbe` (ACT-6) runs on its own
   task with a timeout, because `AXUIElementCopyElementAtPosition` has been observed taking up to
   half a second.
5. **`CGEvent` posting happens on the main actor**, reached only through `SafetyInterlock`.

---

## 3. The coordinate contract

Three coordinate systems with three different origins (SRS §2.7). This is the highest-density
defect area in the project, so it gets one module, distinct types, and golden tests.

```
Vision normalized          AppKit global              CoreGraphics global
(0,1) ┌──────┐ (1,1)       ▲ y up                     ┌──────▶ x
      │      │             │                          │
      │      │             │  origin at bottom-left   │  origin at top-left
(0,0) └──────┘ (1,0)       └──────▶ x  of PRIMARY     ▼ y down   of PRIMARY
  origin bottom-left          screen                    display
```

The types are distinct — `NormalizedPoint`, `AppKitPoint`, `ScreenPoint` — so a conversion cannot
be skipped by accident. `CoordinateSpace` is the only place conversions are written.

Golden tests cover, at minimum: single display; two displays side by side; a secondary display
positioned above the primary and to its left (negative coordinates in both spaces); mixed backing
scale factors (1× beside 2×); and a pointer traversing every boundary (PTR-7).

Mirroring for the user-facing camera is applied **exactly once**, at the sensing boundary, and
recorded in the session header so a recording replays identically (COORD-2, DAT-2).

---

## 4. Platform hazards

Findings from the research that directly shaped requirements. Each is a real, documented macOS
behaviour that would otherwise be discovered late and expensively.

| # | Hazard | Consequence | Response |
| --- | --- | --- | --- |
| H1 | `CGWarpMouseCursorPosition` suppresses hardware mouse events for 0.25 s and produces spurious deltas | Breaks the "physical mouse always works" guarantee, the project's most important safety property | Post `mouseMoved` events instead (ACT-1). If warping is ever unavoidable, zero the suppression interval and re-associate immediately (ACT-2) |
| H2 | `AXUIElementCopyElementAtPosition` can block for ~500 ms against some applications | A single hover query stalls the entire pipeline | Off-path, timed out, result is a hint that may be absent (ACT-6, ACT-7) |
| H3 | `VNHumanHandPoseObservation.chirality` frequently reports `.right` regardless of the actual hand | Two-hand gestures bind to the wrong hand | Derive handedness geometrically (SEN-6, ASM-5) |
| H4 | Secure input mode blocks synthetic keystrokes when a password field has focus | Injection silently does nothing | Detect and show it (SAF-2) — visible degradation, never silent failure |
| H5 | Accessibility permission is unavailable to sandboxed applications | Mac App Store distribution is impossible | Developer ID + notarization (CON-4, APP-6). Decided at M0, not discovered at M7 |
| H6 | `ignoresMouseEvents` alone is not enough; a panel can still take focus | The overlay steals keyboard input from the app underneath | Non-activating panel **and** `canBecomeKey == false` **and** no hide-on-deactivate — all three (OVL-1, OVL-2) |
| H7 | ScreenCaptureKit back-pressures and drops frames if buffers are held | The magnifier stutters and drags down capture | Release `IOSurface`-backed buffers promptly; skip idle frames (LNS-3) |
| H8 | Vision falls back from the ANE to GPU/CPU when the ANE is busy — 8 ms becomes 30–40 ms | The latency budget silently blows | Detect and report the compute unit; surface it in the HUD (ASM-2, R2, OBS-3) |
| H9 | TCC grants bind to the code signature, not the binary path | Permissions granted in development evaporate on a re-sign | Ship the signed, notarized shell at **M0**, before any feature work (R8) |
| H10 | Screen-saver window level is reserved and should not be used in production | Rejected or misbehaving overlay | Use a floating/status level, not `NSScreenSaverWindowLevel` |
| H11 | An `AVCaptureSession` preset selects a format delivering ~16 fps on the built-in camera | Half the frame rate, for free, silently | Select `activeFormat` explicitly and pin `activeVideoMin/MaxFrameDuration` (SRS SEN-1). `.inputPriority` would say so explicitly but is iOS-only |
| H12 | The built-in FaceTime camera publishes **no 60 fps format at any resolution** | The 60 ms motion-to-photon target is unreachable on the default hardware | Split the requirement by camera capability (SRS PERF-1a/b); promote forward prediction from stretch to mitigation |
| H13 | The first Vision request loads and compiles the model, taking seconds | The opening seconds of a session are lost; a short recording captures almost nothing | `VisionHandTracker.warmUp()` before capture starts (SRS PERF-7) |

---

## 5. Testing strategy

### 5.1 The present suite

| Level | Present target or path | What exists now | Needs |
| --- | --- | --- | --- |
| Unit | `VisionDropCoreTests` | Features, filters, pinch/idle machines, pointer and coordinate conversion | Nothing |
| Replay | `VisionDropCoreTests` | In-memory and disk round-trips; deterministic synthetic event sequences | Fixture data only |
| Fixture CLI | `Tests/Fixtures/pinch-click.jsonl` | One synthetic v2 JSONL file checked for one press, click, and no drag | Swift toolchain |
| Kit mapping | `VisionDropKitTests` | Vision joint mapping and geometric handedness | Nothing |

The present suite runs without a camera, display, or TCC permission. The previously described overlay
golden tests, canned-video integration tests, real recorded evaluation corpus, manual release checklist,
and metric baselines are planned, not current coverage.

### 5.2 The fixture rule

> **A fixture that cannot express a value cannot test it.**

This is `MNT-8`, and it exists because of a specific failure. The Python suite has 36 passing
tests. Every one of them constructs hands with `z = 0.0`. The production path receives non-zero
depth from MediaPipe, and the feature layer includes it in every distance — so a firmly-closed
pinch measuring 0.054 in tests can measure 0.90 in reality, crossing both thresholds. The tests
were green and the code was wrong, because the fixtures could not represent the failing input.

Concretely: every fixture generator populates every field the production path can carry, with
realistic non-degenerate values, and property tests assert invariance where invariance is claimed
(scale-free features under distance change, rotation-tolerant features under rotation).

### 5.3 Fixtures

The repository currently commits one **synthetic v2** fixture:
`Tests/Fixtures/pinch-click.jsonl`. `tools/lab/make_fixture.py` generates it independently of the Swift
test helpers. Swift tests cover codec and deterministic engine paths in memory, while CI replays the
committed file through `visiondrop-cli`. Together these check the v2 codec, coordinate convention,
engine path, CLI file path, and a basic event sequence.

It is not an evaluation corpus. Real recorded, labelled sessions, tracker A/B video, a conversion from
the prototype's rejected v1 format, pinch F1, false-click rate, and p99 baselines do not exist yet. The
planned `tools/lab/` Python-to-Swift event-sequence agreement is therefore not complete, and
`tools/lab/` has not reached its deletion milestone.

### 5.4 What is not unit-tested

Stated so it is a decision rather than an oversight: overlay click-through (OVL-1), permission
flows, and the kill switch under real load. No headless test can establish these. They live in the
release checklist and are re-verified on every macOS update (R5).

---

## 6. Coding standards

### 6.1 Toolchain

| | |
| --- | --- |
| Language | Swift 6 language mode in the package; warnings-as-errors build in CI |
| Minimum OS | macOS 15.0 |
| Build | Swift Package Manager. The `visiondrop-app` executable and live tracking loop are present; signing, notarization, and an Xcode app project remain. |
| Tests | Swift Testing (`@Test` / `#expect`) |
| Lint | No SwiftLint configuration or SwiftLint step is currently present. |

### 6.2 Conventions

- **Units and coordinate spaces belong in the type or the name.** `freezeDuration: Duration`, not
  `freezeMs: Double`. `ScreenPoint`, not `CGPoint`. Where a type cannot carry it, the doc comment
  must (MNT-7).
- **No magic numbers.** Every threshold, timing and gain in the SRS lives in `Configuration`
  (CFG-1). A literal in a decision path is a review rejection.
- **Value types by default.** Reference types only for things with genuine identity: windows,
  the camera session, the pipeline actor.
- **Errors are typed and handled.** No `try?` that discards a failure on a path a user can reach
  (REL-4). Every error has a defined user-visible outcome.
- **`public` is deliberate.** Default to `internal`; make something `public` when another target
  genuinely needs it.
- **Documentation comments state the contract**, not the implementation: units, coordinate space,
  valid ranges, what happens at the boundaries.
- **No abstraction without a second implementation or a test that needs it.** `HandTracking` is a
  protocol because SEN-8 and the A/B evaluation require it. That is the bar.

### 6.3 Commits and reviews

- Conventional commit subjects, scoped to a module: `feat(core): hysteretic pinch machine`.
- A commit that changes engine behaviour updates the affected replay fixture's expected sequence
  **in the same commit**, so the diff shows the behavioural change explicitly.
- A commit that touches `Control/` states in the message which interlocks it was checked against.
- Every PR names the SRS requirement IDs it implements or changes.

### 6.4 Current CI

The `.github/workflows/ci.yml` workflow runs on macOS 15 for pushes to `master` and pull requests:

1. `swift build -Xswiftc -warnings-as-errors`
2. strict recursive `swift format lint`
3. `swift test --enable-code-coverage`
4. the `VisionDropCore` ≥ 85% line-coverage gate
5. `visiondrop-cli replay` over every file in `Tests/Fixtures/`
6. expected-event assertions from `Scripts/check-fixtures.sh`

The current fixture check protects the one synthetic event sequence. It does not yet calculate or block
on pinch F1, false-click rate, engine p99, an evaluation-corpus baseline, tag signing/notarization, or
the full planned regression gate in SRS §7.2.

---

## 7. Migration from the Python engine

| Python | Swift | Note |
| --- | --- | --- |
| `features.py` | `Core/Features/HandFeatures.swift` | **Port with the 2D fix.** Not a transcription |
| `filters.py` | `Core/Filters/OneEuroFilter.swift` | Direct port; algorithm is unchanged |
| `gestures.py` | `Core/Gestures/PinchMachine.swift` | Direct port; the FSM is sound |
| `cursor.py` | `Core/Pointer/PointerMap.swift` | Direct port, plus multi-display (PTR-3, PTR-7) |
| `engine.py` | `Core/Engine.swift` | Direct port; drop the Quartz screen-size lookup |
| `tracking.py` | `Kit/Tracking/VisionHandTracker.swift` | Rewritten against Vision |
| `capture.py` | `Kit/Camera/CameraSource.swift` | Rewritten against AVFoundation |
| `telemetry.py` | `Kit/Recording/` + `Kit/Telemetry/` | Rewritten; signposts replace the latency meter |
| `app.py` | `visiondrop-cli` + `App/` | Split: headless tooling vs the app |
| `tools/lab/tests/` | `Tests/VisionDropCoreTests/` | Assertions survive; fixtures gain non-zero fields (MNT-8) |

The engine port is roughly 700 lines of arithmetic with a 1:1 landmark mapping. The verification
is that both implementations produce identical event sequences over the recorded fixtures before
`tools/lab/` is removed.

`legacy/` and `requirements.txt` are historical artifacts. They are not maintained, not in CI, and
not part of the product (SRS Q2).
