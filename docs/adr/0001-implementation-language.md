# ADR 0001 — Implementation language and runtime stack

- **Status:** Accepted; partially implemented (2026-09-24)
- **Date:** 2026-09-22
- **Deciders:** Anish Giri
- **Supersedes:** the stack implied by [PLAN.md](../../PLAN.md) §5 (Python + MediaPipe + PyObjC)
- **Related:** [SRS.md](../SRS.md), [ARCHITECTURE.md](../ARCHITECTURE.md)

---

## 1. Context

VisionDrop is a macOS-only touchless interaction layer: a webcam tracks the hand, a transparent
click-through overlay draws a cursor and gesture feedback over the real desktop, and synthetic
mouse/keyboard events drive whatever application is underneath.

At the time of the decision, Phases 0 and 1 existed in Python (`src/visiondrop`, 1319 lines, 36 passing
tests): camera capture, a MediaPipe wrapper, scale-free hand features, One Euro filtering, a hysteretic
pinch state machine, cursor mapping, and JSONL record/replay. The platform-facing overlay, event
injection, Canvas, magnifier, and OCR were then unwritten.

The Swift direction is now partially implemented: the package includes a pure engine, deterministic
v2 replay, AVFoundation capture, Vision tracking, a headless CLI, and a menu-bar app shell with a
cancellable live camera → Vision → engine loop. There is still no click-through overlay, event
injection, Canvas, Lens, signed distribution, or completed evaluation corpus. This ADR records the
accepted stack decision; it is not evidence that those remaining surfaces are implemented.

### 1.1 What the system actually spends time on

This is the decisive observation, and it cuts against the intuition that a "real-time computer
vision app" needs a systems language.

| Work | Who performs it | Cost per frame |
| --- | --- | --- |
| Camera frame acquisition | AVFoundation (OS) | ~16 ms at 60 fps (pipeline, not CPU) |
| Hand landmark inference | Neural Engine / GPU (OS or MediaPipe C++) | 8–12 ms on ANE, 30–40 ms on CPU fallback |
| Feature math on 21 points | **Our code** | ~5 µs |
| One Euro filter + pinch FSM | **Our code** | ~1 µs |
| Overlay compositing | Core Animation / GPU (OS) | one 60 Hz frame |
| Event injection | CoreGraphics (OS) | < 1 ms |
| OCR, screen capture | Vision / ScreenCaptureKit (OS) | on demand |

Our own arithmetic is **six microseconds of work on 21 points**. It is four orders of magnitude
below the frame budget. No language choice can make it matter.

What *does* matter is everything around it:

1. **How cleanly the language binds to AVFoundation, Vision, AppKit, CoreGraphics and
   ScreenCaptureKit** — because that is where 90% of the remaining code lives.
2. **How well the language behaves in a 60 Hz main-thread run loop** alongside a concurrent
   inference pipeline — jitter, not throughput, is the user-visible failure mode.
3. **How hard it is to ship as a signed, notarized `.app`** — macOS binds TCC permission grants
   (Camera, Accessibility, Screen Recording) to a code signature, so packaging is not a
   last-mile concern; it gates development.

The language decision is a **binding-quality and distribution decision**, not a performance one.

### 1.2 A defect found while evaluating the options

While reading the current engine to estimate porting cost, the following was verified by
experiment (`src/visiondrop/features.py:36`):

```python
def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))
```

`landmarks` is a `(21, 3)` array of MediaPipe's `[x, y, z]`, so **every distance in the feature
layer is 3D and includes MediaPipe's depth term**. Meanwhile `_scale_points` multiplies column 0
by the frame aspect ratio and leaves `z` alone, so the norm mixes an aspect-corrected `x` with an
uncorrected `z`.

MediaPipe documents `z` as using "roughly the same scale as `x`", with the wrist as origin. In the
test fixture the hand scale is 0.188 and the true 2D pinch distance is 0.007, so a realistic
thumb-vs-index depth difference of 0.05 is **~0.3× the hand scale** — far larger than the signal
being measured. Measured over 200 randomized runs:

| Injected z spread | Resulting `pinch_ratio` | With z = 0 |
| --- | --- | --- |
| ±0.02 | 0.053 – 0.390 | 0.054 |
| ±0.05 | 0.046 – 0.901 | 0.054 |
| ±0.10 | 0.031 – 2.078 | 0.054 |

