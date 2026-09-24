# VisionDrop 2.0 — Research & Implementation Plan

> **Status (2026-09-24): mixed research record and superseded proposal.** Sections 1–4, 9,
> and 12 retain the product goal, root-cause analysis, research synthesis, evaluation design, and
> design principles. Sections 5–8, 11, and 13 describe the original Python/PyObjC implementation
> proposal and roadmap and are superseded by [docs/SRS.md](docs/SRS.md),
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and
> [ADR 0001](docs/adr/0001-implementation-language.md). They are not a record of completed work.
>
> **Current progress:** the Swift package now contains geometry conversion, two-dimensional hand
> landmarks and features, One Euro filtering, pinch and idle state machines, pointer mapping,
> configuration, AVFoundation capture, Vision tracking, a landmark-only v2 recorder, deterministic
> replay, a headless CLI, and a menu-bar app shell with cancellable live camera → Vision → engine
> tracking. Core and Vision mapping tests plus a synthetic replay fixture are present. There is still no
> click-through overlay, event injection, Canvas, Lens, real evaluation corpus, or demonstrated M0–M7
> milestone exit criterion. The Python prototype remains under `src/visiondrop/`; the original demos
> are under `legacy/`.

---

## 1. Product goal

Turn VisionDrop from a camera-preview demo into an **ambient, screen-space interaction layer**:

- The camera is a **sensor only** — no webcam window.
- Hand tracking drives a **cursor and gestures on top of the real desktop**, drawn by a transparent,
  click-through overlay.
- The overlay supports **navigation, selection, copy/edit, drawing, annotation, zoom/pan/scale**, and
  **detection annotations over real UI content** (text, links, page elements).
- Feedback is **visual, immediate, and legible** — the current version's biggest weakness.

Three user-visible modes:

| Mode | Purpose |
| --- | --- |
| **Pointer** | Air mouse: move, click, drag, scroll, select, copy/paste, navigate pages. |
| **Canvas** | Draw on a transparent layer over anything, with shape recognition/beautification and annotations that persist. |
| **Lens** | Zoom / pan / magnify any region; OCR-detected words and UI elements become pinch targets. |

---

## 2. Why the current pinch is broken (root-cause analysis)

Current implementation: `drag_squares_project/drag_squares.py:68-107` (`is_pinching`),
`109-121` (`get_pinch_position`), used in `drag_squares.py:247-278`.

| # | Root cause | Consequence |
| --- | --- | --- |
| 1 | Threshold is a **fixed normalized distance** (`0.04`) between thumb tip (4) and index tip (8) | Fails with hand distance from camera and hand size. MediaPipe coords are normalized to the *image*, not the hand. |
| 2 | `index_extended = index_tip.y < index_pip.y` and same for middle | Image-space Y comparison is invalid when the hand tilts or rotates; a natural pinch often fails the extra condition, so pinches are rejected. |
| 3 | Single threshold, **no hysteresis** | State chatters around the threshold → flicker, missed clicks, accidental drags. |
| 4 | Cooldown returns `self.last_pinch_state` (`drag_squares.py:73-75`) | The FSM can return *stale* state for 5 frames after any transition, masking real transitions. |
| 5 | No hand-size normalization, no use of `world_landmarks` | Depth/size dependence; MediaPipe's metric landmarks are ignored. |
| 6 | Raw positions, no filtering | Cursor and trail jitter; dragging targets the noisy midpoint of two noisy tips. |
| 7 | Almost **no visual feedback** | User cannot tell "armed", "pinching", "click fired", "drag captured". |
| 8 | Hand lost → trail cleared, state not reset per-square | Drags can stick; no recovery semantics. |

**Fix direction (research-backed):** normalize by hand size, add hysteresis + EMA/One-Euro smoothing,
freeze the cursor at click time, and render a continuous "pinch meter" plus click/drag affordances.

---

## 3. Research synthesis

### 3.1 Tracking / pose estimation

