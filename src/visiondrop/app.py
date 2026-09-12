"""VisionDrop application entry point."""

from __future__ import annotations

import argparse
import logging
import signal
import time
from collections import deque

import cv2
import numpy as np

from visiondrop.association import associate_hands
from visiondrop.config import AppConfig, find_zone, is_in_any_zone
from visiondrop.feedback import Feedback
from visiondrop.hands import HandTracker, draw_hands
from visiondrop.interaction import InteractionEngine, State
from visiondrop.logging_config import setup_logging
from visiondrop.objects import ColorObjectDetector, create_object_detector, draw_detections
from visiondrop.session import SessionRecorder

logger = logging.getLogger(__name__)


class RollingStats:
    """Small rolling window for p50/p95 latency readouts."""

    def __init__(self, window: int = 60):
        self._values: deque[float] = deque(maxlen=window)

    def add(self, value: float) -> None:
        self._values.append(value)

    def percentile(self, q: float) -> float:
        if not self._values:
            return 0.0
        return float(np.percentile(self._values, q))

    @property
    def latest(self) -> float:
        return self._values[-1] if self._values else 0.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="visiondrop",
        description="Webcam-based mid-air drag-and-drop.",
    )
    parser.add_argument("--source", default="0", help="Camera index or video file path (default: 0)")
    parser.add_argument("--model-dir", default=None, help="Directory for model weights")
    parser.add_argument("--width", type=int, default=None, help="Capture width override")
    parser.add_argument("--height", type=int, default=None, help="Capture height override")
    parser.add_argument(
        "--detector", choices=("yolo", "color"), default="yolo",
        help="Object detector backend (default: yolo, falls back to color)",
    )
    parser.add_argument(
        "--classes", default=None,
        help="Comma-separated COCO class allowlist, e.g. cup,bottle,cell phone",
    )
    parser.add_argument("--imgsz", type=int, default=None, help="Detector inference size (default: 640)")
    parser.add_argument(
        "--condition", choices=("pinch", "dwell"), default="pinch",
        help="Grab condition: pinch or dwell (study use, default: pinch)",
    )
    parser.add_argument("--log", default=None, help="Write a JSONL session log to this path")
    parser.add_argument("--no-objects", action="store_true", help="Disable object detection")
    parser.add_argument("--debug", action="store_true", help="Show latency percentiles in the HUD")
    parser.add_argument("--log-level", default="INFO", help="Log level (default: INFO)")
    return parser.parse_args(argv)


def parse_source(value: str) -> int | str:
    """Interpret a CLI source as a camera index when numeric."""
    return int(value) if value.isdigit() else value


def parse_classes(value: str | None) -> tuple[str, ...] | None:
    if not value:
        return None
    classes = tuple(name.strip() for name in value.split(",") if name.strip())
    return classes or None


def open_capture(source: int | str, width: int, height: int) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(source)
    if isinstance(source, int):
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return capture


def build_detector(config: AppConfig):
    """Create the configured detector, falling back to color detection."""
    try:
        return create_object_detector(
            config.detector, config.yolo, config.color, model_dir=config.model_dir
        )
    except ImportError as exc:
        logger.warning("YOLO detector unavailable (%s); falling back to color detection", exc)
        return ColorObjectDetector(config.color)


def draw_hud(frame, lines, origin=(10, 30), line_height=28) -> None:
    x, y = origin
    for text, color in lines:
        cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        y += line_height