The thresholds are `enter_ratio = 0.45`, `exit_ratio = 0.65`. **The depth term alone can move a
firmly-closed pinch across both thresholds.**
The original prototype tests all passed because every fixture in `tools/lab/tests/helpers.py` set `z = 0.0`. The suite was
entirely 2D while the live path was 3D. This is the same class of failure PLAN.md §2 was written to
eliminate — a threshold compared against a quantity that carries an uncontrolled term — and it
remains a known limitation of the Python prototype.

This does not by itself decide the language, but it does two things: it establishes that the
tracker's coordinate contract must be explicit and tested, and it removes the assumption that the
existing Python engine is a finished component to be preserved.

---

## 2. Decision drivers

| # | Driver | Why it matters here |
| --- | --- | --- |
| D1 | Native binding quality to Apple frameworks | ~90% of unwritten code is OS calls |
| D2 | Determinism of a 60 Hz render loop (no GC/GIL pauses) | Jitter is the user-visible defect |
| D3 | Code signing, hardened runtime, notarization, TCC | Permissions are bound to the signature |
| D4 | Testability of gesture logic without camera or GUI | The replay-based regression gate must survive |
| D5 | Single-maintainer velocity | One developer, evenings; no toolchain tax |
| D6 | Dependency and bundle footprint | Fewer moving parts to sign, audit and update |
| D7 | Access to on-device ML acceleration (ANE) | Latency budget depends on it |
| D8 | Cross-platform optionality | Explicitly deferred: PLAN.md §11.1 decided macOS-only |

D8 is listed to be discharged, not satisfied. Cross-platform is a stated non-goal; any option
whose main benefit is portability is being charged for something the project does not want.

---

## 3. Options considered

### Option A — Swift 6, Apple frameworks only

Vision for hand pose, AVFoundation for capture, AppKit + Core Animation for the overlay,
CoreGraphics for event injection, ScreenCaptureKit for the magnifier, Vision for OCR.
**Zero third-party runtime dependencies.**

The enabling discovery is that `VNDetectHumanHandPoseRequest` returns **21 landmarks with the same
topology as MediaPipe** — one wrist plus four joints per finger:

| MediaPipe index | Vision joint | MediaPipe index | Vision joint |
| --- | --- | --- | --- |
| 0 | `.wrist` | 9–12 | `.middleMCP/PIP/DIP/Tip` |
| 1–4 | `.thumbCMC/MP/IP/Tip` | 13–16 | `.ringMCP/PIP/DIP/Tip` |
| 5–8 | `.indexMCP/PIP/DIP/Tip` | 17–20 | `.littleMCP/PIP/DIP/Tip` |

The joint topology maps 1:1. Feature, filter, and state-machine concepts transfer without redesign,
but recordings do not transfer byte-for-byte: the prototype's headerless v1 landmark arrays contain
`[x, y, z]`, while the Swift v2 contract is a versioned header plus `[x, y, confidence]` or missing.
The Swift reader rejects v1. Conversion requires an explicit tool to discard the contaminated depth
term, define confidence and handedness, and emit a valid v2 header; no converter is implemented yet.

- **+** No FFI anywhere; Vision/AppKit/CoreGraphics are first-party.
- **+** Runs on the Neural Engine (~8 ms) with automatic GPU/CPU fallback.
- **+** Swift Concurrency (actors, `@MainActor`) enforces the "AppKit on the main thread"
  rule *at compile time* under Swift 6 strict concurrency — the exact class of bug that
  causes overlay jitter.
- **+** Ships as a notarized `.app` from one `xcodebuild` invocation; a few MB.
- **+** `os_signpost` gives motion-to-photon latency in Instruments for free — the NFR is
  measurable with no custom instrumentation.
- **−** Vision gives **2D points plus confidence only**: no metric world landmarks. (Given §1.2,
  this is a feature, not a loss — it makes the coordinate contract explicit.)
- **−** `VNHumanHandPoseObservation.chirality` is widely reported as unreliable, frequently
  returning `.right` regardless. Handedness must be derived geometrically.