| Work | ID | What we take |
| --- | --- | --- |
| MediaPipe Hands: On-device Real-time Hand Tracking (Zhang et al., CVPRW 2020) | arXiv:2006.10214 | The two-stage palm-detector + landmark model; 21 landmarks including 2.5D. This is the baseline. |
| MediaPipe framework (Lugaresi et al.) | arXiv:1906.08172 | Graph/calculator architecture; informs our threading pipeline. |
| BlazeFace / BlazePalm | arXiv:1907.05047 | Detector design; explains detection cadence. |
| On-device Real-time Hand Gesture Recognition (Google, 2021) | arXiv:2111.00038 | Skeleton-first + lightweight classifier split; world-metric landmarks; gesture classifier only runs when a hand is present. |
| HaMeR: Reconstructing Hands in 3D with Transformers (CVPR 2024) | arXiv:2312.05251 | Higher-fidelity 3D hand mesh; candidate for occlusion robustness later (heavy). |
| WiLoR (CVPR 2025) | arXiv:2409.12259 | Full-stack detection + 3D reconstruction, 130+ FPS detector. **License: CC-BY-NC-ND + MANO — non-commercial; treat as research-only.** |
| Visual Hand Gesture Recognition with Deep Learning (survey, 2025) | arXiv:2507.04465 | Taxonomy of static/dynamic/continuous recognition, datasets, metrics. |
| Survey on Hand Gesture Recognition from Visual Input (2025) | arXiv:2501.11992 | RGB vs depth, occlusion/generalization/real-time challenges. |

**Decision:** MediaPipe Tasks `HandLandmarker` (2D + world landmarks) as the shipping tracker. WiLoR/HaMeR
are documented as optional "high-fidelity 3D" backends behind an interface, not required.

### 3.2 Cursor, jitter, latency (the make-or-break layer)

| Work | ID | What we take |
| --- | --- | --- |
| 1€ Filter (Casiez, Roussel, Vogel, CHI 2012) | DOI 10.1145/2207676.2208639 | Adaptive low-pass: low cutoff at low speed (kills jitter), high cutoff at high speed (kills lag). Target from the paper: **jitter < 1 mm mean-to-peak, lag < 60 ms**. |
| N-euro Predictor (IMWUT 2023) | DOI 10.1145/3610884 | Neural smoothing + prediction reduces jitter and lag simultaneously; stretch goal over 1€. |
| Effects of Latency Jitter and Dropouts in Pointing Tasks | CEUR Vol-588 | Latency/dropouts degrade pointing; motivates a latency budget and telemetry. |
| Everything to Gain: Area Cursors + Control-Display Gain (CHI 2025) | DOI 10.1145/3706598.3714021 | Area cursors + gain improve touchless speed/accuracy. Directly informs our cursor design. |
| Don't Touch Me! (INTERACT 2021) | arXiv:2107.05408 | Touchless vs touch usability; expectation management, benchmark against SUS. |

### 3.3 Gesture vocabulary & selection (avoid inventing gestures)

| Work | ID | What we take |
| --- | --- | --- |
| Towards a Consensus Gesture Set: Survey of Mid-Air Gestures (CHI 2023) | DOI 10.1145/3544548.3581420 | 22-gesture consensus set; **scale = two hands apart**, cursor = index pointing, minimize = close hand. Use their agreement rates to pick our vocabulary. |
| An empirical evaluation for a mid-air gesture dictionary (2024) | arXiv:2404.05842 | People map touch/mouse gestures onto mid-air; expect legacy bias; validate with users. |
| Push or Pinch? Slider control in touchless UIs (2022) | DOI 10.1145/3546155.3546702 | Pinch is workable but not always best; continuous controls need explicit engagement. |
| Pinch, Click, or Dwell (ACM 2021) | DOI 10.1145/3448018.3457998 | Pinch vs dwell vs click: dwell = fewest errors but slow; pinch ≈ acceptable. Gives us a method to compare selection techniques. |
| GaVe: webcam gaze vending with dwell (PMC10640920) | — | Dwell-time calibration protocol (0.5/0.8/1.0/1.2 s), one-point calibration idea. Reused for our optional dwell click. |
| Exploring Mid-Air Hand Interaction in Data Visualization (2023) | arXiv:2311.15372 | Ergonomic restrictions, input resolution, translation ambiguity — design warnings. |
| Can't (Midas) touch this: clutching evaluation (2025) | DOI 10.1145/3743049.3743055 | The Midas-touch problem and clutching strategies; motivates explicit "engage/idle" states. |
| AirPen (2019) | arXiv:1904.06122 | In-air writing + command gestures; MobileNetV2 + fingertip regression + BiLSTM, 0.12 s latency. Reference for drawing UX. |

