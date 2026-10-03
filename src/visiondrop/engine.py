"""The interaction engine: landmarks in, cursor + gesture state out.

This module is UI-free and platform-free on purpose. The live app, the debug
HUD, and the replay tests all drive the same ``Engine.process``.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from dataclasses import dataclass

from . import config as _config
from .cursor import Cursor
from .features import HandFeatures
from .filters import VelocityTracker
from .gestures import PinchEventKind, PinchFSM, PinchState, is_idle_pose
from .tracking import FrameObservation


FALLBACK_SCREEN_SIZE = (1920, 1080)


def primary_screen_size() -> tuple[int, int]:
    """Primary screen size in pixels, falling back to 1920x1080 when unavailable.

    macOS asks Quartz (needs the ``macos`` extra), Windows asks user32, and
    everything else asks ``xrandr``, which covers X11 and XWayland sessions.
    """
    try:
        if sys.platform == "darwin":
            import Quartz

            display = Quartz.CGMainDisplayID()
            size = (int(Quartz.CGDisplayPixelsWide(display)), int(Quartz.CGDisplayPixelsHigh(display)))
        elif sys.platform == "win32":
            import ctypes

            user32 = ctypes.windll.user32
            size = (int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1)))
        else:
            result = subprocess.run(
                ["xrandr", "--current"], capture_output=True, text=True, timeout=2, check=True
            )
            size = parse_xrandr(result.stdout)
    except Exception:
        return FALLBACK_SCREEN_SIZE
    if size is None or size[0] <= 0 or size[1] <= 0:
        return FALLBACK_SCREEN_SIZE
    return size


_XRANDR_OUTPUT = re.compile(r"^\S+ connected (primary )?.*?(\d+)x(\d+)\+\d+\+\d+", re.MULTILINE)


def parse_xrandr(text: str) -> tuple[int, int] | None:
    """The primary output's size from ``xrandr`` output, else the first active one."""
    outputs = [(bool(m.group(1)), (int(m.group(2)), int(m.group(3)))) for m in _XRANDR_OUTPUT.finditer(text)]
    for primary, size in outputs:
        if primary:
            return size
    return outputs[0][1] if outputs else None


@dataclass(frozen=True)
class EngineState:
    timestamp_s: float
    hand_present: bool
    active: bool
    idle: bool
    features: HandFeatures | None
    pinch: PinchState | None
    cursor: tuple[int, int]
    velocity: float

    @property
    def events(self) -> tuple[PinchEventKind, ...]:
        return self.pinch.events if self.pinch else ()


class Engine:
    def __init__(
        self,
        config: _config.EngineConfig | None = None,
        screen_size: tuple[int, int] | None = None,
        frame_aspect: float = 16 / 9,
    ) -> None:
        self.config = config or _config.DEFAULT_CONFIG
        self.frame_aspect = frame_aspect
        self.cursor = Cursor(
            screen_size=screen_size or primary_screen_size(),
            config=self.config.cursor,
            filter_config=self.config.filters,
        )
        self.pinch = PinchFSM(self.config.pinch)
        self._velocity = VelocityTracker()

    def reset(self) -> None:
        self.pinch.reset()
        self.cursor.reset()
        self._velocity.reset()

    def process(self, observation: FrameObservation) -> EngineState:
        ts_s = observation.timestamp_s
        ts_ms = ts_s * 1000.0

        if not observation.hands:
            self.pinch.reset()
            self._velocity.reset()
            return EngineState(
                timestamp_s=ts_s,
                hand_present=False,
                active=False,
                idle=True,
                features=None,
                pinch=None,
                cursor=self.cursor.position,
                velocity=0.0,
            )

        hand = max(observation.hands, key=lambda item: item.score)
        features = HandFeatures.from_landmarks(hand.landmarks, aspect=self.frame_aspect)
        speed = self._velocity(features.pinch_point, ts_s)
        idle = is_idle_pose(features, speed)
        if idle:
            self.pinch.reset()
            return EngineState(
                timestamp_s=ts_s,
                hand_present=True,
                active=False,
                idle=True,
                features=features,
                pinch=None,
                cursor=self.cursor.position,
                velocity=speed,
            )

        ratio = features.pinch_ratio
        screen_pos = self.cursor.map_to_screen(features.pinch_point)
        pinch = self.pinch.update(ratio, screen_pos, ts_ms)

        active = features.pointing or pinch.closed
        if active:
            cursor_pos = self.cursor.update(features.pinch_point, ts_s, ts_ms)
        else:
            cursor_pos = self.cursor.position

        for event in pinch.events:
            if event is PinchEventKind.PRESS:
                self.cursor.freeze(ts_ms)
            elif event is PinchEventKind.DRAG_START:
                self.cursor.unfreeze()
            elif event in (PinchEventKind.CLICK, PinchEventKind.DOUBLE_CLICK):
                self.cursor.freeze(ts_ms)

        return EngineState(
            timestamp_s=ts_s,
            hand_present=True,
            active=active,
            idle=idle,
            features=features,
            pinch=pinch,
            cursor=cursor_pos,
            velocity=speed,
        )