- **−** Locks the project to Apple platforms. Already the stated intent.

### Option B — Rust

`objc2` / `objc2-app-kit` bindings are real and maintained, and menu-bar apps have been built
this way. But every Vision, AppKit and CoreGraphics call becomes hand-written FFI with manual
memory-management rules, and the Vision hand-pose surface in particular has little precedent.
Rust's headline benefit — memory safety — addresses a risk this workload does not have: there is
no parser, no untrusted input, no manual buffer arithmetic. The gain is real only if D8 is
in scope, and it is not.

- **+** No GC; predictable latency; excellent testing story for the core.
- **−** Every OS interaction is unsafe-adjacent FFI written and maintained by hand.
- **−** App bundling, signing and notarization are bolted on rather than built in.
- **−** Pays a large, permanent integration tax for a benefit the project declined.

### Option C — Rust core + Swift shell

The sophisticated-sounding answer: engine as a Rust staticlib behind a C ABI, Swift app for
capture, overlay and injection.

This is genuinely correct **if and only if** the engine is destined for Windows/Linux. It is not.
What it costs unconditionally: two toolchains, two test harnesses, a hand-maintained C header, a
serialization boundary in the hot path, and debugging that crosses languages. For a solo
maintainer on a macOS-only product, it buys portability that has been explicitly declined and
charges for it every day.

**Rejected as over-engineering.** Reconsider only if §6's revisit trigger fires.

### Option D — C++

MediaPipe's native home, and the only option with direct access to its C++ graph API. But the
overlay, injection, OCR and capture layers would all be written in Objective-C++, there is no
dependency management worth the name, and the build would be the most complex of any option.
Slowest development velocity by a wide margin, for no benefit the alternatives lack.

### Option E — Go

Worst fit. Every AppKit call goes through cgo with per-call overhead; the garbage collector
introduces pauses precisely in the 60 Hz loop where jitter is the defect; `runtime.LockOSThread`
fights AppKit's main-thread requirement; and there is no route to the Neural Engine. Listed for
completeness.

### Option F — Status quo: Python + MediaPipe + PyObjC

Honest accounting of what continuing would mean:

- **+** Phases 0–1 already work; numpy/matplotlib/Jupyter are excellent for offline threshold
  tuning; the fastest possible iteration on *algorithms*.
- **−** The GIL is contended between MediaPipe inference and a PyObjC main-thread run loop
  driving a 60 Hz overlay. MediaPipe releases the GIL inside C++, but interpreter and GC pauses
  land in the render loop.
- **−** Bundle footprint: TensorFlow, OpenCV, MediaPipe and numpy total roughly 500 MB. Signing a
  py2app bundle with hundreds of nested dylibs under the hardened runtime is a recurring,
  well-documented tax — and it must be solved before Phase 3, because TCC grants attach to the
  bundle, not the terminal.
- **−** PyObjC bridging cost is paid per call, in the loop where it hurts.
- **−** The project already carries `requirements.txt` (TensorFlow, Keras, JAX, TensorBoard, ~50
  packages) purely for `legacy/`, which the new engine does not use at all.

Python's strengths are real, but they are **prototyping** strengths. They do not survive contact
with Phases 2–6.

---

## 4. Analysis

Scored against the drivers. ●●● strong, ●● adequate, ● weak.

| Driver | A: Swift | B: Rust | C: Rust+Swift | D: C++ | E: Go | F: Python |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| D1 Apple framework binding | ●●● | ● | ●●● | ●● | ● | ●● |
| D2 60 Hz loop determinism | ●●● | ●●● | ●●● | ●●● | ● | ● |
| D3 Signing / notarization / TCC | ●●● | ● | ●● | ●● | ● | ● |
| D4 Headless testability of logic | ●●● | ●●● | ●●● | ●● | ●●● | ●●● |
| D5 Solo-dev velocity | ●●● | ●● | ● | ● | ●● | ●●● |
| D6 Dependency footprint | ●●● | ●● | ●● | ● | ●● | ● |
| D7 ANE access | ●●● | ● | ●●● | ●● | ● | ●● |
| D8 Cross-platform *(non-goal)* | ● | ●●● | ●●● | ●● | ●●● | ●● |