### 3.4 Drawing, shape recognition, annotation

| Work | ID / link | What we take |
| --- | --- | --- |
| $1 Unistroke Recognizer (Wobbrock, Wilson, Li, UIST 2007) | DOI 10.1145/1294211.1294238; code: `depts.washington.edu/acelab/proj/dollar/` (New BSD) | ~100-line template matcher, 97%+ with 1–3 templates. Perfect for snapping hand-drawn strokes to clean lines/circles/rectangles/arrows/triangles. |
| $P Point-Cloud Recognizer (ICMI 2012) and $Q (CHI 2018) | $ family, New BSD | Multi-stroke/quick variants for multi-stroke shapes. |
| Air Canvas family (OpenCV + MediaPipe) | e.g. `ShivamPawaskar/Air-Canvas`, `aayush23206/Air-Canvas` | Gesture-to-tool switching, alpha-blended canvas, eraser semantics. Prior art for our Canvas mode. |
| Pinterest-style "Code Shaping" (CHI 2025, free-form AI-interpreted sketching) | DOI via CHI 2025 (cited in $1 thread) | Inspiration for interpreting a sketch into a semantic object (stretch). |

### 3.5 Open-source references we should learn from / reuse

| Repo | License | Reuse |
| --- | --- | --- |
| `google-ai-edge/mediapipe` | Apache-2.0 | Tracker + Tasks API. |
| `Kazuhito00/simple-virtual-mouse-using-mediapipe` | Apache-2.0 | Minimal cursor mapping + PyAutoGUI click pattern. |
| `harrynoble/Gesture-Cursor` | verify | Modular split (detection / interpretation / OS interaction) we should copy structurally. |
| `adammcarter/annotate` | MIT | **Best macOS overlay reference**: click-through overlay per screen, Core Animation, geometry pinned by golden tests, Accessibility for UI element positions. Swift; we mirror the architecture in PyObjC. |
| `loomhq/ElectronMacOSClickThrough` | verify | Documents `NSWindow.ignoresMouseEvents` three-state pitfall. |
| `DmytroVasin/DrawPen` | MIT | Cross-platform annotation tool UX: tools, shortcuts, pointer mode, laser. |
| `opensourcebharat/lekhini` | verify | Electron overlay per display, dpi handling, click-through with event forwarding, tool profiles. |
| `CreativeInquiry/handsfree-js` | verify | "Pincher" plugin: 24+ pinch events with `start/held/released` states modeled on mouse events. Good FSM semantics to borrow. |
| `KTokos/MediaPipeGestureDetection` | verify | Pinch distance in cm via hand-scale estimate — exactly the depth-invariance idea. |
| `MahmudulAlam/Unified-Gesture-and-Fingertip-Detection` | MIT | Egocentric fingertip regression + gesture in one network; alternative to MediaPipe. |
| `pupil-labs/gaze-control` | verify | UX reference: click mode vs zoom mode, dwell progress ring, audio click. |
| `rolpotamias/WiLoR`, `geopavlakos/hamer` | CC-BY-NC-ND / verify | Optional 3D backend (research-only). |
| air-touch.ir (browser touchless mouse) | reference only | Design notes: depth-invariant normalized pinch thresholds, center-box mapping (no arm stretching), EMA smoothing, cursor freeze during click, corner-abort failsafe. |

---

## 4. Design principles (derived from the above)

