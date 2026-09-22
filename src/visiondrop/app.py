"""Command-line entry points for VisionDrop.

    visiondrop run        live engine (headless); optional debug window/recording
    visiondrop replay     re-run the engine over a recorded landmark stream
    visiondrop info       print environment and permission checklist
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from . import __version__
from . import config as _config
from .capture import CameraCapture
from .engine import Engine, primary_screen_size
from .gestures import PinchEventKind
from .telemetry import FPSCounter, JsonlRecorder, LatencyMeter, load_recording


def _format_events(events: tuple[PinchEventKind, ...], cursor: tuple[int, int]) -> str:
    parts = []
    for event in events:
        if event in (PinchEventKind.CLICK, PinchEventKind.DOUBLE_CLICK):
            parts.append(f"{event.value}@({cursor[0]},{cursor[1]})")
        else:
            parts.append(event.value)
    return ", ".join(parts)


def _run(args: argparse.Namespace) -> int:
    cfg = _config.DEFAULT_CONFIG
    recorder = JsonlRecorder(args.record) if args.record else None
    recorder_ctx = recorder if recorder else _NullContext()

    try:
        with CameraCapture(config=cfg) as camera, recorder_ctx:
            frame = camera.read()[0]
            assert frame is not None and camera.actual_size is not None
            aspect = camera.actual_size[0] / camera.actual_size[1]

            from .tracking import HandTracker

            tracker = HandTracker(cfg)
            engine = Engine(cfg, frame_aspect=aspect)
            fps = FPSCounter()
            latency = LatencyMeter()
            last_timestamp = 0.0
            last_report = time.monotonic()

            print(
                f"VisionDrop {__version__} running: camera={cfg.camera_index} "
                f"size={camera.actual_size[0]}x{camera.actual_size[1]} "
                f"screen={primary_screen_size()[0]}x{primary_screen_size()[1]}"
            )
            print("Point with your index finger. Pinch thumb+index to click/drag. Ctrl+C to stop.")

            while True:
                frame, timestamp = camera.read()
                if frame is None or timestamp == last_timestamp:
                    time.sleep(0.002)
                    continue
                last_timestamp = timestamp

                started = time.perf_counter()
                observation = tracker.process(frame, timestamp)
                state = engine.process(observation)
                latency.record((time.perf_counter() - started) * 1000.0)
                fps.tick(timestamp)

                if recorder is not None:
                    recorder.write(observation)

                if state.events:
                    print(f"[{state.timestamp_s:8.3f}] {_format_events(state.events, state.cursor)}")

                if args.debug_window:
                    import cv2

                    tracker.draw(frame, observation)
                    _draw_hud(cv2, frame, state, fps.tick(timestamp), latency)
                    cv2.imshow("VisionDrop (debug)", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                if time.monotonic() - last_report >= args.report_interval:
                    last_report = time.monotonic()
                    stats = latency.stats()
                    print(
                        f"    fps={fps.tick(timestamp):5.1f} "
                        f"latency={stats.mean_ms:5.1f}ms(p95 {stats.p95_ms:5.1f}) "
                        f"hand={'yes' if state.hand_present else 'no '} "
                        f"pinch={'closed' if state.pinch and state.pinch.closed else 'open  '} "
                        f"cursor={state.cursor}"
                    )
    except KeyboardInterrupt:
        print("\nStopping.")
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        try:
            import cv2

            cv2.destroyAllWindows()
        except Exception:
            pass
    return 0


def _draw_hud(cv2, frame, state, current_fps: float, latency: LatencyMeter) -> None:
    height, width = frame.shape[:2]
    lines = [
        f"fps {current_fps:4.1f}",
        f"lat {latency.stats().mean_ms:4.1f}ms",
        f"pinch {state.pinch.ratio:.2f}" if state.pinch else "pinch --",
        "IDLE" if state.idle else ("ACTIVE" if state.active else "waiting"),
    ]
    for index, text in enumerate(lines):
        cv2.putText(
            frame,
            text,
            (12, 28 + index * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )


class _NullContext:
    def __enter__(self) -> "_NullContext":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _replay(args: argparse.Namespace) -> int:
    observations = load_recording(args.path)
    if not observations:
        print(f"error: no frames in {args.path}", file=sys.stderr)
        return 2

    engine = Engine(_config.DEFAULT_CONFIG, frame_aspect=args.aspect)
    counts: dict[str, int] = {}
    for observation in observations:
        state = engine.process(observation)
        for event in state.events:
            counts[event.value] = counts.get(event.value, 0) + 1
            if args.verbose:
                print(
                    f"[{state.timestamp_s:8.3f}] {event.value} "
                    f"cursor={state.cursor} ratio={state.pinch.ratio if state.pinch else 0:.3f}"
                )

    print(f"replayed {len(observations)} frames from {args.path}")
    for name, count in sorted(counts.items()):
        print(f"  {name}: {count}")
    return 0


def _info(_: argparse.Namespace) -> int:
    print(f"visiondrop {__version__}")
    print(f"screen: {primary_screen_size()[0]}x{primary_screen_size()[1]}")
    print(f"camera index: {_config.DEFAULT_CONFIG.camera_index}")
    print("\nPermissions required (macOS):")
    print("  Camera            - hand tracking")
    print("  Accessibility     - injecting clicks/keys (Phase 3)")
    print("  Screen Recording  - magnifier and OCR (Phase 5)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="visiondrop", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="run the live interaction engine")
    run.add_argument("--record", type=Path, default=None, help="write landmark stream to JSONL")
    run.add_argument("--debug-window", action="store_true", help="show skeleton window (off by default)")
    run.add_argument("--report-interval", type=float, default=5.0, help="seconds between status lines")
    run.set_defaults(func=_run)

    replay = subparsers.add_parser("replay", help="replay a recorded landmark stream")
    replay.add_argument("path", type=Path)
    replay.add_argument("--aspect", type=float, default=16 / 9)
    replay.add_argument("--verbose", action="store_true")
    replay.set_defaults(func=_replay)

    info = subparsers.add_parser("info", help="print environment and permission checklist")
    info.set_defaults(func=_info)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1

    signal.signal(signal.SIGINT, signal.default_int_handler)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