Swift leads every driver the project actually holds, and loses only the one it has declined.

---

## 5. Decision

**Adopt Swift 6 as the single implementation language, targeting macOS 15.0 (Sequoia) or later,
using Apple frameworks exclusively and no third-party runtime dependencies.**

Concretely:

| Concern | Choice | Replaces |
| --- | --- | --- |
| Hand landmarks | Vision `DetectHumanHandPoseRequest` (ANE) | MediaPipe |
| Camera capture | AVFoundation `AVCaptureSession` | OpenCV `VideoCapture` |
| Overlay | AppKit `NSPanel` + Core Animation, one per `NSScreen` | PyObjC (unwritten) |
| Event injection | CoreGraphics `CGEvent` | pyautogui / PyObjC (unwritten) |
| Screen capture | ScreenCaptureKit `SCStream` | mss (unwritten) |
| OCR | Vision `RecognizeTextRequest` | — (unwritten) |
| Numerics | `simd` + Foundation | numpy |
| Tests | Swift Testing (`@Test` / `#expect`) | pytest |
| Build | Swift Package Manager + Xcode app target | uv |

Supporting decisions:

1. **Hand tracking sits behind a `HandTracking` protocol.** `VisionHandTracker` ships. This is not
   speculative abstraction — it is required by DEC-2 below, which needs two trackers evaluated
   against one recording.
2. **The recorder captures raw video alongside landmarks.** Landmark-only recordings cannot
   compare trackers. This is the evidence base for revisiting the Vision-vs-MediaPipe choice.
3. **The landmark contract is explicitly 2D.** Depth is not part of any feature computation
   unless a tracker supplies calibrated metric landmarks and a test proves the calibration. See
   §1.2; this closes the defect at the type level rather than by convention.
4. **The Python engine is not ported line-by-line and is not dual-maintained.** It is frozen under
   `tools/lab/` with one job — generating and cross-checking JSONL fixtures during the port — and
   is deleted once Swift replay tooling lands in Phase 2. Stated here so the expiry is on record.
5. **Distribution is Developer ID + notarization + hardened runtime, not the Mac App Store.**
   Forced, not chosen: Accessibility permission is unavailable to sandboxed apps, and event
   injection is the product.
6. **Apple silicon is the supported target.** Intel Macs lack the Neural Engine and fall back to
   30–40 ms inference, which does not fit the latency budget. Best-effort, not supported.

---

## 6. Consequences

### Positive

- One language, one toolchain, one build command, one test framework.
- The runtime dependency graph becomes **empty**. Nothing to audit, sign, pin or update but the
  OS itself.
- Bundle drops from ~500 MB to single-digit MB; notarization becomes routine.
- Swift 6 strict concurrency makes "AppKit only on the main thread" a **compile error** rather
  than an intermittent production crash.
- `os_signpost` makes the motion-to-photon NFR measurable in Instruments without custom code.
- The port is small at the arithmetic layer and benefits from a 1:1 landmark topology, but the current
  engine is not a verified recording-port conversion: v1 prototype files are rejected and no v1→v2
  converter exists yet.
- Losing numpy/matplotlib costs some offline analysis convenience. Mitigated by keeping
  `tools/lab/` for the duration of the port.
- Swift's ecosystem for signal processing is thin. Irrelevant at this scale — the entire
  numerical surface is One Euro filtering and 2D distances.

### Neutral / accepted

- `src/visiondrop/` remains runnable but is not dual-maintained as the product. `tools/lab/` remains for
  prototype tests and generating v2 fixtures until cross-language validation is complete.
- `legacy/` and `requirements.txt` remain untouched as historical artifacts. They are not part of
  the product and are not maintained.
### What this forecloses

Windows and Linux ports. Reversing this later means rewriting the engine (~700 lines, cheap) and
the entire platform layer (expensive). That is the real cost of the decision, stated plainly.

---

## 7. Revisit triggers

Reopen this ADR if any of the following becomes true:

1. **Vision hand pose proves inadequate** — pinch F1 below 0.95, or landmark dropout above 5% of
   frames, on the recorded evaluation set. → Add MediaPipe behind `HandTracking`; the protocol and
   video recordings exist precisely for this test.