1. **Never invent gestures blindly.** Ship a small vocabulary validated by the CHI'23 agreement rates.
2. **Normalize everything by hand size** (`scale = ||wrist − index MCP||`, or world landmarks in meters).
3. **Hysteresis + debounce on every discrete state.** Two thresholds; N-frame confirmation; time-based cooldown.
4. **Smooth with 1€, not EMA alone**, and keep an explicit latency budget (< 60 ms added).
5. **Freeze the cursor when a click fires**; do not let the pointer drift during selection.
6. **Continuous feedback for continuous state.** Pinch openness drives a visible meter; hover drives target highlight.
7. **Explicit engage/idle** to defeat Midas touch (open palm = idle; UI dims; clicks disabled).
8. **Physical mouse always works.** Global kill switch (Esc or corner abort).
9. **Two-handed for scale, one-handed for pointing.** Scale = hands apart; pan = both hands translate.
10. **Area cursor + gain** for speed, with a precise mode toggle (fist/close) for fine targets.
11. **Everything is testable**: landmark streams are recorded and replayed in CI; overlay geometry gets golden tests.

---

## 5. Proposed architecture

New package, `uv`-managed, installable, with the old demos kept for reference.

```
VisionDrop/
├── pyproject.toml                 # uv project, console scripts, optional extras
├── src/visiondrop/
│   ├── app.py                     # wiring, global hotkeys, mode switching, kill switch
│   ├── config.py                  # layered config (defaults + user TOML + per-app profiles)
│   ├── capture.py                 # background camera thread, latest-frame handoff, timestamps
│   ├── tracking.py                # HandLandmarker wrapper: 2D + world landmarks, video mode
│   ├── features.py                # hand scale, pinch ratio, finger extension, velocity, palm normal
│   ├── filters.py                 # OneEuro, EMA, velocity estimator, forward prediction
│   ├── gestures.py                # FSMs: pinch (click/drag/double), dwell, two-hand zoom/pan, swipes, idle
│   ├── cursor.py                  # camera->screen mapping, gain, area cursor, clutch, freeze
│   ├── actions.py                 # Quartz/CGEvent + pyautogui fallback: click, drag, key, scroll
│   ├── targets.py                 # Accessibility (AXUIElement) hit-testing + snap
│   ├── overlay/
│   │   ├── base.py                # renderer interface, shape model, DPI-aware coordinates
│   │   └── macos.py               # NSPanel per display, click-through, Core Animation/Quartz drawing
│   ├── canvas.py                  # stroke model, RDP simplification, undo/redo, save SVG/PNG
│   ├── recognize.py               # $1/$P templates, shape fitting/beautification
│   ├── ocr.py                     # Vision VNRecognizeTextRequest -> tappable words/elements
│   ├── magnifier.py               # screen capture (mss/Quartz) + zoom/pan lens
│   ├── hud.py                     # corner HUD: mode, FPS, latency, pinch meter, skeleton toggle
│   └── telemetry.py               # latency/jitter/FPS logs, session recordings (JSONL)
├── tests/
│   ├── unit/                      # filters, FSMs, mapping, recognizer
│   ├── replay/                    # recorded landmark streams -> expected gesture labels
│   └── golden/                    # overlay geometry snapshots
├── data/recordings/               # labeled landmark sessions (git-ignored or LFS)
└── legacy/                        # current visiondrop_project + drag_squares_project (unchanged)
```

### Data flow

```
camera thread ──frame──▶ tracker thread ──landmarks+ts──▶ gesture/feature loop
                                                             │
                          ┌──────────────────────────────────┼───────────────────────────┐
                          ▼                                  ▼                           ▼
                   cursor/state machine              canvas/recognizer            magnifier/OCR
                          │                                  │                           │
                          └───────────────▶ overlay renderer (main thread, 60 Hz) ◀───────┘
                                                     │
                                                     ▼
                                        actions (Quartz injection)
```

- **Threads:** capture + inference off the main thread; AppKit UI strictly on the main thread.
- **Concurrency primitive:** single-slot latest-frame / latest-state handoff (no queues → no backlog lag).
- **Time:** every frame and landmark stamped; filters take real `dt`; telemetry records end-to-end latency.

### Gesture vocabulary (v1)

