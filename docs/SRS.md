# VisionDrop — Software Requirements Specification

| | |
| --- | --- |
| **Document** | SRS, VisionDrop 2.0 |
| **Version** | 1.0 (implementation baseline) |
| **Date** | 2026-09-24 |
| **Author** | Anish Giri |
| **Status** | Active specification with partial implementation. M1 and M2 have code, but no milestone is accepted and the 2.0 acceptance criteria have not been demonstrated. |
| **Supersedes** | [PLAN.md](../PLAN.md) §5–§8 (architecture, feature plan, roadmap) |
| **Companions** | [ADR 0001 — implementation language](adr/0001-implementation-language.md) · [ARCHITECTURE.md](ARCHITECTURE.md) |

---

## Table of contents

1. [Introduction](#1-introduction)
2. [Overall description](#2-overall-description)
3. [Functional requirements](#3-functional-requirements)
4. [External interface requirements](#4-external-interface-requirements)
5. [Non-functional requirements](#5-non-functional-requirements)
6. [Data requirements](#6-data-requirements)
7. [Verification and validation](#7-verification-and-validation)
8. [Release plan](#8-release-plan)
9. [Risks](#9-risks)
10. [Open questions](#10-open-questions)
11. [Traceability](#11-traceability)

---

## 1. Introduction

### 1.1 Purpose

This document specifies the requirements for VisionDrop 2.0, a macOS application that turns a
webcam into a touchless input device for the desktop. It is written for the implementer, and it is
the contract that the test suite verifies against.

It replaces the architecture and roadmap sections of PLAN.md. PLAN.md remains authoritative for
the **interaction research** — the gesture vocabulary, filtering approach and evaluation protocol
are taken from the literature reviewed there and are not re-derived here.

### 1.2 Scope

**In scope.** A menu-bar application that:

- tracks one or two hands from the built-in or an external webcam, with no camera preview shown;
- draws a cursor, gesture feedback and annotations on a transparent, click-through overlay above
  all other windows on every display;
- injects synthetic mouse and keyboard events so that ordinary applications can be operated
  without touching the trackpad;
- provides three modes — Pointer, Canvas and Lens;
- records and replays landmark sessions so that gesture behaviour is regression-tested offline.

**Out of scope for 2.0.** Windows or Linux support; any network feature, account or telemetry
upload; multi-user or remote operation; training or fine-tuning of vision models; voice input;
mobile or visionOS clients; Mac App Store distribution (structurally excluded — see CON-4).

### 1.3 Definitions

| Term | Meaning |
| --- | --- |
| **Landmark** | One of 21 hand joint positions returned by the tracker, in normalized image coordinates |
| **Hand scale** | Distance from wrist to index MCP; the normalizer that makes thresholds camera-distance-invariant |
| **Pinch ratio** | Thumb-tip to index-tip distance divided by hand scale; dimensionless |
| **Active box** | The sub-rectangle of the camera frame mapped onto the full screen, so the user need not reach the frame edges |
| **Engage / Idle** | Explicit states that gate whether gestures may produce OS events; the defence against Midas touch |
| **Midas touch** | Unintended activation caused by a system that cannot tell intentional gestures from incidental motion |
| **Motion-to-photon** | Elapsed time from physical hand movement to the corresponding pixel change on screen |
| **Interlock** | A condition that unconditionally suppresses event injection (see SAF-*) |
| **TCC** | macOS Transparency, Consent and Control — the privacy permission system |
| **Replay** | Re-running the engine deterministically over a recorded landmark stream |
| **Golden test** | A test asserting output matches a committed reference, used for overlay geometry |

### 1.4 References

- [ADR 0001 — implementation language and runtime stack](adr/0001-implementation-language.md)
- [ARCHITECTURE.md](ARCHITECTURE.md) — module layout, concurrency model, coding standards
- [PLAN.md](../PLAN.md) §3 — interaction research synthesis; §12 — bibliography
- Casiez, Roussel & Vogel, *1€ Filter*, CHI 2012 — jitter/lag targets in PERF-3
- Hosseini et al., *Towards a Consensus Gesture Set*, CHI 2023 — gesture vocabulary in ENG-8

### 1.5 Requirement conventions

Each requirement has an identifier, a **shall** statement, a priority and a verification method.

**Priority (MoSCoW):** `M` must have — 2.0 does not ship without it · `S` should have · `C` could
have · `W` won't have this release, recorded to bound scope.

**Verification method:** `T` automated test · `D` demonstration against a scripted scenario ·
`A` analysis or measurement · `I` inspection of code or configuration.

Identifier prefixes: `SEN` sensing · `ENG` engine · `PTR` pointer · `OVL` overlay ·
`ACT` OS actions · `SAF` safety · `MOD` modes · `CNV` canvas · `LNS` lens · `CFG` configuration ·
`REC` recording · `APP` application · `PERF` `REL` `PRV` `SEC` `ACC` `USE` `MNT` `OBS` `PRT`
non-functional · `CON` constraint · `ASM` assumption.

---

## 2. Overall description

### 2.1 Product perspective

VisionDrop is a standalone, self-contained macOS application. It has no server, no account and no
network dependency. It sits between the camera and the rest of the desktop:

```
   ┌──────────┐   frames    ┌───────────────┐  landmarks  ┌────────────────┐
   │  Webcam  │────────────▶│   Sensing     │────────────▶│ Interaction    │
   └──────────┘             │ AVFoundation  │  (21 pts,   │ engine         │
                            │ + Vision/ANE  │   2D + conf)│ features,      │
                            └───────────────┘             │ filters, FSMs  │
                                                          └───────┬────────┘
                                          ┌───────────────────────┼───────────────────┐
                                          │                       │                   │
                                          ▼                       ▼                   ▼
                                 ┌────────────────┐     ┌──────────────────┐  ┌───────────────┐
                                 │ Overlay        │     │ Safety interlock │  │ Recorder      │
                                 │ NSPanel/CALayer│     │  (SAF-*)         │  │ JSONL + video │
                                 │ per display    │     └────────┬─────────┘  └───────────────┘
                                 └────────────────┘              │ permits
                                          │ draws               ▼
                                          │              ┌──────────────────┐
                                          │              │ Action injector  │
                                          ▼              │ CGEvent          │
                                 ┌─────────────────────────────────┐        │
                                 │      The user's real desktop    │◀───────┘
                                 └─────────────────────────────────┘
```

The critical structural property: **the overlay never intercepts input.** It is click-through, so
the physical mouse and trackpad continue to work unchanged at all times. VisionDrop adds a second
input source; it never takes one away.

### 2.2 Product functions

| | Function |
| --- | --- |
| F1 | Track hands from a webcam without displaying a camera preview |
| F2 | Convert landmarks into a smoothed screen-space pointer |
| F3 | Recognise a small, research-backed gesture vocabulary |
| F4 | Render continuous visual feedback over the real desktop |
| F5 | Drive the OS: move, click, right-click, drag, scroll, key shortcuts |
| F6 | Suppress input whenever it would be unsafe or unintended |
| F7 | Draw and annotate over the screen (Canvas mode) |
| F8 | Magnify and pan a screen region, and target OCR-detected text (Lens mode) |
| F9 | Record and replay sessions for tuning and regression testing |
| F10 | Configure thresholds, gestures and permissions from a menu-bar UI |

### 2.3 User classes

| Class | Description | Priority |
| --- | --- | --- |
| **U1 — Primary operator** | The developer/enthusiast running VisionDrop on their own Mac. Technically capable, tolerant of calibration, wants it to feel good. | Primary |
| **U2 — Accessibility user** | Someone with limited fine motor control for whom mid-air pointing plus dwell selection is a genuine alternative to a trackpad. Drives ACC-* and the dwell requirements. | Secondary |
| **U3 — Presenter** | Uses Canvas and Lens to annotate and magnify while presenting. Drives the annotate/zoom requirements and the "physical mouse still works" constraint. | Secondary |
| **U4 — Contributor** | Reads this document, the ADR and the architecture doc to make a change. Drives MNT-* and OBS-*. | Tertiary |

### 2.4 Operating environment

| | |
| --- | --- |
| OS | macOS 15.0 (Sequoia) minimum; developed and validated on macOS 26 (Tahoe) and 27 (Golden Gate) |
| Hardware | Apple silicon required (Neural Engine). Intel Macs are best-effort and unsupported — see CON-6 |
| Camera | Any `AVCaptureDevice`; built-in FaceTime camera is the reference configuration |
| Displays | One or more, mixed scale factors and mixed refresh rates |
| Distribution | Developer ID signed, notarized, hardened runtime, **not sandboxed** |

### 2.5 Design and implementation constraints

| ID | Constraint | Source |
| --- | --- | --- |
| **CON-1** | Implementation language shall be Swift 6 with strict concurrency enabled. | ADR 0001 |
| **CON-2** | The application shall have **zero third-party runtime dependencies**. Only Apple frameworks and the Swift standard library may be linked into the shipped binary. | ADR 0001 |
| **CON-3** | All AppKit and Core Animation work shall occur on the main actor; sensing and inference shall not. | AppKit threading rules |
| **CON-4** | The application shall not be sandboxed. Accessibility permission — required for event injection — is unavailable to sandboxed applications. This structurally excludes Mac App Store distribution. | macOS TCC |
| **CON-5** | The landmark contract is **two-dimensional**. No feature computation may use a depth component unless the tracker supplies calibrated metric landmarks and a test demonstrates the calibration. | ADR 0001 §1.2 |
| **CON-6** | The performance requirements in §5.1 are specified for Apple silicon only. | Vision falls back to CPU (30–40 ms) without an ANE |
| **CON-7** | The application shall make no outbound network connections of any kind, including crash and usage reporting. | PRV-1 |

### 2.6 Assumptions and dependencies

| ID | Assumption | If false |
| --- | --- | --- |
| **ASM-1** | Vision's hand pose is accurate and robust enough for pointing at typical desk distances (0.4–0.9 m) under office lighting. | ADR 0001 §7 revisit trigger 1: add MediaPipe behind `HandTracking` |
| **ASM-2** | ~~Vision hand pose inference runs at ≤ 12 ms per frame.~~ **Measured at M1: 8–21 ms, mean ~15 ms.** Carried into the budget above. | Already exceeded the original assumption; tracked by PERF-1a/b rather than by this assumption |
| **ASM-3** | The user grants Camera, Accessibility and Screen Recording permissions. | Features degrade per APP-4; the app must remain usable and explain what is missing |
| **ASM-4** | The camera sits above the screen (laptop lid), so hands rest below the display. | Active-box mapping and gain constants need re-tuning; see PLAN.md §11.2 |
| **ASM-6** | The user can attach a 60 fps camera if PERF-1a matters to them. | Only PERF-1b applies; forward prediction becomes required rather than optional |
| **ASM-5** | `VNHumanHandPoseObservation.chirality` is **not** reliable and shall not be depended on. | Documented as an observed defect; handedness is derived geometrically per SEN-6 |

### 2.7 Coordinate systems

Three coordinate systems are in play, with three different origins. Confusing them is the single
most likely source of defects in the overlay and pointer layers, so the conversion contract is
specified here as a requirement rather than left to the implementation.

| Space | Origin | Y direction | Units | Produced by |
| --- | --- | --- | --- | --- |
| **Vision normalized** | bottom-left of the image | up | 0…1 | `VNRecognizedPoint.location` |
| **AppKit global** | bottom-left of the *primary* screen | up | points | `NSScreen.frame`, window frames |
| **CoreGraphics global** | top-left of the *primary* display | down | pixels | `CGEvent` locations, `CGDisplayBounds` |

**COORD-1 (M, T).** All conversions between these spaces shall be performed by a single module
with no other responsibility, and shall be covered by tests including: multi-display layouts,
displays positioned above and to the left of the primary (negative coordinates), and mixed
backing scale factors.

**COORD-2 (M, T).** The mirroring applied for a user-facing camera shall be applied exactly once,
at the sensing boundary, and shall be recorded in the session metadata.

---

## 3. Functional requirements

### 3.1 Sensing — `SEN`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **SEN-1** | The system shall acquire frames from an `AVCaptureDevice` at a requested 60 fps, falling back to the highest rate the device supports, and shall select the capture format explicitly rather than by session preset. | M | D |
| **SEN-2** | The system shall never display the camera image outside of an explicitly enabled debug view. | M | I |
| **SEN-3** | The system shall detect up to two hands per frame and return, for each, 21 landmarks in Vision normalized coordinates with a per-landmark confidence. | M | T |
| **SEN-4** | The system shall process only the most recent frame, dropping any frame that arrives while the previous one is still being processed, and shall report the drop rate. | M | T |
| **SEN-5** | Every frame shall carry a monotonic capture timestamp taken at the sensing boundary; all downstream time arithmetic shall use it rather than wall-clock time. | M | T |
| **SEN-6** | Handedness shall be derived from landmark geometry, not from `chirality`. | M | T |
| **SEN-7** | Landmarks whose confidence is below a configurable threshold (default 0.5) shall be reported as missing rather than as coordinates. | M | T |
| **SEN-8** | Hand tracking shall be accessed through a protocol that permits an alternative tracker to be substituted without changes to the engine. | M | I |
| **SEN-9** | When the camera is disconnected or becomes unavailable, the system shall enter a visible degraded state and recover automatically when it returns. | S | D |
| **SEN-10** | The camera device shall be user-selectable when more than one is present. | S | D |

*Rationale for SEN-4:* a queue would trade latency for throughput. In an interactive pointer,
stale frames are worse than dropped ones.

### 3.2 Interaction engine — `ENG`

The engine is pure logic: landmarks and a timestamp in, gesture and pointer state out. It has no
knowledge of AppKit, Vision or the camera, which is what makes the replay tests possible.

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **ENG-1** | All spatial thresholds shall be expressed as multiples of hand scale, never in pixels or normalized image units. | M | I |
| **ENG-2** | Feature computation shall use two-dimensional landmark coordinates only (CON-5), and this shall be enforced by the landmark type rather than by convention. | M | T |
| **ENG-3** | Aspect-ratio correction shall be applied to all coordinates of a landmark consistently, or to none. | M | T |
| **ENG-4** | Pinch detection shall use two thresholds (hysteresis), an N-frame confirmation and a release cooldown, all configurable. | M | T |
| **ENG-5** | The pinch machine shall distinguish press, click, double-click, drag-start and drag-end, and shall not emit a click when a drag occurred. | M | T |
| **ENG-6** | Loss of the hand shall reset every gesture machine to a neutral state within one frame, leaving no latched or stuck state. | M | T |
| **ENG-7** | The engine shall be deterministic: replaying an identical landmark sequence shall produce an identical event sequence. | M | T |
| **ENG-8** | The v1 gesture vocabulary shall be: point (move), thumb–index pinch (click/drag), thumb–middle pinch (right click), double pinch (double click), open palm held (idle), two hands apart/together (zoom), two hands translating (pan), index+middle horizontal swipe (page navigation). | M | T |
| **ENG-9** | The engine shall expose a continuous pinch closure value in 0…1 for feedback rendering, not only the discrete state. | M | T |
| **ENG-10** | Cursor position shall be smoothed with a One Euro filter whose parameters are configurable per mode. | M | T |
| **ENG-11** | An idle pose (open, relaxed palm held below a velocity threshold) shall suppress all gesture events until an explicit engage. | M | T |
| **ENG-12** | Dwell selection shall be available as a configurable alternative to pinch, with a configurable dwell time and a visible progress indicator. | S | T |
| **ENG-13** | A precise mode (reduced control-display gain) shall be reachable by gesture for fine targeting. | C | D |

*Rationale for ENG-2 and ENG-3:* these close the defect documented in ADR 0001 §1.2, where a
depth term that no test exercised could move a firmly-closed pinch across both thresholds.

### 3.3 Pointer — `PTR`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **PTR-1** | The active box (the region of the frame mapped to the screen) shall be configurable and default to the centre of the frame, so the user need not reach the frame edges. | M | T |
| **PTR-2** | Control-display gain shall be configurable and applied about the centre of the active box. | M | T |
| **PTR-3** | The pointer shall be clamped to the union of all display bounds and shall never be placed in a gap between non-adjacent displays. | M | T |
| **PTR-4** | On a click, the pointer shall freeze for a configurable interval so the selection lands where the user aimed. | M | T |
| **PTR-5** | On a drag start, the freeze shall be released immediately. | M | T |
| **PTR-6** | The pointer shall support clutching: disengaging, repositioning the hand, and re-engaging shall not move the pointer. | M | T |
| **PTR-7** | The pointer shall traverse display boundaries continuously in a multi-display layout. | M | T |
| **PTR-8** | An area cursor with a configurable radius shall be used for target acquisition, snapping to an accessibility element when one is available under the cursor. | S | D |

### 3.4 Overlay — `OVL`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **OVL-1** | The overlay shall be click-through: it shall never receive or consume mouse, scroll or gesture events, and the physical mouse shall behave exactly as if the overlay were absent. | M | D |
| **OVL-2** | The overlay shall never become the key or main window and shall never steal keyboard focus from the application beneath it. | M | D |
| **OVL-3** | One overlay window shall exist per `NSScreen`, and the set shall update when displays are connected, disconnected or rearranged. | M | D |
| **OVL-4** | The overlay shall be visible on all Spaces and above full-screen applications, without following Space switches as a separate window. | M | D |
| **OVL-5** | The overlay shall render at the display refresh rate, driven by a display link, with no busy-wait or timer polling. | M | A |
| **OVL-6** | Overlay geometry shall be correct at every backing scale factor, verified by golden tests over a matrix of scale factors and display arrangements. | M | T |
| **OVL-7** | The cursor shall render as an outer ring and inner dot, with the ring radius driven continuously by the pinch closure value from ENG-9. | M | D |
| **OVL-8** | Each of the following shall have a distinct, immediately legible visual state: idle, engaged, hovering a target, pressed, dragging, click fired, and blocked by an interlock. | M | D |
| **OVL-9** | A corner HUD shall show current mode, frame rate, measured latency and interlock status, and shall be dismissible. | S | D |
| **OVL-10** | The skeleton and debug visualisations shall be off by default and shall be enabled only from the settings UI. | M | I |
| **OVL-11** | The overlay shall be excluded from screen capture when Lens mode captures the screen, so it does not recursively capture itself. | M | D |
| **OVL-12** | The overlay shall honour the system Reduce Motion and Increase Contrast accessibility settings. | S | I |

### 3.5 OS actions — `ACT`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **ACT-1** | Pointer movement shall be delivered as posted mouse-moved events, not by warping the cursor, so that hover tracking works and hardware input is not suppressed. | M | T |
| **ACT-2** | If cursor warping is used anywhere, the local-events suppression interval shall be set to zero and the mouse re-associated immediately afterwards. | M | I |
| **ACT-3** | The system shall inject left click, right click, double click, press-drag-release, and scroll. | M | D |
| **ACT-4** | The system shall inject the copy, paste, cut and undo shortcuts, and back/forward page navigation. | S | D |
| **ACT-5** | Every injected event shall be tagged with a user data field identifying VisionDrop as the source, so the application can recognise and ignore its own events. | M | T |
| **ACT-6** | Accessibility hit-testing shall run off the interaction path, with a timeout, and its result shall be treated as a hint that may be absent. | M | T |
| **ACT-7** | A single accessibility query shall never block frame delivery, pointer updates or overlay rendering. | M | A |
| **ACT-8** | When Accessibility permission is absent, all injection shall be disabled and the overlay shall say so rather than failing silently. | M | D |

*Rationale for ACT-1 and ACT-2:* `CGWarpMouseCursorPosition` suppresses hardware mouse events for
0.25 s by default and produces spurious deltas — directly contradicting OVL-1's guarantee that the
physical mouse keeps working.

*Rationale for ACT-6 and ACT-7:* `AXUIElementCopyElementAtPosition` has been measured taking up to
half a second against some applications. It is a hint, not a dependency.

### 3.6 Safety interlocks — `SAF`

VisionDrop synthesises clicks and keystrokes into whatever application has focus. An unintended
click can delete a file, send a message or confirm a dialog. These requirements are not
negotiable and are not subject to simplification.

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **SAF-1** | A global kill switch shall immediately and unconditionally stop all event injection, shall be reachable from the keyboard at any time, and shall not depend on hand tracking working. | M | D |
| **SAF-2** | While macOS secure input is active, keystroke injection shall be suppressed and the state shall be shown in the overlay. | M | T |
| **SAF-3** | Event injection shall be suppressed whenever the engine is in the idle state (ENG-11). | M | T |
| **SAF-4** | Event injection shall be suppressed for a configurable interval after tracking is regained following a loss, to prevent a re-acquisition transient from firing an event. | M | T |
| **SAF-5** | Injection shall be rate-limited, with a configurable maximum click rate, and rate-limit hits shall be counted and shown in the HUD. | M | T |
| **SAF-6** | Injection shall be suppressed while any modal system alert or authentication prompt owns the input. | M | D |
| **SAF-7** | On entering any degraded state — camera lost, permission revoked, inference failing — the system shall fail closed: suppress injection, keep the overlay showing why. | M | T |
| **SAF-8** | All interlocks shall be evaluated in one place, and injection shall be reachable only through it. There shall be no code path that injects an event without consulting the interlock. | M | I |
| **SAF-9** | Every interlock activation shall be visible in the overlay within one frame; no interlock may suppress input silently. | M | D |
| **SAF-10** | First launch shall start with injection disabled; the user shall explicitly enable it after completing onboarding. | M | D |

### 3.7 Modes — `MOD`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **MOD-1** | The system shall provide three modes — Pointer, Canvas, Lens — with exactly one active at a time. | M | D |
| **MOD-2** | Mode shall be switchable by global hotkey and from the menu bar. | M | D |
| **MOD-3** | The current mode shall be unambiguous from the overlay alone, without opening a menu. | M | D |
| **MOD-4** | Each mode shall carry its own filter and gesture configuration. | S | T |

### 3.8 Canvas mode — `CNV`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **CNV-1** | The user shall draw strokes on a transparent layer over the desktop using a pinch-and-move gesture. | M | D |
| **CNV-2** | Colour, stroke width and eraser shall be selectable without leaving the mode. | M | D |
| **CNV-3** | Undo and redo shall be available, with a bounded history depth. | M | T |
| **CNV-4** | Strokes shall be simplified before storage while remaining visually faithful. | S | T |
| **CNV-5** | Closed strokes shall be optionally recognised and beautified into line, rectangle, ellipse, triangle or arrow, with a visible way to reject the substitution. | S | T |
| **CNV-6** | The annotation layer shall be exportable as PNG and as SVG. | S | D |
| **CNV-7** | Annotations shall survive a mode switch and be explicitly clearable. | S | D |
| **CNV-8** | Text and sticky-note insertion. | C | D |

### 3.9 Lens mode — `LNS`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **LNS-1** | The user shall magnify a screen region, with the magnification factor controlled by a two-hand gesture. | M | D |
| **LNS-2** | The magnified region shall be pannable by a two-hand translation gesture. | M | D |
| **LNS-3** | Screen capture shall use ScreenCaptureKit, shall exclude VisionDrop's own overlay windows, and shall release frame buffers promptly. | M | I |
| **LNS-4** | Text within the captured region shall be recognised and made available as pinch targets. | S | D |
| **LNS-5** | Pinching a recognised word shall select it in the underlying application where the accessibility tree permits, and shall otherwise copy it. | C | D |
| **LNS-6** | When Screen Recording permission is absent, Lens mode shall be unavailable and shall say why, rather than showing an empty view. | M | D |

### 3.10 Configuration — `CFG`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **CFG-1** | Every threshold, timing and gain referenced in this document shall be configurable; none shall be a literal in the source. | M | I |
| **CFG-2** | Configuration shall be stored as a single human-readable file in Application Support, and shall be editable outside the application. | M | I |
| **CFG-3** | An invalid or corrupt configuration shall fall back to defaults with a visible warning, and shall never prevent launch. | M | T |
| **CFG-4** | Configuration changes shall take effect without restarting the application. | S | D |
| **CFG-5** | A settings UI shall expose the commonly tuned values with live preview; the full set remains available in the file. | S | D |
| **CFG-6** | Per-application gesture profiles. | W | — |

### 3.11 Recording and telemetry — `REC`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **REC-1** | The system shall record landmark streams to a documented JSONL format including timestamps, confidences, handedness, mirroring and tracker identity. | M | T |
| **REC-2** | The system shall replay a recording through the engine and produce an identical event sequence on every run (ENG-7). | M | T |
| **REC-3** | Recording shall optionally include the source video, so that two trackers can be compared on identical input. | M | D |
| **REC-4** | Recording shall never start implicitly. It requires an explicit user action each session, and the overlay shall show a persistent indicator while active. | M | D |
| **REC-5** | The system shall measure frame rate, per-stage latency and dropped-frame rate continuously and expose them to the HUD. | M | T |
| **REC-6** | Latency measurement shall use signposts so the pipeline can be profiled in Instruments without a custom harness. | M | I |
| **REC-7** | A headless command-line tool shall replay a recording and print the resulting event sequence and metrics, for use in CI. | M | T |

### 3.12 Application — `APP`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **APP-1** | The application shall run as a menu-bar item with no Dock icon and no main window. | M | D |
| **APP-2** | The menu shall show tracking state, active mode, interlock status, and a visible master enable/disable. | M | D |
| **APP-3** | First launch shall present onboarding that explains each permission, why it is needed, and deep-links to the relevant System Settings pane. | M | D |
| **APP-4** | The application shall start and remain usable with any subset of permissions granted, disabling only the dependent features and stating which are disabled. | M | D |
| **APP-5** | Permission state shall be re-checked when the application becomes active, so a grant made in System Settings takes effect without a restart. | M | D |
| **APP-6** | The application shall be signed with a Developer ID certificate, notarized and stapled, with the hardened runtime enabled. | M | I |
| **APP-7** | The application shall shut down cleanly: camera released, overlay windows torn down, no injected event left in a pressed state. | M | T |
| **APP-8** | A crash or unhandled error shall not leave a mouse button or modifier key stuck down. | M | T |
| **APP-9** | Launch at login shall be available and off by default. | C | D |

---

## 4. External interface requirements

### 4.1 User interfaces

| Surface | Description |
| --- | --- |
| Menu bar item | Primary control: state, mode, master switch, settings, quit |
| Overlay | The main interaction surface: cursor, feedback, HUD, annotations |
| Settings window | Standard AppKit/SwiftUI settings; keyboard navigable, VoiceOver labelled |
| Onboarding | First-run permission walkthrough with per-permission status and deep links |
| CLI | Headless `replay`, `bench` and `info` subcommands for CI and tuning |

### 4.2 Hardware interfaces

| Device | Interface | Notes |
| --- | --- | --- |
| Camera | `AVCaptureDevice` | 60 fps requested, degrades gracefully; no preview rendered |
| Displays | `NSScreen`, `CGDirectDisplayID` | Hot-plug and rearrangement handled at runtime |
| Keyboard | Global hotkey registration | Kill switch and mode switching only |
| Neural Engine | via Vision | Not addressed directly; fallback is automatic and must be detected and reported |

### 4.3 Software interfaces

| Framework | Used for | Permission required |
| --- | --- | --- |
| AVFoundation | Camera capture | **Camera** (TCC) |
| Vision | Hand pose, text recognition | — |
| AppKit / Core Animation | Overlay, menu bar, settings | — |
| CoreGraphics | Event injection, display geometry | **Accessibility** |
| ApplicationServices (AX) | Element hit-testing | **Accessibility** |
| ScreenCaptureKit | Lens capture | **Screen Recording** |
| Carbon (secure input query) | SAF-2 interlock | — |
| OSLog | Logging, signposts | — |

**Permission degradation matrix:**

| Granted | Available |
| --- | --- |
| None | Menu bar, settings, onboarding only |
| Camera | Tracking, overlay feedback, recording. **No injection.** |
| Camera + Accessibility | Full Pointer mode, Canvas mode |
| Camera + Accessibility + Screen Recording | All modes including Lens |

### 4.4 Communications interfaces

**None.** The application performs no network I/O. See PRV-1 and CON-7.

---

## 5. Non-functional requirements

### 5.1 Performance — `PERF`

**Latency budget.** Motion-to-photon, Apple silicon. Measured figures are from
M1 on an M-series MacBook Pro with the built-in FaceTime HD camera, 1280×720.

| Stage | Budgeted | Measured | Basis |
| --- | --- | --- | --- |
| Camera exposure and delivery | 16–22 ms | **~33 ms** | The built-in camera offers **no 60 fps mode at any resolution** — every format it publishes is 30 fps. One frame at 30 Hz is 33 ms. |
| Vision hand pose | 8–12 ms | **8–21 ms**, mean ~15 ms | Measured per-frame over a live session. |
| Features + filter + state machines | < 1 ms | **10–17 µs** | ~60× inside budget. |
| Overlay composite and present | 8–16 ms | not yet built | one display frame |
| Event injection | < 1 ms | not yet built | `CGEventPost` |
| **Total** | 33–51 ms | **~57–71 ms projected** | |

**The 60 ms target is not reachable with the built-in camera.** Its 30 fps
ceiling costs 17 ms over the assumed 60 fps delivery, which alone consumes the
margin. PERF-1 is therefore split by hardware, and forward prediction is
recorded as the mitigation for the 30 fps case (PLAN.md §3.2 lists it as a
stretch over the 1€ filter; this measurement promotes it).

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **PERF-1a** | With a camera delivering 60 fps or better, motion-to-photon latency shall be below 60 ms at the 95th percentile. | M | A |
| **PERF-1b** | With a 30 fps camera, motion-to-photon latency shall be below 75 ms at the 95th percentile. | M | A |
| **PERF-1c** | The system shall report the camera's actual frame rate and which of the two targets applies. | M | T |
| **PERF-2** | The overlay shall sustain the display refresh rate with no dropped frames at the 99th percentile during a 60-second pointing session. | M | A |
| **PERF-3** | Pointer jitter shall be below 1 mm mean-to-peak with the hand held stationary. | M | A |
| **PERF-4** | The engine shall process a frame in under 1 ms at the 99th percentile, excluding inference. | M | T |
| **PERF-5** | Idle CPU usage, with tracking enabled and no hand present, shall be below 15% of one core. | S | A |
| **PERF-6** | Memory shall be stable over an eight-hour session, with no unbounded growth in recordings, stroke history or telemetry buffers. | M | A |
| **PERF-7** | Time from launch to first tracked frame shall be under 3 seconds. | S | A |
| **PERF-8** | Dropped camera frames shall be below 5% during normal operation, and the rate shall be reported. | M | A |

PERF-1a and PERF-3 are the numeric targets from the 1€ filter literature (PLAN.md §3.2);
PERF-1b is that target plus the 17 ms the built-in camera's 30 fps ceiling costs.

### 5.2 Reliability — `REL`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **REL-1** | The application shall run for eight hours without crash, leak or degradation of latency. | M | A |
| **REL-2** | Camera loss, permission revocation and display reconfiguration shall each be recovered from without restart. | M | D |
| **REL-3** | No failure mode shall leave a synthetic mouse button or modifier key held down. | M | T |
| **REL-4** | Every error path shall have a defined user-visible outcome; no error shall be silently swallowed. | M | I |

### 5.3 Privacy — `PRV`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **PRV-1** | The application shall make no network connections. Verified by inspection of the linked frameworks and by observing the process under a network monitor during an acceptance run. | M | I+A |
| **PRV-2** | Camera frames shall never be written to disk except during an explicitly started recording (REC-4). | M | I |
| **PRV-3** | Recordings shall be stored only in a documented, user-visible location, and shall be listable and deletable from the settings UI. | M | D |
| **PRV-4** | Screen content captured in Lens mode shall exist only in memory for the lifetime of the frame and shall never be persisted. | M | I |
| **PRV-5** | Logs shall contain no screen content and no recognised text. | M | I |
| **PRV-6** | The overlay shall display a persistent, unmistakable indicator whenever recording is active. | M | D |

### 5.4 Security — `SEC`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **SEC-1** | The hardened runtime shall be enabled, with only the entitlements actually required and each one justified in a comment. | M | I |
| **SEC-2** | The application shall not require nor request administrator privileges. | M | I |
| **SEC-3** | The configuration file shall be parsed defensively; no input from it shall be able to crash the application or disable a safety interlock. | M | T |
| **SEC-4** | Recording files shall be parsed defensively; a malformed recording shall produce an error, not a crash. | M | T |
| **SEC-5** | No code path shall be able to disable a SAF-* interlock through configuration. Interlocks are tunable in threshold, never in existence. | M | I |

### 5.5 Accessibility — `ACC`

VisionDrop is partly an assistive tool (user class U2); its own interfaces must not be inaccessible.

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **ACC-1** | Settings and onboarding shall be fully keyboard navigable and correctly labelled for VoiceOver. | M | D |
| **ACC-2** | No state shall be conveyed by colour alone; every overlay state shall differ in shape or motion as well. | M | I |
| **ACC-3** | Reduce Motion shall suppress overlay animations without removing the information they convey. | S | D |
| **ACC-4** | Dwell selection (ENG-12) shall be sufficient on its own to operate Pointer mode, with no pinch required. | S | D |
| **ACC-5** | Overlay contrast shall meet WCAG AA against both light and dark desktop backgrounds. | S | A |

### 5.6 Usability — `USE`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **USE-1** | A first-time user shall complete onboarding and acquire a target within five minutes without documentation. | M | D |
| **USE-2** | Unintended clicks shall occur fewer than once per minute of active use. | M | A |
| **USE-3** | System Usability Scale score shall be 70 or above across 8–12 participants. | S | A |
| **USE-4** | Fitts' law throughput shall be at least 2.5 bits/s. | S | A |
| **USE-5** | Every visual state in OVL-8 shall be distinguishable by a user who has not read the documentation. | M | D |

USE-2 through USE-4 follow the evaluation protocol in PLAN.md §9.

### 5.7 Maintainability — `MNT`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **MNT-1** | The interaction engine shall compile and its tests shall run with no camera, no display and no permissions. | M | T |
| **MNT-2** | Line coverage of the engine module shall be at least 85%. | M | A |
| **MNT-3** | Every gesture requirement in §3.2 shall have at least one replay test over a recorded or synthetic stream. | M | T |
| **MNT-4** | Every safety requirement in §3.6 shall have at least one test that asserts injection does **not** occur. | M | T |
| **MNT-5** | The build shall be warning-free with strict concurrency enabled. | M | I |
| **MNT-6** | Formatting and linting shall be enforced in CI, not by convention. | M | I |
| **MNT-7** | Every public type, and every method whose contract is not evident from its signature, shall carry a documentation comment stating units, coordinate space and boundary behaviour. Comments that exist shall be verified against the code they document, enforced by `ValidateDocumentationComments` in CI. | M | I |
| **MNT-8** | Test fixtures shall include non-zero values for every field the production path can populate. | M | I |
*Rationale for MNT-8:* the defect in ADR 0001 §1.2 survived the original prototype tests solely because every fixture
set the depth component to zero. A fixture that cannot express a value cannot test it.

### 5.8 Observability — `OBS`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **OBS-1** | Logging shall use the unified logging system with per-subsystem categories and appropriate privacy annotations. | M | I |
| **OBS-2** | Each pipeline stage shall emit signposts so end-to-end latency is attributable in Instruments. | M | I |
| **OBS-3** | The HUD shall show frame rate, latency, drop rate, tracking state and active interlocks. | M | D |
| **OBS-4** | A diagnostic report — versions, permission state, device, recent metrics — shall be exportable in one action, and shall contain no screen content or recognised text. | S | D |

### 5.9 Portability — `PRT`

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **PRT-1** | The engine module shall depend on no platform framework, so it remains portable if ADR 0001 is revisited. | M | I |
| **PRT-2** | The recording format shall be platform- and tracker-independent. | M | I |
| **PRT-3** | Non-Apple platform support. | W | — |

---

## 6. Data requirements

### 6.1 Session recording

One JSON object per line. A header line establishes the session; frame lines follow.

```jsonc
// header (first line)
{ "type": "header", "version": 2, "tracker": "vision.handpose.r1",
  "camera": { "id": "…", "width": 1280, "height": 720, "fps": 60, "mirrored": true },
  "displays": [ { "id": 1, "bounds": [0,0,1920,1080], "scale": 2.0, "primary": true } ],
  "started": "2026-09-22T17:04:11Z", "video": "session-0001.mov" }

// frame line
{ "type": "frame", "t": 12.3456,
  "hands": [ { "handedness": "right", "score": 0.94,
               "points": [ [0.51,0.62,0.98], … ] } ] }   // [x, y, confidence] — 21 entries
```

| ID | Requirement | Pri | Ver |
| --- | --- | :---: | :---: |
| **DAT-1** | Each landmark shall be `[x, y, confidence]` in Vision normalized coordinates. There shall be no depth component (CON-5). | M | I |
| **DAT-2** | The header shall record tracker identity and version, so a recording made with one tracker is never silently replayed as another. | M | T |
| **DAT-3** | The format shall be versioned, and a reader shall reject an unknown version explicitly. | M | T |
| **DAT-4** | Video, when recorded, shall be referenced by relative path beside the JSONL. | M | I |
| **DAT-5** | A missing landmark shall be represented distinctly from a low-confidence one. | M | T |

### 6.2 Configuration

Stored at `~/Library/Application Support/VisionDrop/config.json`. Hand-editable; every key
optional; unknown keys preserved on rewrite so a newer config survives an older build.

### 6.3 Storage locations

| Data | Location | Retention |
| --- | --- | --- |
| Configuration | `~/Library/Application Support/VisionDrop/config.json` | Until deleted |
| Recordings | `~/Library/Application Support/VisionDrop/Recordings/` | User-managed, listable and deletable in settings |
| Logs | Unified logging | System-managed |
| Annotations | In memory until explicitly exported | Cleared on quit |

---

## 7. Verification and validation

### 7.1 Intended test levels

| Intended level | Scope | Intended runs |
| --- | --- | --- |
| **Unit** | Features, filters, implemented state machines, coordinate conversion | Every commit, headless |
| **Golden** | Overlay geometry across scale factors and display layouts | Every commit, headless |
| **Replay** | Labelled recorded and synthetic streams → expected event sequences | Every commit, headless |
| **Integration** | Camera → Vision → engine on a canned video file | Every commit, headless |
| **Manual scripted** | Permission flows, click-through, multi-display, kill switch | Every release |
| **Evaluation study** | USE-2 … USE-5, per PLAN.md §9 | Before 2.0 |

These are target verification levels, not a description of the present suite. Today the Swift tests
cover core logic plus recording round-trips/errors, and Vision tests cover joint mapping and handedness.
CI additionally replays one committed synthetic v2 file through the CLI. Overlay golden tests,
canned-video integration, a labelled real evaluation corpus, the manual release checklist, and the
evaluation study do not yet exist.

### 7.2 Present regression gate and planned gate

Current CI replays the committed synthetic fixture and asserts its press/click/no-drag sequence. It does
not yet maintain a real evaluation baseline or calculate pinch F1, false-click rate, or engine p99.

The intended 2.0 regression gate will block a merge if any of those metrics regresses against a
committed labelled evaluation set, or if any replay fixture's expected event sequence changes without
an intentional update.

### 7.3 Acceptance criteria for 2.0

All of the following are release gates, not achieved results: every `M` requirement verified; pinch
F1 ≥ 0.95; motion-to-photon p95 below 60 ms at 60 fps or 75 ms at 30 fps; pointer jitter below 1 mm
mean-to-peak; fewer than one unintended click per minute; at least 90% scripted-workflow success; at
least 85% `VisionDropCore` line coverage; and zero stuck-input incidents. The coverage floor is enforced
in current CI, but the other criteria require evaluation or product work that is not yet present.

### 7.4 Test data

The current committed fixture is synthetic and covers a point-to-pinch-to-release click sequence. The
required real corpus must cover varying camera distance, hand size, rotation, lighting, one and two
hands, fast motion, tracking loss/recovery, and a resting hand that emits no events. Each recording
must be labelled with its expected event sequence, and fixtures must populate every field the
production path can carry (MNT-8). This corpus has not been created.

Python prototype recordings are v1 and have no v2 header; their landmark arrays contain `[x, y, z]`
rather than `[x, y, confidence]`. The Swift reader deliberately rejects v1. Converting one requires an
explicit converter that discards the contaminated depth term, adds a v2 header/confidence contract, and
validates handedness and coordinates; no converter is implemented. New or converted corpus files must
satisfy the v2 schema rather than being silently reinterpreted.

---

## 8. Release plan

The following is a target release plan, not an achievement ledger. No milestone is currently accepted:
the package, CI, and menu-bar shell with live tracking controls are present, and M1/M2 have partial
Swift implementations, but signing/notarization, the real evaluation criteria, and M3–M7 remain
incomplete.

| # | Milestone | Contents | Exit criterion |
| --- | --- | --- | --- |
| **M0** | Skeleton | SPM layout, app target, CI, signing, notarization, menu bar, onboarding, permission matrix | A signed, notarized, empty menu-bar app installs and requests permissions correctly |
| **M1** | Sensing | AVFoundation capture, Vision tracker, protocol boundary, recorder with video, CLI replay | Records a session and replays it deterministically; drop rate and latency reported |
| **M2** | Engine | Features, filters, state machines, pointer mapping, coordinate module — ported with CON-5 enforced | Pinch F1 ≥ 0.95 on the evaluation set; engine p99 < 1 ms; MNT-1 holds |
| **M3** | Overlay | Per-display click-through panels, display-link rendering, cursor and state visuals, HUD | OVL-1 … OVL-8 demonstrated on a two-display mixed-scale setup; golden tests pass |
| **M4** | Control | Event injection, the full interlock set, accessibility hit-testing | Scripted workflow ≥ 90%; every SAF-* test asserts non-injection; zero stuck inputs |
| **M5** | Canvas | Strokes, tools, undo/redo, shape recognition, export | A labelled diagram drawn and exported; shape recognition ≥ 90% on five base shapes |
| **M6** | Lens | ScreenCaptureKit magnifier, two-hand zoom and pan, OCR targets | A PDF page magnified and read; a recognised word pinched |
| **M7** | Evaluation | Study, tuning, documentation, packaging | §7.3 acceptance criteria met |

The Swift engine supersedes the Python implementation for the 2.0 direction, but the planned
cross-language fixture validation is incomplete. Prototype v1 recordings require explicit v2
conversion; the Swift reader rejects them. `tools/lab/` remains until the agreed Swift fixture
validation and deletion milestone are complete (ADR 0001 §5.4).

---

## 9. Risks

| ID | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| R1 | Vision hand pose is less robust than MediaPipe in real conditions | Medium | High | `HandTracking` protocol plus video recordings make an A/B comparison cheap; ADR 0001 §7 trigger 1 |
| R2 | Inference falls back off the ANE and blows the latency budget | Low | High | Detect and report the compute unit; PERF-1a/b measured continuously; reduce resolution before dropping features |
| R11 | The camera's frame rate, not our code, is the dominant latency term | **Confirmed at M1** | High | Explicit format selection (SEN-1); split targets (PERF-1a/b); forward prediction for the 30 fps case |
| R3 | An unintended click causes real damage | Medium | **Severe** | The entire SAF-* set; fail-closed default; injection off until explicitly enabled |
| R4 | Accessibility hit-testing stalls the pipeline | Medium | Medium | ACT-6 and ACT-7: off the interaction path, timed out, treated as a hint |
| R5 | Overlay click-through regresses on a macOS update | Medium | High | OVL-1 is in the manual release checklist; it cannot be covered by a headless test |
| R6 | Gorilla arm makes extended use unpleasant | High | Medium | Clutching (PTR-6), gain (PTR-2), idle (ENG-11), dwell (ENG-12); measured in the study |
| R7 | The Swift port stalls half-finished, leaving two engines | Medium | Medium | ADR 0001 §5.4 gives `tools/lab/` one job and a deletion milestone |
| R8 | Notarization or TCC friction discovered late | Low | High | M0 ships a signed notarized shell **before** any feature work |
| R9 | Coordinate-space confusion produces subtle multi-display defects | High | Medium | COORD-1 and COORD-2: one module, golden tests over a layout matrix |
| R10 | Scope creep across Canvas and Lens | Medium | Medium | Milestones independently shippable; `W` priorities recorded to bound scope |

---

## 10. Open questions

| # | Question | Needed by | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Is a two-display, mixed-scale setup available for development, or only the laptop display? | M3 | Assume single display; golden tests cover the rest synthetically |
| Q2 | Should the legacy Python demos and `requirements.txt` be deleted once Swift lands, or kept as an archive? | M2 | Keep in `legacy/`, unmaintained, excluded from CI |
| Q3 | Is the evaluation study (USE-3, USE-4) actually going to be run, or are those aspirational? | M7 | Treat as `S`; ship on USE-1, USE-2, USE-5 alone |
| Q4 | Is an external webcam at eye level available, or is the laptop lid camera the only configuration? | M2 | Tune for the lid camera (ASM-4) |
| Q5 | Should the kill switch be a hotkey, a corner abort gesture, or both? | M4 | Both: hotkey is mandatory (SAF-1), corner abort is additive |

---

## 11. Traceability

### 11.1 Feature to requirements

| Product function | Requirements |
| --- | --- |
| F1 Track hands, no preview | SEN-1 … SEN-10, COORD-2 |
| F2 Screen-space pointer | ENG-10, PTR-1 … PTR-8, COORD-1 |
| F3 Gesture vocabulary | ENG-1 … ENG-13 |
| F4 Visual feedback | OVL-1 … OVL-12, SAF-9 |
| F5 Drive the OS | ACT-1 … ACT-8 |
| F6 Suppress unsafe input | SAF-1 … SAF-10, REL-3 |
| F7 Canvas | CNV-1 … CNV-8, MOD-1 … MOD-4 |
| F8 Lens | LNS-1 … LNS-6 |
| F9 Record and replay | REC-1 … REC-7, DAT-1 … DAT-5 |
| F10 Configuration | CFG-1 … CFG-6, APP-1 … APP-9 |

### 11.2 Requirements addressing known defects

| Defect | Requirements |
| --- | --- |
| Depth term contaminating the pinch ratio (ADR 0001 §1.2) | CON-5, ENG-2, ENG-3, DAT-1 |
| Tests that cannot express the failing value | MNT-8, §7.4 |
| Fixed-pixel thresholds failing with camera distance (PLAN.md §2) | ENG-1 |
| State chatter around a single threshold (PLAN.md §2) | ENG-4 |
| Stale state after a transition (PLAN.md §2) | ENG-6, SAF-4 |
| No visual feedback (PLAN.md §2) | OVL-7, OVL-8, ENG-9, SAF-9 |

### 11.3 Requirements traceable to a researched platform hazard

| Hazard | Requirements |
| --- | --- |
| Cursor warp suppresses hardware input for 0.25 s | ACT-1, ACT-2 |
| Accessibility hit-test can block for ~500 ms | ACT-6, ACT-7 |
| `chirality` frequently reports the wrong hand | SEN-6, ASM-5 |
| Secure input blocks synthetic keystrokes | SAF-2 |
| Accessibility permission is unavailable to sandboxed apps | CON-4, APP-6 |
| Vision normalized coordinates are bottom-left origin; CGEvent is top-left | COORD-1, §2.7 |
| ScreenCaptureKit back-pressures if buffers are held | LNS-3 |
| Vision falls back from the ANE when it is busy | ASM-2, R2, OBS-3 |
| A session preset selects a 16 fps format on the built-in camera | SEN-1 |
| The built-in camera has no 60 fps mode at any resolution | PERF-1a, PERF-1b, PERF-1c, ASM-6, R11 |
| The first Vision request loads and compiles the model, costing seconds | PERF-7 |
