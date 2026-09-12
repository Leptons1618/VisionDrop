"""Mid-air drag-and-drop interaction state machine.

States: IDLE -> HOVER -> DRAG, driven either by pinching (default) or by
dwelling over an object (accessibility / study condition). Grab and release
are debounced and use separate thresholds, and association loss during a drag
is tolerated (occlusion) until the hand itself disappears for too long.

Dwell mode: hold the cursor over an object for ``dwell_s`` to grab; hold it
away from the grab point (beyond ``dwell_exit_px``) for ``dwell_s`` to drop.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum

from visiondrop.association import Association
from visiondrop.config import InteractionConfig
from visiondrop.filters import PointFilter
from visiondrop.hands import Hand

Point = tuple[float, float]


class State(Enum):
    IDLE = "IDLE"
    HOVER = "HOVER"
    DRAG = "DRAG"


@dataclass(frozen=True)
class InteractionResult:
    state: State
    event: str | None = None  # "grabbed" | "dropped" | "cancelled"
    cursor: Point | None = None
    held_object: dict | None = None
    dropped_object: dict | None = None


class InteractionEngine:
    def __init__(self, config: InteractionConfig | None = None):
        self.config = config or InteractionConfig()
        self.state = State.IDLE
        self._cursor = PointFilter(self.config.filter_min_cutoff, self.config.filter_beta)
        self._last_cursor: Point | None = None
        self._held: dict | None = None
        self._pinch_streak = 0
        self._release_streak = 0
        self._missing = 0
        self._cooldown = 0
        self._hover_started: float | None = None
        self._drop_dwell_started: float | None = None
        self._grab_cursor: Point | None = None

    def update(
        self,
        hand: Hand | None,
        association: Association | None,
        timestamp: float | None = None,
    ) -> InteractionResult:
        timestamp = time.perf_counter() if timestamp is None else timestamp
        if hand is None:
            return self._handle_missing_hand()

        self._missing = 0
        self._last_cursor = self._cursor.filter(hand.pinch_point, timestamp)
        if self._cooldown > 0:
            self._cooldown -= 1

        closed = hand.pinch_ratio <= self.config.grab_ratio
        opened = hand.pinch_ratio >= self.config.release_ratio

        if self.state is State.DRAG:
            return self._update_dragging(association, opened, timestamp)
        return self._update_not_dragging(association, closed, timestamp)

    def _update_not_dragging(
        self, association: Association | None, closed: bool, timestamp: float
    ) -> InteractionResult:
        if association is None:
            self.state = State.IDLE
            self._pinch_streak = 0
            self._hover_started = None
            return self._result(None)

        self.state = State.HOVER
        if self.config.grab_mode == "dwell":
            if self._cooldown > 0:
                self._hover_started = None
            elif self._hover_started is None:
                self._hover_started = timestamp
            elif timestamp - self._hover_started >= self.config.dwell_s:
                return self._start_drag(association)
            return self._result(None)

        self._pinch_streak = self._pinch_streak + 1 if closed else 0
        if self._pinch_streak >= self.config.debounce_frames and self._cooldown == 0:
            return self._start_drag(association)
        return self._result(None)

    def _start_drag(self, association: Association) -> InteractionResult:
        self.state = State.DRAG
        self._held = association.detection
        self._pinch_streak = 0
        self._release_streak = 0
        self._hover_started = None
        self._drop_dwell_started = None
        self._grab_cursor = self._last_cursor
        return self._result("grabbed")

    def _update_dragging(
        self, association: Association | None, opened: bool, timestamp: float
    ) -> InteractionResult:
        if association is not None:
            self._held = association.detection

        if self.config.grab_mode == "dwell":
            if self._last_cursor is not None and self._grab_cursor is not None:
                distance = math.hypot(
                    self._last_cursor[0] - self._grab_cursor[0],
                    self._last_cursor[1] - self._grab_cursor[1],
                )
                if distance < self.config.dwell_exit_px:
                    self._drop_dwell_started = None
                elif self._drop_dwell_started is None:
                    self._drop_dwell_started = timestamp
                elif timestamp - self._drop_dwell_started >= self.config.dwell_s:
                    return self._do_drop(association)
            return self._result(None)

        self._release_streak = self._release_streak + 1 if opened else 0
        if self._release_streak >= self.config.debounce_frames:
            return self._do_drop(association)
        return self._result(None)

    def _do_drop(self, association: Association | None) -> InteractionResult:
        dropped = self._held
        self._held = None
        self._release_streak = 0
        self._pinch_streak = 0
        self._hover_started = None
        self._drop_dwell_started = None
        self._grab_cursor = None
        self._cooldown = self.config.cooldown_frames
        self.state = State.HOVER if association is not None else State.IDLE
        return self._result("dropped", dropped=dropped)

    def _handle_missing_hand(self) -> InteractionResult:
        self._missing += 1
        if self.state is State.DRAG:
            self._drop_dwell_started = None
            if self._missing <= self.config.lost_tolerance_frames:
                return self._result(None)
            held = self._held
            self._held = None
            self._grab_cursor = None
            self.state = State.IDLE
            return self._result("cancelled", dropped=held)

        self._cursor.reset()
        self._pinch_streak = 0
        self._hover_started = None
        self.state = State.IDLE
        return self._result(None)

    def _result(self, event: str | None, dropped: dict | None = None) -> InteractionResult:
        return InteractionResult(
            state=self.state,
            event=event,
            cursor=self._last_cursor,
            held_object=self._held,
            dropped_object=dropped,
        )