| Gesture | Detection | Action |
| --- | --- | --- |
| Point (index extended, others curled) | finger-extension features | Move cursor |
| Thumb–index pinch (hold) | normalized pinch ratio + hysteresis | Left click / drag; freeze cursor on engage |
| Thumb–middle pinch | same ratio on (4,12) | Right click |
| Double pinch | two engage edges < 350 ms | Double click |
| Two hands apart/together | inter-hand distance delta | Zoom / scale |
| Two hands translate | inter-hand centroid delta | Pan |
| Open palm held | all fingers extended, low motion | Idle / pause (Midas guard) |
| Swipe L/R (index+middle) | horizontal velocity threshold | Next / previous page |
| Dwell (optional) | cursor inside target for T ms | Click (progress ring), for accessibility |
| Fist (precise mode) | all curled | Reduce gain for fine targets |

Thresholds are **ratios, not pixels**, and all live in `config.py` for tuning.

### Visual feedback spec (fixes the "no visual feedback" complaint)

- **Cursor**: outer ring + inner dot; ring contracts as the pinch closes (continuous "pinch meter").
- **Hover**: target under cursor outlined; via Accessibility snap when available.
- **Click**: instant flash + cursor freeze (250 ms) + optional audio tick.
- **Drag**: anchor marker + elastic tether; drop target highlighted.
- **Scroll/navigate**: direction chevrons; page indicator.
- **Zoom/pan**: live scale badge + ghost outline of the pre-zoom frame; percentage.
- **Canvas**: pen cursor with size ring, color swatch, eraser radius, undo/redo toasts.
- **Shape snap**: after stroke end, show recognized shape with a 400 ms "morph" animation and a way to reject the snap.
- **Idle**: HUD dims, cursor hollows out; clicks are hard-disabled.
- **HUD**: mode badge, FPS, latency, pinch confidence; skeleton overlay is a debug toggle, **off by default**.

---

## 6. Feature plan (mapped to your list)

| Feature | Technique | Phase |
| --- | --- | --- |
| Fix pinch | normalization + hysteresis + 1€ + FSM + tests | 1 |
| Visual feedback | overlay renderer + state-driven visuals | 2 |
| Move/click/drag/right-click/scroll | Quartz event injection + freeze-on-click | 3 |
| Select / copy / edit | pinch-drag selection + Cmd+C/V/X/Z; AX element snap | 3 |
| Navigate pages | swipe L/R + scroll gestures; OCR page numbers | 3, 6 |
| Draw on canvas | stroke capture, RDP, colors, widths, undo/redo | 4 |
| Shape drawing w/ vision assist | $1/$P recognition + beautification | 4 |
| Annotations over screen | persistent vector layer, clear/undo, save PNG/SVG | 4 |
| Zoom / scale / pan | lens renderer + two-hand scale/pan | 5 |
| Detection of on-screen content | Vision OCR word/line boxes -> pinch targets | 5 |
| Add things | insert shapes/text/sticky notes into canvas layer | 4 |
| App profiles / settings | per-app gesture tuning, TOML config, settings UI | 6 |
| Packaging | `.app` bundle + TCC onboarding (camera, accessibility, screen recording) | 6 |

---

## 7. Phased roadmap with acceptance criteria

**Phase 0 — Foundations & measurement (1–2 days)**
- `pyproject.toml` + `uv` extras; `telemetry.py`; offline landmark recorder/replayer; debug HUD window (opt-in).
- Accept: can record a session and replay it; latency/FPS/jitter numbers are logged.

**Phase 1 — Interaction engine (3–5 days)**
- `tracking`, `features`, `filters`, `gestures` with hysteresis and hand-size normalization; unit + replay tests.
- Accept: pinch F1 ≥ 0.95 on a scripted recorded set; no stuck states after hand loss; added latency < 60 ms.

**Phase 2 — Overlay & cursor (5–7 days)**
- PyObjC click-through overlay per display (Retina + multi-monitor), cursor FSM, visual states, global hotkeys, kill switch.
- Accept: 60 fps overlay, verified click-through, cursor freeze on click, no interference with normal mouse use.

**Phase 3 — OS control (5–7 days)**
- Quartz click/drag/scroll/key injection, AX hit-test snap, copy/paste/undo, swipe navigation.
- Accept: complete a scripted workflow (open app, click, drag file, select text, copy, paste) hands-free ≥ 90% success.