2. **A non-Apple platform becomes a real requirement.** → Option C (Rust core + Swift shell)
   becomes correct rather than over-engineered.
3. **Inference falls back off the ANE persistently** and the latency budget cannot be met on
   supported hardware. → Reconsider a quantized custom Core ML model.
4. **Swift 6 strict concurrency blocks a needed pattern** in the capture→inference→render
   pipeline. → Re-evaluate; do not disable strict concurrency silently.

---

## 8. References

Apple documentation
- [VNDetectHumanHandPoseRequest](https://developer.apple.com/documentation/vision/vndetecthumanhandposerequest)
- [DetectHumanHandPoseRequest (Swift Vision API)](https://developer.apple.com/documentation/vision/detecthumanhandposerequest)
- [VNHumanHandPoseObservation](https://developer.apple.com/documentation/vision/vnhumanhandposeobservation)
- [Detecting Hand Poses with Vision](https://developer.apple.com/documentation/vision/detecting-hand-poses-with-vision)
- [Detect Body and Hand Pose with Vision — WWDC20 10653](https://developer.apple.com/videos/play/wwdc2020/10653/)
- [Discover Swift enhancements in the Vision framework — WWDC24 10163](https://developer.apple.com/videos/play/wwdc2024/10163/)
- [Capturing screen content in macOS (ScreenCaptureKit)](https://developer.apple.com/documentation/ScreenCaptureKit/capturing-screen-content-in-macos)
- [AXUIElementCopyElementAtPosition](https://developer.apple.com/documentation/applicationservices/1462077-axuielementcopyelementatposition)
- [CGWarpMouseCursorPosition](https://developer.apple.com/documentation/coregraphics/1456387-cgwarpmousecursorposition)
- [VNImagePointForNormalizedPoint](https://developer.apple.com/documentation/vision/vnimagepointfornormalizedpoint(_:_:_:))
- [TN2150: Using Secure Event Input Fairly](https://developer.apple.com/library/archive/technotes/tn2150/_index.html)

Platform behaviour and prior art
- [Detecting hand pose with the Vision framework — Create with Swift](https://www.createwithswift.com/detecting-hand-pose-with-the-vision-framework/)
- [Hand Pose using Vision Framework — Snowdog](https://www.snow.dog/blog/hand-pose-using-vision-framework)
- [Apple Vision Framework: On-Device CV Most Devs Skip](https://blakecrosley.com/blog/vision-framework-built-in)
- [On-Device Pose Estimation on iOS: What Actually Works in Production](https://dev.to/benjamin_pires_59127eddff/on-device-pose-estimation-on-ios-what-actually-works-in-production-not-just-research-papers-48ma)
- [Accessibility Permission in macOS — jano.dev](https://jano.dev/apple/macos/swift/2025/01/08/Accessibility-Permission.html)
- [macOS Input Monitoring, Screen Capture & Accessibility — HackTricks](https://hacktricks.wiki/en/macos-hardening/macos-security-and-privilege-escalation/macos-security-protections/macos-input-monitoring-screen-capture-accessibility.html)
- [macOS Window Levels Explained — Noticky](https://www.noticky.app/en/blog/macos-window-levels-explained)
- [Mac games and cursor warping weirdness — Colin Cornaby](https://www.colincornaby.me/2023/02/mac-games-and-cursor-warping-weirdness/)
- [MouseWarpBug — ioquatix](https://github.com/ioquatix/MouseWarpBug)
- [FB11586064: AXUIElementCopyElementAtPosition blocks input](https://github.com/feedback-assistant/reports/issues/368)
- [Parsing macOS application UI — MacPaw Research](https://research.macpaw.com/publications/how-to-parse-macos-app-ui)
- [Secure Input on macOS — Espanso](https://espanso.org/docs/troubleshooting/secure-input/)
- [objc2-app-kit](https://lib.rs/crates/objc2-app-kit) · [objc2](https://docs.rs/objc2)
- `swift-format` · [`SwiftLint`](https://github.com/realm/SwiftLint) (optional third-party tool; not part of this package)

Interaction research: see [PLAN.md](../../PLAN.md) §3 and §12, which remain the basis for the
gesture vocabulary, filtering and evaluation design. This ADR changes the implementation stack,
not the interaction research.