def run(config: AppConfig, show_objects: bool = True, debug: bool = False) -> int:
    capture = open_capture(config.source, config.frame_width, config.frame_height)
    if not capture.isOpened():
        logger.error("Could not open video source %r", config.source)
        return 1

    detector = build_detector(config) if show_objects else None
    engine = InteractionEngine(config.interaction)
    feedback = Feedback()
    recorder = SessionRecorder(config.log_path)
    if recorder.enabled:
        logger.info("Session log: %s", recorder.path)
        recorder.event(0, 0.0, "session_start", condition=config.interaction.grab_mode)
    score = 0
    misses = 0
    frame_index = 0
    is_file = not isinstance(config.source, int)
    video_fps = float(capture.get(cv2.CAP_PROP_FPS)) if is_file else 0.0
    if not 0 < video_fps <= 240:
        video_fps = 30.0
    hand_stats = RollingStats()
    detect_stats = RollingStats()
    fps = 0.0
    last_frame_time = time.perf_counter()

    try:
        with HandTracker(config.hand, model_dir=config.model_dir) as tracker:
            logger.info("Running. Press 'q' to quit.")
            while True:
                ok, frame = capture.read()
                if not ok:
                    logger.info("Video source ended")
                    break

                frame = cv2.flip(frame, 1)
                # File sources use video time so replay is deterministic.
                frame_time = frame_index / video_fps if is_file else time.perf_counter()
                timestamp_ms = int(frame_time * 1000)

                started = time.perf_counter()
                hands = tracker.process(frame, timestamp_ms)
                hand_ms = (time.perf_counter() - started) * 1000
                hand_stats.add(hand_ms)

                detections = []
                detect_ms = 0.0
                if detector is not None:
                    started = time.perf_counter()
                    detections = detector.detect_objects(frame)
                    detect_ms = (time.perf_counter() - started) * 1000
                    detect_stats.add(detect_ms)

                associations = associate_hands(
                    hands,
                    detections,
                    radius_ratio=config.grab_radius_ratio,
                    min_radius=config.min_grab_radius,
                )
                associated_hand_indexes = {association.hand_index for association in associations}

                primary_association = next(
                    (a for a in associations if a.hand_index == 0), None
                )
                interaction = engine.update(
                    hands[0] if hands else None, primary_association, frame_time
                )
                if interaction.event == "grabbed":
                    held = interaction.held_object or {}
                    logger.info("Interaction: grabbed")
                    recorder.event(
                        frame_index, frame_time, "grabbed",
                        object_type=held.get("type"), track_id=held.get("track_id"),
                    )
                    feedback.play("grab")
                    feedback.flash(hands[0].pinch_point, config.colors["white"], frame_time)
                elif interaction.event == "cancelled":
                    logger.info("Interaction: cancelled")
                    recorder.event(frame_index, frame_time, "cancelled")
                    feedback.play("miss")
                elif interaction.event == "dropped":
                    dropped = interaction.dropped_object
                    if dropped is not None:
                        zone = find_zone(dropped["center"], config.drop_zones)
                        if zone is not None:
                            logger.info("Interaction: dropped in zone %s", zone.label)
                            score += 1
                            feedback.mark_onboarded()
                            feedback.play("success")
                            feedback.flash(dropped["center"], config.colors["green"], frame_time)
                            recorder.event(
                                frame_index, frame_time, "dropped",
                                object_type=dropped.get("type"), track_id=dropped.get("track_id"),
                                zone=zone.label,
                            )
                        else:
                            logger.info("Interaction: dropped outside zones")
                            misses += 1
                            feedback.play("miss")
                            feedback.flash(dropped["center"], config.colors["red"], frame_time)
                            recorder.event(
                                frame_index, frame_time, "dropped",
                                object_type=dropped.get("type"), track_id=dropped.get("track_id"),
                            )

                recorder.frame(
                    frame_index, frame_time, interaction.state.value, interaction.cursor,
                    len(hands), len(detections), len(associations),
                    hand_ms, detect_ms, fps,
                )
                frame_index += 1

                for zone in config.drop_zones:
                    cv2.rectangle(
                        frame, (zone.x1, zone.y1), (zone.x2, zone.y2), config.colors["blue"], 2
                    )
                    cv2.putText(
                        frame,
                        zone.label,
                        (zone.x1 + 8, zone.y1 + 28),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        config.colors["blue"],
                        2,
                    )

                if detector is not None:
                    draw_detections(frame, detections)

                for association in associations:
                    hand = hands[association.hand_index]
                    x, y, w, h = association.detection["bbox"]
                    cv2.line(
                        frame,
                        hand.pinch_point,
                        (x + w // 2, y + h // 2),
                        config.colors["green"],
                        2,
                    )
                    protruding = association.hand_index == 0 and interaction.state is State.HOVER
                    pad = 4 if protruding else 0
                    cv2.rectangle(
                        frame,
                        (x - pad, y - pad),
                        (x + w + pad, y + h + pad),
                        config.colors["green"],
                        3,
                    )

                if interaction.held_object is not None:
                    x, y, w, h = interaction.held_object["bbox"]
                    cv2.rectangle(frame, (x, y), (x + w, y + h), config.colors["yellow"], 3)
                    cv2.putText(
                        frame, "HELD", (x, max(y - 10, 18)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, config.colors["yellow"], 2,
                    )

                draw_hands(frame, hands)
                for hand_index, hand in enumerate(hands):
                    inside = is_in_any_zone(hand.pinch_point, config.drop_zones)
                    associated = hand_index in associated_hand_indexes
                    color = config.colors["green"] if inside else config.colors["red"]
                    radius = 14 if associated else (12 if inside else 6)
                    cv2.circle(frame, hand.pinch_point, radius, color, 2)

                now = time.perf_counter()
                delta = now - last_frame_time
                last_frame_time = now
                if delta > 0:
                    instant = 1.0 / delta
                    fps = instant if fps == 0 else 0.9 * fps + 0.1 * instant

                hud = [
                    (f"{fps:5.1f} FPS", config.colors["yellow"]),
                    (f"Score {score}  Misses {misses}", config.colors["white"]),
                ]
                if debug:
                    hud.append(
                        (f"hands  p50 {hand_stats.percentile(50):4.1f}  p95 {hand_stats.percentile(95):4.1f} ms",
                         config.colors["white"])
                    )
                    hud.append(
                        (f"detect p50 {detect_stats.percentile(50):4.1f}  p95 {detect_stats.percentile(95):4.1f} ms",
                         config.colors["white"])
                    )
                    hud.append(
                        (f"objects {len(detections)}  linked {len(associations)}",
                         config.colors["white"])
                    )
                    hud.append((f"state {interaction.state.value}", config.colors["white"]))
                draw_hud(frame, hud)

                cv2.putText(
                    frame, "Press 'q' to quit", (10, frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, config.colors["red"], 1,
                )

                feedback.draw_flashes(frame, frame_time)
                feedback.draw_onboarding(frame, frame_time)

                cv2.imshow("VisionDrop", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("Quit command received")
                    break
    finally:
        capture.release()
        recorder.close()
        cv2.destroyAllWindows()

    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(getattr(logging, args.log_level.upper(), logging.INFO))

    config = AppConfig(
        source=parse_source(args.source),
        model_dir=args.model_dir,
        log_path=args.log,
        detector=args.detector,
    )
    if args.width:
        config.frame_width = args.width
    if args.height:
        config.frame_height = args.height
    if args.imgsz:
        config.yolo.image_size = args.imgsz
    config.yolo.classes = parse_classes(args.classes)
    config.interaction.grab_mode = args.condition

    signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        return run(config, show_objects=not args.no_objects, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down")
        cv2.destroyAllWindows()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