**Phase 4 — Canvas (5–7 days)**
- Stroke model + renderer, tools, undo/redo, save, $1 shape snap/beautify.
- Accept: draw a labeled diagram; shape snapping correct ≥ 90% on the 5 base shapes.

**Phase 5 — Lens (5–7 days)**
- Magnifier, two-hand zoom/pan, Vision OCR targets ("pinch the word").
- Accept: read and zoom a PDF page; pinch a word to select it.

**Phase 6 — Polish & evaluation (1–2 weeks)**
- Onboarding/calibration, settings, packaging, TCC flows; run the study below.
- Accept: SUS ≥ 70; false-click rate < 1/min; Fitts throughput ≥ 2.5 bits/s.

**Stretch**
- WiLoR/HaMeR 3D backend behind a flag; neural 1€ successor (N-euro) ; voice commands; iPad/Windows port.

---

## 8. Platform requirements & permissions (macOS)

| Capability | Permission | Why |
| --- | --- | --- |
| Camera | Camera (TCC) | Tracking. |
| Move cursor / inject clicks & keys | Accessibility | Quartz `CGEventPost` requires it. |
| Magnifier + OCR + screenshots | Screen Recording | Capturing the screen. |
| Global hotkeys / kill switch | Input Monitoring (varies) | Toggle modes from anywhere. |

Distribution notes: unsigned Python apps must be bundled (py2app/Briefcase) and notarized for others; for
personal use, ad-hoc signing is fine. Permissions are granted to the **bundle**, not the terminal — plan the
packaging step early so permission prompts behave in dev too.

---

## 9. Evaluation plan

- **Quantitative**: motion-to-photon latency (target < 60 ms), cursor jitter (< 1 mm mean-to-peak), Fitts
  law throughput (bits/s) vs trackpad baseline, click error rate, gesture confusion matrix.
- **Qualitative**: SUS, Gesture Usability Scale (GSUS), NASA-TLX, session fatigue (gorilla arm), interviews.
- **Protocol**: 8–12 participants, 3 conditions (trackpad, current demo, new engine), counterbalanced task
  order; tasks: target acquire, drag-drop, text select+copy, draw+snap, zoom+read.
- **Rolling**: replay-based regression gate in CI (no metric regressions on the recorded set).

---

## 10. Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Arm fatigue (gorilla arm) | Short sessions, relative mode + clutch, gain, precise-mode fist, idle detection. |
| Occlusion / self-occlusion | MediaPipe robustness + world landmarks; optional 3D backend (research-only license). |
| Jitter vs lag | 1€ filter with per-mode tuning; forward prediction; measured latency budget. |
| Accidental input (Midas) | Open-palm idle, freeze-on-click, audio/visual confirmation, global kill switch, undo everywhere. |
| Overlay fights the OS | Verified click-through pattern (`ignoresMouseEvents`, panel level, all-spaces); never intercept the real mouse. |
| TCC friction | Package early; onboarding screen that deep-links to each Settings pane; degrade gracefully. |
| Multi-monitor/DPI | Per-display overlays, `backingScaleFactor`-aware geometry, golden tests. |
| License traps | Apache/MIT/BSD components only by default; WiLoR/MANO docs marked non-commercial. |
| Scope creep | Phases independently shippable; each has measurable acceptance criteria. |

---

## 11. Decisions (answered 2026-09-22)

1. **Platform scope:** macOS-only. Use PyObjC `NSPanel` click-through overlays, Quartz event injection,
   and Apple Vision OCR.
2. **Camera placement:** laptop webcam. Consequences accepted: hands sit below the screen, so the active-box
   mapping, control-display gain, and clutch behavior matter more; ergonomics review is required in Phase 6.
3. **Repo strategy:** new `src/visiondrop` package managed by `uv`; the existing `visiondrop_project/` and
   `drag_squares_project/` move to `legacy/` unchanged.
4. **Selection model:** pinch only for v1. Dwell selection is deferred to a later phase as an accessibility
   option and should be evaluated with the Pinch/Click/Dwell protocol when added.
5. **Drawing target:** (deferred) annotation layer over the live desktop first; standalone exportable canvas
   is a stretch goal in Phase 4.

---

## 12. References

