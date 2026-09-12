# VisionDrop User Study Protocol

Status: ready for data collection (pending the mouse-baseline instrument).
Scope: M5 of [CASE_STUDY.md](CASE_STUDY.md). This file defines exactly how to
run the evaluation; results go in a separate `RESULTS.md` when collected.

## 1. Research questions

- **RQ1 (interaction):** Does pinch-grab outperform dwell-grab for task
  throughput and accuracy in real-object sorting?
- **RQ2 (filtering):** Does the 1€ filter improve cursor smoothness without
  degrading completion time? (planned follow-up sub-study, see §10)
- **RQ3 (feedback):** Do audio + pseudo-haptic cues reduce invalid drops and
  improve subjective ratings? (compare against the color-only build or run
  conditions with `--no-audio`; not part of the main three conditions)

## 2. Design

Within-subject, three conditions, order counterbalanced with a Latin square:

| # | Condition | How | Command |
|---|-----------|-----|---------|
| 1 | Pinch | Pinch to grab, open hand to release | `--condition pinch` |
| 2 | Dwell | Hover 0.5 s to grab; move > 80 px; dwell 0.5 s to release | `--condition dwell` |
| 3 | Mouse baseline | Drag mirrored on-screen boxes on a frozen snapshot | pending §10 |

**Task:** sort 12 objects into 2 labeled zones (e.g. "fruit" vs "packaging").
One repetition = all 12 objects moved. Three repetitions per condition,
objects returned to start positions between repetitions. Participants are told:
"Move each object to its zone as quickly and accurately as you can."

Dwell parameters are calibration knobs (`InteractionConfig.dwell_s`,
`dwell_exit_px`); keep them fixed at 0.5 s / 80 px for all participants, and
record deviations.

## 3. Participants

- n = 12–15, naive to VisionDrop.
- Inclusion: able to stand/sit in front of a webcam for ~30 min, move one hand
  freely, comfortable with light physical exercise.
- Dwell condition exists specifically for users who cannot pinch reliably;
  do not exclude for reduced pinch strength.
- Consent: purpose, ~30 min duration, camera feed is processed locally and not
  stored; session logs contain cursor positions and events only, no video;
  right to withdraw at any time; pseudonymous participant IDs (P01, P02, ...).
- Collect: age band, handedness, prior experience with gesture interfaces
  (0–5), whether they wear glasses/contacts.

## 4. Setup checklist

- Camera at chest height, 1.5–2 m away, index passed via `--source`.
- Even lighting (>300 lux), no backlighting; plain background if possible.
- Screen ≥ 720p, zones large and reachable without leaning.
- Objects: 12 COCO-detectable items, e.g. 3 cups, 3 apples/oranges,
  3 bottles, 3 boxes/books. Keep colors varied to avoid relying on YOLO only
  recognizing one object.
- Launch with the class allowlist for speed:

```bash
python -m visiondrop \
  --condition pinch \
  --classes cup,bottle,apple,orange,banana,book,cell phone,scissors \
  --log logs/P01_pinch_rep1.jsonl
```

- Name logs `logs/<participant>_<condition>_rep<N>.jsonl`. The condition is
  also written into the log as a `session_start` event, so files can be
  cross-checked.

## 5. Procedure

1. Consent + demographics (~5 min).
2. Introduction, show the zones, 1 minute free exploration.
3. Practice: 2–3 drops per condition until the participant says the mechanic
   is understood (never coach during measured trials).
4. For each condition in the assigned order:
   a. Start the app with the condition's command.
   b. Measured run: 12 objects sorted; repeat 3 times with reset pauses.
   c. Questionnaires after the condition: SUS (10 items), NASA-TLX (6
      subscales), and "Would you use this again? (1–5)".
5. Debrief: rank the three conditions, free comments, ask permission for the
   demo recording.

The onboarding overlay disappears after the first successful drop; treat that
moment as the end of the practice phase, not as measured data.

## 6. Metrics

Automatic (from JSONL, per condition and repetition):

| Metric | Source |
|---|---|
| Completion time | `duration_s` of the repetition log |
| Grabs / drops / scored / cancelled | event counts |
| Grab success rate | `drops / grabs` |
| Drop accuracy | `scored / drops` |
| Carry time | `carry_median_s` |
| Occlusion robustness | `occlusion_rate` of drag frames |
| Latency | `hand_p50/p95_ms`, `detect_p50/p95_ms` |

Subjective: SUS score (0–100), NASA-TLX (0–100), preference ranking.
Safety proxy: unintended grabs per minute during the reset pauses (read from
the log frames between measured trials).

## 7. Analysis plan

- Per-participant means per condition; paired comparisons with Wilcoxon
  signed-rank (non-normal, small n), Holm correction across the two primary
  contrasts (pinch vs dwell, visionDrop vs mouse).
- Effect size: matched-pairs rank-biserial correlation; report medians and IQR.
- SUS scoring: for each odd item subtract 1, for each even item subtract from
  5; sum and multiply by 2.5.
- Report all conditions honestly, including where the mouse wins.
- Reproduce each session's interaction metrics with:

```bash
python scripts/analyze_session.py logs/P01_pinch_rep1.jsonl
```

## 8. Ethical and practical notes

- No video or images are stored by the app; only JSONL event data.
- Participant can stop at any time; arm fatigue is the main discomfort —
  offer breaks between conditions.
- Do not record faces in the demo video; crop to hands and screen.

## 9. Demo video storyboard (~45 s)

1. 0:00 Hook: real cup pinched in mid-air, HELD box follows the hand.
2. 0:10 Carry across the screen into zone A, release; chime, flash, score.
3. 0:20 Cut: dwell condition — hover, grab, dwell to drop.
4. 0:30 Occlusion: hand passes over the object; the hold survives.
5. 0:38 End card: repo link, study protocol link, "results pending".

## 10. Pending instruments

- **Mouse baseline (≈1 h):** a script that freezes a camera snapshot, runs the
  detector once, and lets the mouse drag the mirrored boxes through the same
  zones and logger. Build before data collection; it is not required for RQ1
  (pinch vs dwell) but is part of the three-condition comparison.
- **Results write-up:** fill `docs/RESULTS.md` after data collection with the
  tables from §6/§7, plots from `analyze_session.py`, and the limitations
  section.
