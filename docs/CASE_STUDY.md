# VisionDrop 2.0 — Case Study & Project Plan

**Working title:** *VisionDrop: A Webcam-Based Mid-Air Drag-and-Drop System for Real Objects*

**Status:** Planning
**Last updated:** 2026-09-13

---

## 1. Executive summary

VisionDrop currently proves the concept: a webcam, MediaPipe hand tracking, a touchless cursor, and color-blob detection. It does not yet implement the thing its name promises — dragging and dropping.

VisionDrop 2.0 turns the demo into a real system: **you pinch a physical object on your desk (a cup, a phone, an apple), move it in the air, and release it into a virtual zone shown on screen.** The object is tracked by a modern detector, the hand by MediaPipe's Tasks API, and the interaction is governed by a filtered, debounced state machine designed from published HCI research rather than intuition.

The deliverable is a portfolio-grade case study with four parts: a working system, a small user study comparing interaction designs, a demo video, and this write-up. The practical framing is **contactless sorting** — lab benches, kitchens, clinical/sterile environments, and accessibility — where touching a shared screen or mouse is undesirable. The cool factor is that the objects are physically real.

---

## 2. Problem & motivation

### 2.1 Why touchless

Direct manipulation (grab an object, move it, drop it) is the most intuitive interaction paradigm we have. Touchscreens brought it to digital content, but they require contact, and contact has measurable costs:

- 82% of surveyed consumers consider touchscreens unhygienic and prefer touchless alternatives ([Digital Signage Today / Ultraleap panel](https://www.digitalsignagetoday.com/articles/touchless-drives-vending-kiosks-interactive-signage)).
- In operating rooms, scrubbed surgeons cannot touch keyboards without breaking asepsis. Touchless navigation of radiological images is an active, validated research area ([Jacob et al., JAMIA 2013](https://pubmed.ncbi.nlm.nih.gov/23250787/); [CACM, Touchless Interaction in Surgery](https://cacm.acm.org/research/touchless-interaction-in-surgery)).
- For users with motor impairments, mid-air gestures can replace precision motor tasks (mouse aiming, clicking) with gross motor tasks (pointing, pinching) that are easier to perform.

### 2.2 Why drag-and-drop specifically

Drag-and-drop is the canonical direct-manipulation task. It exercises every hard problem in gesture interfaces at once:

1. **Selection** — acquiring a target without a click event.
2. **Continuous control** — tracking the hand with acceptable precision and latency.
3. **State transitions** — distinguishing hover, grab, drag, release with no hardware button.
4. **Feedback** — confirming state changes the user cannot feel.

If the system handles drag-and-drop well, it generalizes to sorting, organizing, photo management, file handling, AR assembly, and gameplay. That makes it the right case study scope.

### 2.3 Why real objects

Virtual object demos (drag a colored square) do not test the hard part of the problem: whether perception can associate a hand with an object and maintain that association through occlusion, motion blur, and lighting changes. Real objects also make the application practical — sorting pills, parts, tools, produce, samples — instead of a toy.

---

## 3. Current implementation assessment

| Area | Current state | Gap |
|---|---|---|
| Hand tracking | Legacy `mp.solutions.hands`, `.find_hands()` in `visiondrop_project/hand_tracker.py` | Legacy API; no Tasks API migration; no handedness/laterality; no landmark confidence filtering |
| Cursor | Palm center (landmark 9) in `hand_tracker.py:36` | Not a pinch point; causes offset errors; no filter, so cursor jitters |
| Object detection | HSV yellow threshold in `object_detector.py:27-33` | Brittle to lighting; only yellow; no tracking; no classification of real objects |
| Interaction | Zone membership test only (`vision_drag_drop.py:76-85`) | No grab, no drag, no release, no state machine, no hysteresis |
| Drop zones | Hardcoded in `config.py:11-14` | Not data-driven; no zone metadata/labels |
| Feedback | Dot color change | No audio, no animation, no pseudo-haptics, no grab confirmation |
| Performance | Single thread; TensorFlow imported at startup (`vision_drag_drop.py:1-2`) | Detection and rendering serialize; TF/JAX dependencies (~2 GB) unused by MediaPipe |
| Testing | None | No unit tests for geometry, state, or association logic |

**Conclusion:** the perception layer needs replacement (legacy → Tasks API + YOLO), and the interaction layer needs to be built from scratch. The repository structure and configuration/logging habits are worth keeping.

---

## 4. State of the art (2025–2026)

### 4.1 Perception stack

**Hand tracking.** [MediaPipe Hands](https://arxiv.org/pdf/2006.10214) (Zhang et al., 2020) remains the baseline: 21 2.5D landmarks per hand, real-time on commodity hardware. The modern interface is the [MediaPipe Tasks Vision API](https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer/python) — `HandLandmarker` and `GestureRecognizer` — which replaced the legacy `mp.solutions` path. The built-in gesture classifier recognizes seven canned classes plus `None`:

> `Closed_Fist`, `Open_Palm`, `Pointing_Up`, `Thumb_Down`, `Thumb_Up`, `Victory`, `ILoveYou`

Custom gestures are possible via Model Maker, but the canned set plus geometric pinch detection covers this project.

**Object detection.** [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11) is the pragmatic choice: YOLO11n is 2.6M params, 39.5 mAP (COCO val 50-95), ~1.5 ms on T4 TensorRT, ~56 ms CPU ONNX, with built-in multi-object tracking (ByteTrack/BoT-SORT). [YOLO26](https://arxiv.org/html/2510.09653) (2026) removes NMS and distribution focal loss, further improving CPU inference (~38.9 ms, ~39.8% mAP) — relevant if the target machine has no GPU. Alternatives: RT-DETR/DEIM (higher AP, higher cost), or keeping an HSV fallback for custom objects not in COCO.

**Smoothing.** Raw landmark coordinates jitter visibly at rest. The [1€ filter](https://gery.casiez.net/1euro) (Casiez et al., CHI 2012) is the standard fix: a speed-adaptive low-pass filter that smooths when slow and reduces lag when fast. It ships inside MediaPipe and Chrome. For occlusion (hand behind object), a 2024 CISAI study ([DOI 10.1145/3703187.3703295](https://dl.acm.org/doi/10.1145/3703187.3703295)) combines historical trajectory, Kalman filtering, and smoothing to survive "layer crossing" and maintain tracking.

**Hand–object interaction research.** Determining whether a hand is actually grasping an object — not just near it — is an active field:

- [Ego-HOI detection](https://arxiv.org/abs/2109.14734) (Lu & Mayol-Cuevas): 89% accuracy at >30 FPS using hand pose + hand mask + in-hand object mask, with a half-second temporal filter to suppress flicker.
- [HOT3D](https://arxiv.org/abs/2406.09598) (Meta, 2024): 833 minutes / 3.7M images of egocentric hand–object tracking on Quest 3 and Aria, with 3D pose ground truth. Useful for validating the association problem.
- [Ego-HOIBench](https://arxiv.org/abs/2506.14189) (2025): 27K egocentric images with fine-grained hand-verb-object annotations.
- Surveys: [Survey on Hand Gesture Recognition from Visual Input](https://arxiv.org/abs/2501.11992) (2025) and [Visual HGR with Deep Learning](https://arxiv.org/abs/2507.04465) (2025) map the method/dataset landscape.

### 4.2 Interaction research (what actually works)

- **Gesture choice for translation.** Remizova's doctoral thesis ([Mid-Air Gestural Interaction with Large Interactive Displays](https://researchportal.tuni.fi/en/publications/mid-air-gestural-interaction-with-large-interactive-displays), Tampere 2026, N=30 in Study I) compared fist-, palm-, pinch-, and sideways-based translation of 2D objects. Pinch-based grasping is the strongest fit for object manipulation; sideways/fist gestures are better for coarse translation.
- **Confirmation: tap beats dwell.** The same thesis found tapping with audio-visual feedback yielded ~60% higher throughput than dwell-based selection, was faster, and produced fewer target re-entries. Dwell remains useful as a fallback for users who cannot pinch. Dwell thresholds in the literature range 200–1000 ms ([GaVe gaze-vending study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10640920)).
- **Pseudo-haptic feedback.** Without force feedback, mid-air interaction feels weightless. [Kim & Xiong (2021)](https://arxiv.org/abs/2112.11007) found proximity feedback, protrusion, hit effects, and penetration blocking all improve perceived haptics, embodiment, satisfaction, and spatial perception; protrusion and hit effects are the most beneficial. Practical translation: an object that lags slightly behind the cursor, scales up when hovered, and pops when dropped reads as "physical."
- **Gesture consensus is weak.** A [CHI 2023 survey](https://dl.acm.org/doi/full/10.1145/3544548.3581420) and [Vuletic et al.'s 2019 review of 148 interfaces](https://www.sciencedirect.com/science/article/pii/S1071581918305676) both conclude that mid-air gestures are frequently *not* intuitive and must be taught. Onboarding cannot be skipped.
- **Objects as gesture props.** [Objestures](https://arxiv.org/abs/2503.02973) (CHI 2026) explores squeezing and manipulating everyday objects as expressive input — a reminder that the physical object need not merely be a target; it can carry state (e.g., squeeze to confirm).
- **Comfort limits.** Gestures far from the body (>30 cm) and long holds (>6 s) reduce public acceptance/comfort ([Ahlström & Hasan, MobileHCI 2014](https://hci.cs.umanitoba.ca/assets/publication_files/MobileHCI_2014-Khalad-Social.PDF)). Arm fatigue bounds interaction duration; industrial deployers keep sessions short and gestures compact.

### 4.3 Practical deployments

- **Sterile/OR**: touchless radiology navigation (Jacob 2013; [Wipfli et al. 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4833285/)); [usability of a touchless image viewer in the OR](https://pmc.ncbi.nlm.nih.gov/articles/PMC6989265/) (2020) — gesture sets must respect sterile field constraints, not just preference.
- **Kiosks/public displays**: commercial gesture kiosks ship today (e.g., Imageholders, 2021). [Ultraleap's TouchFree guidance](https://docs.ultraleap.com/TouchFree/touchless-interfaces/guidance.html) codifies onboarding: attract loop (5–8 s animated instructions), visible cursor, explicit "this is touchless" messaging. The [audience funnel](https://scispace.com/papers/the-audience-funnel-observations-of-gesture-based-vjz9i0u0sq) models how passersby graduate from watching to interacting.
- **Rehabilitation**: vision-based "Gesture Therapy" was evaluated in a controlled clinical trial for stroke upper-limb rehab ([Sucar et al. 2010](https://pubmed.ncbi.nlm.nih.gov/21096856)); the [VIGoROUS RCT](https://www.thelancet.com/journals/eclinm/article/PIIS2589-5370(21)00520-4/fulltext) validated home self-managed game-based therapy. Consumer tracking hardware is accurate enough for clinical use ([EU ImpHandRehab](https://cordis.europa.eu/article/id/436475-virtual-reality-helps-stroke-patients-overcome-hand-movement-impairments)).

### 4.4 Prior art & demos

| Project | What it does | Lesson for us |
|---|---|---|
| [XianlinLu/air-canvas](https://github.com/XianlinLu/air-canvas) | Draw in air; open palm inflates shapes into 3D balloons (Three.js) | Gesture-to-state transition on hold; delight through transformation |
| [charanuggala26/Virtual-Mouse](https://github.com/charanuggala26/Virtual-Mouse) | Pinch-and-hold drag & drop, scroll, screenshot, OS volume/brightness | Modular package layout; cooldown/hysteresis logic; exponential smoothing |
| [mvipin/gesturebot](https://github.com/mvipin/gesturebot) | MediaPipe gestures drive a ROS 2 robot on Raspberry Pi 5 | Deployment discipline: FPS/resource measurement, graceful degradation |
| [aayush23206/Air-Canvas](https://github.com/aayush23206/Air-Canvas) | Point to draw, two fingers to erase | Extremely clear gesture mapping and onboarding README |
| MediaPipe Studio / Gesture Recognizer demo | Browser demos for all vision tasks | Reference behavior for the Tasks API; baseline for our gesture latency |
| MP-GestLSTM ([paper](https://www.tandfonline.com/doi/full/10.1080/21642583.2025.2587853)) | Sign-language keypoint sequences → text | Path forward if we later add dynamic/custom gestures |

---

## 5. Design implications (research → requirements)

Each requirement below traces to a source above.

| # | Requirement | Source |
|---|---|---|
| R1 | Migrate to MediaPipe Tasks API (`HandLandmarker` + `GestureRecognizer`, VIDEO mode) | Google AI Edge docs; legacy API is a dead end |
| R2 | Detect real objects with a tracking detector (YOLO11n + ByteTrack), keep HSV as configurable fallback | YOLO11 benchmarks; brittleness of HSV in current repo |
| R3 | Use the pinch point (midpoint of thumb tip + index tip), not palm center, as the interaction cursor | MediaPipe landmark semantics; current `hand_tracker.py:36` offset error |
| R4 | Filter cursor and object positions with the 1€ filter (per-axis), tuned for low lag | Casiez CHI 2012; MediaPipe/Chrome precedent |
| R5 | Explicit FSM with hysteresis, frame debouncing, and cooldowns; no interaction without intent | Virtual-Mouse cooldown pattern; Midas-touch problem in GaVe |
| R6 | Grab confirmation must be immediate and multimodal (audio + visual state change) | Remizova 2026: tap + AV feedback ≈ 60% throughput gain vs dwell |
| R7 | Pseudo-haptic rendering: object lags behind cursor, scales on hover, pops on drop | Kim & Xiong 2021 |
| R8 | Onboarding built in: visible cursor, attract/instruction overlay, 5–8 s animated hint | Ultraleap TouchFree guidance |
| R9 | Dwell-to-grab as an alternative mode for users who cannot pinch | Remizova 2026; accessibility |
| R10 | Sessions short; gestures compact; no sustained overhead reaches | MobileHCI 2014 comfort study; fatigue |
| R11 | Occlusion handling: predict through loss using velocity + temporal filtering (≥0.5 s tolerance) | Ego-HOI temporal filter; CISAI 2024 |
| R12 | Instrument everything: per-stage latency, FPS, event log for evaluation | gesturebot deployment measurements |

---

## 6. System design

### 6.1 Architecture

```
                    ┌─────────────────────────────────────────┐
                    │              Camera (720p30)             │
                    └───────────────┬──────────────┬───────────┘
                                    │              │
                 Thread A: hands    │              │   Thread B: objects
        ┌───────────────────────────▼──┐        ┌──▼──────────────────────────┐
        │ MediaPipe Tasks (VIDEO mode) │        │ YOLO11n + ByteTrack         │
        │  - HandLandmarker (21 pts)   │        │  - COCO classes + tracking  │
        │  - GestureRecognizer (canned)│        │  - every 2–3 frames, tracker│
        └───────────────┬──────────────┘        │    fills gaps               │
                        │ landmarks, gesture    └──┬──────────────────────────┘
                        │                          │ detections + IDs
                        └────────────┬─────────────┘
                                     ▼
                       ┌───────────────────────────────┐
                       │  Fusion layer                 │
                       │  - pinch point extraction     │
                       │  - hand↔object association    │
                       │    (distance gating + hand    │
                       │     size normalization)       │
                       │  - 1€ filter (cursor, objects)│
                       │  - velocity estimation        │
                       └──────────────┬────────────────┘
                                      ▼
                       ┌───────────────────────────────┐
                       │  Interaction FSM              │
                       │  IDLE→HOVER→GRAB→DRAG→DROP    │
                       │  hysteresis, debounce, cooldown│
                       └──────────────┬────────────────┘
                                      ▼
                       ┌───────────────────────────────┐
                       │  Renderer + feedback          │
                       │  zones, snapping, pseudo-haptics│
                       │  audio, particles, HUD, score │
                       └───────────────────────────────┘
```

Design rules:

- **Pure logic is separated from rendering.** FSM, association, filtering, and geometry are plain functions/classes testable with pytest and without a camera.
- **Threading**: capture → [hands ∥ objects] → fusion → render, with the newest-frame-wins policy. YOLO runs every N frames; ByteTrack interpolates between detections. Hand inference runs every frame (it is the interaction-critical path).
- **Config over code**: objects of interest, zones (with labels/scores), gesture mode (pinch/dwell/fist), thresholds, and filter parameters live in one dataclass-based config.

### 6.2 Interaction state machine

States and transitions (pinch mode):

| State | Entry condition | Exit condition | Behavior |
|---|---|---|---|
| `IDLE` | Default | Cursor within `hover_radius` of an object | Cursor visible, no target |
| `HOVER` | Above + stays `hover_frames` | Pinch closes (`dist(thumb,index) < grab_threshold` for `grab_frames`), or cursor leaves `hover_radius * 1.3` (hysteresis) | Target highlighted, grows slightly (protrusion) |
| `GRAB` | Pinch closed on a target | Immediate transition to `DRAG` | Grab sound (short click), target ring flash |
| `DRAG` | After GRAB | Pinch opens (`> release_threshold`) → `DROP`; hand lost > `loss_tolerance` (0.5 s) → `CANCEL` | Object follows filtered cursor with a slight lag (mass illusion); valid zones highlight if in range |
| `DROP` | Release event | After snap/return animation | In zone → snap, score, success sound; outside → return-to-origin spring, soft error sound |
| `CANCEL` | Hand lost during drag | Object restored | Fade object back to origin |

Rules learned from research encoded here: separate grab/release thresholds (hysteresis), N-frame debouncing, cooldowns after a drop, dwell variant replaces the pinch condition with "hover for `dwell_ms`", and an explicit `CANCEL` path so a lost track never strands an object.

### 6.3 Latency budget

Motion-to-photon latency is the single biggest predictor of perceived quality in direct manipulation.

| Stage | Target (GPU) | Target (CPU) |
|---|---|---|
| Capture + color convert | 3 ms | 3 ms |
| Hand landmarks + gesture | 8–15 ms | 20–35 ms |
| YOLO11n (amortized every 3rd frame) | 2–5 ms | 15–25 ms |
| Fusion + filters + FSM | < 1 ms | < 1 ms |
| Render + display | 5 ms | 5 ms |
| **Total** | **< 35 ms** | **< 75 ms** |

Instrumentation: timestamp every stage per frame, log rolling p50/p95, display them in a debug HUD toggled with a key.

### 6.4 Feedback design (multimodal, per R6–R8)

- **Visual**: cursor dot with velocity tail; hover highlight + 8% scale-up; grab ring pulse; drag shadow; zone glow when the held object is over a valid zone; snap animation with slight overshoot.
- **Audio**: short click on grab, soft tick while crossing a zone boundary, success chime on drop, muted thud on invalid drop. (Current deps include `sounddevice`; pygame.mixer is an alternative.)
- **Pseudo-haptic**: object position lerps toward the cursor (not rigidly attached) using a spring; trail particle effect communicates motion; released object springs back on invalid drop.
- **Onboarding**: attract overlay with a 5–8 s looping hand animation, explicit "Touchless controls" label, instruction line ("Pinch to grab, release to drop"), shown until the first successful drop.

---

## 7. Scope

### MVP (must ship)
- Tasks API migration, TF/JAX removed from runtime deps.
- YOLO11n detection + tracking, COCO objects of interest on a configurable allowlist.
- Pinch grab/release with the FSM above, 1€ filtering.
- ≥1 zone; drop → score; debug HUD with FPS/latency.
- Deterministic unit tests for geometry, association, FSM, filter.

### V1 (the case study build)
- Multiple labeled zones and a sorting task with timer/score.
- Full feedback set (audio + pseudo-haptics + onboarding overlay).
- Dwell-grab mode as an alternative condition.
- Session logging (JSONL) and an analysis script producing the evaluation tables/plots.
- Recorded-video replay mode for reproducible testing without a camera.

### V2 (stretch)
- Two-handed interaction (hold zone open with one hand, sort with the other).
- Custom object classes via a few-shot fine-tune of YOLO11n.
- Custom gestures via MediaPipe Model Maker (e.g., "OK" to confirm a drop).
- Optional 3D depth via stereo/webcam depth estimation for real z-ordering.
- Packaging: single `python -m visiondrop` entry point, prebuilt model download on first run.

---

## 8. Milestones

| # | Milestone | Deliverable | Acceptance test | Est. |
|---|---|---|---|---|
| M0 | Foundation | Tasks API `HandLandmarker` + `GestureRecognizer` in `hand_tracker.py`; deps slimmed; package restructure | `pytest` green; app runs 30 FPS with no TensorFlow installed | 1 wk |
| M1 | Perception | YOLO11n + ByteTrack detector module; hand–object association; debug overlay | Held cup remains associated through 0.5 s occlusion; p95 detection ≤ 20 ms GPU | 1 wk |
| M2 | Interaction core | 1€ filter; FSM with hysteresis/debounce; pinch grab/release | Unit tests pass on synthetic landmark sequences; zero accidental grabs over 5 min idle hand motion | 1 wk |
| M3 | Game & feedback | Zones, scoring, audio, pseudo-haptics, onboarding overlay | 10/10 successful intentional drops in a manual session; instructions understood without verbal explanation | 1 wk |
| M4 | Evaluation harness | JSONL event logging, latency instrumentation, replay mode, analysis script | Replay of a recorded session reproduces the same metrics; plots generated | 3–4 days |
| M5 | Study & write-up | n≈12–15 within-subject study; results section; demo video; README/GUIDE update | Report complete with metrics, SUS/TLX, screenshots, and honest limitations | 1 wk |

Total: ~5–6 weeks part-time.

### Progress log

- **2026-09-13 — M0 complete.** Tasks API migration, `src/visiondrop/` package,
  TensorFlow/JAX removed from runtime deps, 19 tests. Hand tracking measured at
  10.3 ms/frame worst case (~97 FPS) on CPU.
- **2026-09-13 — M1 complete.** YOLO11n + ByteTrack detector with class
  allowlist, HSV fallback retained, hand–object association with hand-scale
  radius, association line + debug latency HUD, 39 tests. CPU detection measured
  at p50 34 ms / p95 37 ms (imgsz 640), tunable with `--imgsz`; the GPU p95
  acceptance target (≤ 20 ms) is unverified here (no NVIDIA GPU available).
- **2026-09-13 — M2 complete.** 1€ filter (`filters.py`), scale-invariant
  `Hand.pinch_ratio`, and `InteractionEngine` (`interaction.py`): IDLE/HOVER/DRAG
  with frame debouncing, grab/release hysteresis, 0.5 s occlusion tolerance,
  drop cooldown, and association-aware held-object tracking. 63 tests including
  a 5-minute idle-jitter simulation with zero grabs and integration checks on
  real media (`samples/` via `scripts/fetch_samples.py`). The transient GRAB
  state from the plan table is represented by the `"grabbed"` event instead of
  a separate state.
- **2026-09-13 — M3 complete.** Drop resolution into labeled zones
  (`find_zone`), score/miss HUD, sound cues via `sounddevice` with graceful
  silence when no device exists, expanding flash hit effect, hover protrusion,
  and an onboarding overlay shown until the first successful drop. 72 tests.
  Pseudo-haptics are implemented as protrusion (hover) + hit effect (drop) per
  Kim & Xiong; the object-lag illusion does not apply because real objects are
  tracked, not simulated. Manual acceptance (10/10 intentional drops;
  instructions understood without verbal explanation) is pending a webcam
  session.
- **2026-09-13 — M4 complete.** JSONL session recorder (`session.py`), `--log`
  flag, deterministic file-source timestamps so replay re-derives identical
  timestamps and interaction metrics (covered by a replay test in
  `tests/test_samples.py`), `analysis.py` metrics plus a cv2 latency/event plot
  with zero new plotting dependencies, and `scripts/analyze_session.py`. 82
  tests. Latency metrics are machine-specific; interaction metrics reproduce.
- **2026-09-13 — M5 in progress (study prep complete).** Dwell condition
  implemented (`--condition dwell`: hover 0.5 s to grab, dwell 0.5 s beyond
  80 px from the grab point to drop; `InteractionConfig.dwell_*` knobs), session
  logs record the condition in a `session_start` event, and
  `docs/STUDY_PROTOCOL.md` specifies participants, counterbalanced procedure,
  metrics, analysis plan, and the demo storyboard. 85 tests. Remaining:
  mouse-baseline instrument (~1 h), participant sessions, results write-up,
  demo video — all require hardware and humans.

---

## 9. Evaluation protocol

### 9.1 Research questions

- **RQ1 (interaction):** Does pinch-grab outperform dwell-grab for task throughput and accuracy in real-object sorting?
- **RQ2 (filtering):** Does the 1€ filter improve path smoothness without degrading completion time versus raw landmarks?
- **RQ3 (feedback):** Do audio + pseudo-haptic feedback reduce invalid drops and improve subjective ratings?

### 9.2 Design

Within-subject, counterbalanced order of conditions:

1. **Pinch** — pinch to grab, release to drop.
2. **Dwell** — hover 500 ms to grab, pinch/open-hand or dwell on target zone to drop.
3. **Mouse baseline** — drag objects with the mouse on a mirrored on-screen representation (input-effort comparison, not a fair fight; report transparently).

Tasks: sort N=12 objects into 2–3 categories (e.g., "cup/bottle → Container", "phone/remote → Electronics", "fruit → Food"), 3 repetitions per condition. Objects are COCO classes the detector was not trained on by us — this tests real-world generalization.

### 9.3 Metrics

- **Performance:** task completion time, grabs per minute, grab success rate (correct object attached / grab attempts), drop accuracy (objects in correct zone), invalid drops, path efficiency (straight-line / actual cursor path length).
- **System:** end-to-end latency p50/p95, FPS p50/p95, tracking loss rate.
- **Subjective:** System Usability Scale (SUS), NASA-TLX, gesture preference ranking, free-text comments.
- **Safety/hygiene framing:** number of unintended interactions during "non-use" segments (Midas-touch proxy).

### 9.4 Analysis

Per-participant means, paired comparisons (Wilcoxon signed-rank for non-normal Likert/times), effect sizes (r or Cohen's d), and qualitative coding of comments. Report all conditions honestly, including where the mouse wins — the value of the study is showing where touchless is viable, not pretending it is universally better.

### 9.5 Reproducibility

- Config files pin: model versions, thresholds, filter parameters, zone layouts.
- Every session logs raw events (`frame_idx`, `timestamp_ns`, `state`, `object_id`, positions, event type) as JSONL.
- Replay mode renders a recorded MP4 through the pipeline so results can be re-derived without live participants.

---

## 10. Tech stack & decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python 3.11 | Session code and MediaPipe wheel support |
| Hands | `mediapipe` Tasks Vision (`HandLandmarker` + `GestureRecognizer`) | Modern API, canned gestures, VIDEO mode |
| Objects | `ultralytics` YOLO11n (+ ByteTrack); HSV fallback | Real objects, fast, tracking included; fallback for custom objects |
| Vision utilities | OpenCV | Already in stack |
| Filtering | 1€ filter (vendored, ~40 lines) + simple velocity predictor for occlusion | Proven; avoids a dependency for trivial math |
| Audio | `sounddevice` (already a dependency) or `pygame.mixer` | Cross-platform, low latency |
| Rendering | OpenCV only for V1; optional Pygame/ModernGL for V2 effects | Keep the MVP shippable; fancy rendering is not the research question |
| Testing | pytest, synthetic landmark fixtures | Pure-logic separation makes this cheap |
| Packaging | `pyproject.toml`; `python -m visiondrop` | Replaces ad-hoc scripts |
| Removed | tensorflow, keras, jax, matplotlib (runtime), absl/gast/optree chain | ~2 GB of unused runtime weight |

---

## 11. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Lighting-dependent hand tracking failure | Medium | High | Expose confidence thresholds; CLAHE preprocessing; test in 3 lighting conditions; document requirements |
| CPU-only machines miss latency budget | High | Medium | YOLO every 3rd frame; model-complexity 0 for hands; downscale to 640px processing resolution; publish CPU configuration |
| YOLO misses small/custom objects | Medium | Medium | Configurable class allowlist; HSV fallback; V2 fine-tune |
| Depth ambiguity (hand behind object) | Medium | Low | We render held objects above the hand with offset; z-error is a documented limitation |
| Gestures not discovered by users | High | High | Mandatory onboarding overlay (R8); first-run tutorial mode; user study measures learnability |
| MediaPipe API churn | Low | Medium | Pin versions in `pyproject.toml`; isolate MediaPipe behind one adapter class |
| Study bias from author as only expert user | High | Medium | Recruit naive participants; script standardized instructions; counterbalance order |
| Scope creep (physics, 3D, multiplayer) | High | Medium | V2 list is explicitly out of MVP acceptance; only R1–R12 are in scope |

---

## 12. Limitations & future work

- **Monocular RGB cannot resolve true 3D.** Hand–object contact is inferred from 2D proximity; a depth camera or stereo would make grasping unambiguous.
- **Single-hand study.** Bimanual manipulation (hold a container with one hand, place objects into it with the other) is the natural next step and is well supported by MediaPipe's two-hand detection.
- **No force feedback.** Pseudo-haptics simulate weight, but a wearable haptic (band, glove) would close the loop; this connects to research like EI-Lite (UIST 2025).
- **Fixed gesture vocabulary.** Dynamic gestures (swipes, circles) and user-defined gestures are future work; the [Objestures](https://arxiv.org/abs/2503.02973) line of work suggests props and squeezes as an expressive extension.
- **Generalization.** The study tests one environment; robustness across skin tones, hand sizes, and lighting remains an open problem documented in the surveys.

---

## 13. References

**Perception**
1. Zhang et al. *MediaPipe Hands: On-device Real-time Hand Tracking*, 2020. https://arxiv.org/pdf/2006.10214
2. Google AI Edge. *Gesture recognition task guide (Python)*. https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer/python
3. Ultralytics. *YOLO11 documentation*. https://docs.ultralytics.com/models/yolo11
4. Sapkota & Karkee. *Ultralytics YOLO Evolution (YOLO26, YOLO11, YOLOv8, YOLOv5)*, 2026. https://arxiv.org/html/2510.09653
5. Lu & Mayol-Cuevas. *Egocentric Hand-object Interaction Detection and Application*, 2021. https://arxiv.org/abs/2109.14734
6. Banerjee et al. *HOT3D: Egocentric Dataset for 3D Hand and Object Tracking*, 2024. https://arxiv.org/abs/2406.09598
7. Deng et al. *Egocentric Human-Object Interaction Detection: A New Benchmark and Method*, 2025. https://arxiv.org/abs/2506.14189
8. Linardakis et al. *Survey on Hand Gesture Recognition from Visual Input*, 2025. https://arxiv.org/abs/2501.11992
9. Foteinos et al. *Visual Hand Gesture Recognition with Deep Learning*, 2025/2026. https://arxiv.org/abs/2507.04465

**Filtering & tracking stability**
10. Casiez, Roussel & Vogel. *1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in Interactive Systems*, CHI 2012. https://gery.casiez.net/1euro
11. *Gesture Recognition Improvement of MediaPipe Based on Historical Trajectory, Kalman Filtering and Smooth Filtering*, CISAI 2024. https://dl.acm.org/doi/10.1145/3703187.3703295

**Interaction design**
12. Remizova. *Mid-Air Gestural Interaction with Large Interactive Displays*, doctoral thesis, Tampere University, 2026. https://researchportal.tuni.fi/en/publications/mid-air-gestural-interaction-with-large-interactive-displays
13. Kim & Xiong. *Pseudo-Haptic Button for Improving User Experience of Mid-Air Interaction in VR*, 2021. https://arxiv.org/abs/2112.11007
14. *Towards a Consensus Gesture Set: A Survey of Mid-Air Gestures in HCI*, CHI 2023. https://dl.acm.org/doi/full/10.1145/3544548.3581420
15. Vuletic et al. *Systematic literature review of hand gestures used in human-computer interaction interfaces*, 2019. https://www.sciencedirect.com/science/article/pii/S1071581918305676
16. Lyu et al. *Objestures: Everyday Objects Meet Mid-Air Gestures*, CHI 2026. https://arxiv.org/abs/2503.02973
17. Ahlström & Hasan. *Acceptance Studies of Around-Device Gestures in Public Settings*, MobileHCI 2014. https://hci.cs.umanitoba.ca/assets/publication_files/MobileHCI_2014-Khalad-Social.PDF
18. *GaVe: A Webcam-Based Gaze Vending Interface Using One-Point Calibration*, 2023 (dwell thresholds, Midas touch). https://pmc.ncbi.nlm.nih.gov/articles/PMC10640920

**Applications**
19. Jacob et al. *Hand-gesture-based sterile interface for the operating room*, JAMIA 2013. https://pubmed.ncbi.nlm.nih.gov/23250787/
20. Wipfli et al. *Gesture-Controlled Image Management for Operating Room*, PLoS ONE 2016. https://pmc.ncbi.nlm.nih.gov/articles/PMC4833285/
21. *Evaluating Usability of a Touchless Image Viewer in the Operating Room*, 2020. https://pmc.ncbi.nlm.nih.gov/articles/PMC6989265/
22. *Touchless Interaction in Surgery*, Communications of the ACM, 2023. https://cacm.acm.org/research/touchless-interaction-in-surgery
23. Sucar et al. *Gesture Therapy: a vision-based system for upper extremity stroke rehabilitation*, 2010. https://pubmed.ncbi.nlm.nih.gov/21096856/
24. *VIGoROUS: multi-site randomized controlled trial of in-home upper-extremity therapy*, eClinicalMedicine, 2022. https://www.thelancet.com/journals/eclinm/article/PIIS2589-5370(21)00520-4/fulltext
25. Ultraleap. *TouchFree touchless interface guidance*. https://docs.ultraleap.com/TouchFree/touchless-interfaces/guidance.html
26. Digital Signage Today. *Touchless drives vending, kiosks, interactive signage*, 2025. https://www.digitalsignagetoday.com/articles/touchless-drives-vending-kiosks-interactive-signage

**Prior art / demos**
27. https://github.com/XianlinLu/air-canvas
28. https://github.com/charanuggala26/Virtual-Mouse
29. https://github.com/mvipin/gesturebot
30. https://github.com/aayush23206/Air-Canvas