**Papers**
- Zhang et al., *MediaPipe Hands: On-device Real-time Hand Tracking*, CVPRW 2020 — arXiv:2006.10214
- Lugaresi et al., *MediaPipe: A Framework for Building Perception Pipelines*, 2019 — arXiv:1906.08172
- Bazarevsky et al., *BlazeFace*, 2019 — arXiv:1907.05047
- Google, *On-device Real-time Hand Gesture Recognition*, 2021 — arXiv:2111.00038
- Pavlakos et al., *Reconstructing Hands in 3D with Transformers (HaMeR)*, CVPR 2024 — arXiv:2312.05251
- Potamias et al., *WiLoR: End-to-end 3D Hand Localization and Reconstruction in-the-wild*, CVPR 2025 — arXiv:2409.12259
- Foteinos et al., *Visual Hand Gesture Recognition with Deep Learning: A Comprehensive Review*, 2025 — arXiv:2507.04465
- Linardakis et al., *Survey on Hand Gesture Recognition from Visual Input*, 2025 — arXiv:2501.11992
- Casiez, Roussel, Vogel, *1€ Filter*, CHI 2012 — DOI 10.1145/2207676.2208639
- Shao et al., *N-euro Predictor*, IMWUT 2023 — DOI 10.1145/3610884
- Waugh et al., *Everything to Gain: Area Cursors + Control-Display Gain*, CHI 2025 — DOI 10.1145/3706598.3714021
- Hosseini et al., *Towards a Consensus Gesture Set*, CHI 2023 — DOI 10.1145/3544548.3581420
- Pasquale et al., *A mid-air gesture dictionary for web-based interaction*, 2024 — arXiv:2404.05842
- Waugh et al., *Push or Pinch?*, 2022 — DOI 10.1145/3546155.3546702
- *Pinch, Click, or Dwell*, ACM 2021 — DOI 10.1145/3448018.3457998
- *Can't (Midas) touch this: Evaluation of Clutching*, 2025 — DOI 10.1145/3743049.3743055
- Kostic et al., *Exploring Mid-Air Hand Interaction in Data Visualization*, 2023 — arXiv:2311.15372
- *Don't Touch Me! Touch vs Non-Touch Inputs*, INTERACT 2021 — arXiv:2107.05408
- *AirPen: Touchless Fingertip Based Gestural Interface*, 2019 — arXiv:1904.06122
- Wobbrock, Wilson, Li, *A $1 Recognizer for UI Prototypes*, UIST 2007 — DOI 10.1145/1294211.1294238
- Vatavu, Anthony, Wobbrock, *$P Point-Cloud Recognizer*, ICMI 2012
- *Effects of Latency Jitter and Dropouts in Pointing Tasks*, CEUR Vol-588

**Open source**
- MediaPipe — github.com/google-ai-edge/mediapipe (Apache-2.0)
- MediaPipe Hand Landmarker (Tasks) — ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
- Kazuhito00/simple-virtual-mouse-using-mediapipe (Apache-2.0)
- harrynoble/Gesture-Cursor
- adammcarter/annotate (MIT) — macOS click-through overlay architecture
- loomhq/ElectronMacOSClickThrough
- DmytroVasin/DrawPen (MIT)
- opensourcebharat/lekhini
- CreativeInquiry/handsfree-js
- KTokos/MediaPipeGestureDetection
- MahmudulAlam/Unified-Gesture-and-Fingertip-Detection (MIT)
- pupil-labs/gaze-control
- rolpotamias/WiLoR; geopavlakos/hamer
- Wobbrock $1/$N/$P/$Q — depts.washington.edu/acelab/proj/dollar (New BSD)

---

## 13. Immediate next step

The next product step is the click-through overlay, but only after the M1 evidence is collected: capture
representative real v2 landmark sessions, explicitly convert any retained prototype material to v2, and
establish the labelled evaluation corpus and Vision-versus-MediaPipe comparison. The Swift reader
rejects prototype v1, so conversion must be a deliberate, validated data step rather than an implicit
compatibility path. Do not treat the synthetic fixture or unit suite as the M1/M2 evaluation, and do
not mark the original Phase 0/1 acceptance criteria complete.
