"""Gesture state machines.

The pinch FSM is the heart of the interaction engine. It is deliberately
conservative: two thresholds (hysteresis), frame-based debounce, a release
cooldown, click-vs-drag disambiguation, and double-click detection. It never
uses wall-clock time directly, so it can be replayed deterministically in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import PinchConfig
from .features import HandFeatures


class PinchEventKind(str, Enum):
    PRESS = "press"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    DRAG_START = "drag_start"
    DRAG_END = "drag_end"


@dataclass(frozen=True)
class PinchState:
    closed: bool
    dragging: bool
    events: tuple[PinchEventKind, ...]
    ratio: float
    position: tuple[float, float]
    press_duration_ms: float

    @property
    def clicked(self) -> bool:
        return PinchEventKind.CLICK in self.events

    @property
    def double_clicked(self) -> bool:
        return PinchEventKind.DOUBLE_CLICK in self.events


class PinchFSM:
    """Hysteretic pinch detector with drag and double-click semantics."""

    def __init__(self, config: PinchConfig | None = None) -> None:
        self.config = config or PinchConfig()
        self._closed = False
        self._dragging = False
        self._candidate = False
        self._candidate_frames = 0
        self._press_ts: float | None = None
        self._press_pos: tuple[float, float] | None = None
        self._last_click_release_ts: float | None = None
        self._double_click_candidate = False
        self._cooldown_until = 0.0

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def dragging(self) -> bool:
        return self._dragging

    def reset(self) -> None:
        """Return to the open state, e.g. when the hand is lost."""
        self._closed = False
        self._dragging = False
        self._candidate = False
        self._candidate_frames = 0
        self._press_ts = None
        self._press_pos = None
        self._last_click_release_ts = None
        self._double_click_candidate = False
        self._cooldown_until = 0.0

    def update(
        self,
        ratio: float,
        position: tuple[float, float],
        ts_ms: float,
    ) -> PinchState:
        events: list[PinchEventKind] = []

        if ts_ms >= self._cooldown_until:
            threshold = self.config.exit_ratio if self._closed else self.config.enter_ratio
            desired = ratio < threshold if self._closed else ratio <= threshold

            if desired == self._candidate:
                self._candidate_frames += 1
            else:
                self._candidate = desired
                self._candidate_frames = 1

            needed = (
                self.config.min_frames_closed if desired else self.config.min_frames_open
            )
            if desired != self._closed and self._candidate_frames >= needed:
                if desired:
                    events.extend(self._on_press(position, ts_ms))
                else:
                    events.extend(self._on_release(ts_ms))
                self._closed = desired

        # Drag detection only runs while the ratio itself still indicates a
        # closed pinch. Otherwise the midpoint between the fingertips jumps as
        # the fingers open, and the release debounce would read that jump as a
        # drag.
        still_closed = self._closed and ratio < self.config.exit_ratio
        if still_closed and not self._dragging and self._press_pos is not None:
            dx = position[0] - self._press_pos[0]
            dy = position[1] - self._press_pos[1]
            if (dx * dx + dy * dy) ** 0.5 > self.config.drag_move_px:
                self._dragging = True
                events.append(PinchEventKind.DRAG_START)

        press_duration = 0.0
        if self._press_ts is not None:
            press_duration = ts_ms - self._press_ts

        return PinchState(
            closed=self._closed,
            dragging=self._dragging,
            events=tuple(events),
            ratio=ratio,
            position=position,
            press_duration_ms=press_duration,
        )

    def _on_press(
        self, position: tuple[float, float], ts_ms: float
    ) -> list[PinchEventKind]:
        self._press_ts = ts_ms
        self._press_pos = position
        self._double_click_candidate = (
            self._last_click_release_ts is not None
            and ts_ms - self._last_click_release_ts <= self.config.double_click_ms
        )
        return [PinchEventKind.PRESS]

    def _on_release(self, ts_ms: float) -> list[PinchEventKind]:
        events: list[PinchEventKind] = []
        if self._dragging:
            events.append(PinchEventKind.DRAG_END)
            self._last_click_release_ts = None
            self._double_click_candidate = False
        elif self._double_click_candidate:
            events.append(PinchEventKind.DOUBLE_CLICK)
            self._last_click_release_ts = None
            self._double_click_candidate = False
        else:
            events.append(PinchEventKind.CLICK)
            self._last_click_release_ts = ts_ms

        self._dragging = False
        self._press_ts = None
        self._press_pos = None
        self._cooldown_until = ts_ms + self.config.cooldown_ms
        return events



def is_idle_pose(
    features: HandFeatures,
    speed: float,
    speed_threshold: float = 1.2,
    pinch_ratio_threshold: float = 0.8,
) -> bool:
    """Open, relaxed palm held still — the explicit idle/pause pose that guards
    against accidental input (the Midas touch problem, PLAN.md 3.3).

    A pinching hand can have four extended fingers, so an open-palm test alone
    is not enough: the thumb-to-index distance must also be clearly open.
    """
    return (
        features.open_palm
        and features.pinch_ratio > pinch_ratio_threshold
        and speed < speed_threshold
    )
