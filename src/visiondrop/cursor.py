"""Pointer mapping and cursor state.

Maps the fingertip from the camera frame onto the screen through a configurable
active box and control-display gain, smooths with a One Euro filter, and
supports freezing the pointer while a click is emitted (the cursor must not
drift during selection).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import CursorConfig, FilterConfig
from .filters import OneEuroFilter2D, VelocityTracker


@dataclass
class Cursor:
    screen_size: tuple[int, int] = (1920, 1080)
    config: CursorConfig = field(default_factory=CursorConfig)
    filter_config: FilterConfig = field(default_factory=FilterConfig)

    _filter: OneEuroFilter2D = field(init=False, repr=False)
    _velocity: VelocityTracker = field(init=False, repr=False)
    _pos: tuple[float, float] = field(init=False, repr=False)
    _frozen_until_ms: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._filter = OneEuroFilter2D(
            min_cutoff=self.filter_config.min_cutoff,
            beta=self.filter_config.beta,
            d_cutoff=self.filter_config.d_cutoff,
        )
        self._velocity = VelocityTracker()
        self._pos = (self.screen_size[0] / 2.0, self.screen_size[1] / 2.0)
        self._frozen_until_ms = 0.0

    @property
    def position(self) -> tuple[int, int]:
        return (int(round(self._pos[0])), int(round(self._pos[1])))

    @property
    def float_position(self) -> tuple[float, float]:
        return self._pos

    @property
    def area_radius(self) -> float:
        return self.config.area_radius_px

    @property
    def speed(self) -> float:
        return self._velocity.speed

    def reset(self) -> None:
        self._filter.reset()
        self._velocity.reset()
        self._pos = (self.screen_size[0] / 2.0, self.screen_size[1] / 2.0)
        self._frozen_until_ms = 0.0

    def freeze(self, ts_ms: float, duration_ms: float | None = None) -> None:
        duration = self.config.click_freeze_ms if duration_ms is None else duration_ms
        self._frozen_until_ms = max(self._frozen_until_ms, ts_ms + duration)

    def unfreeze(self) -> None:
        self._frozen_until_ms = 0.0

    def is_frozen(self, ts_ms: float) -> bool:
        return ts_ms < self._frozen_until_ms

    def map_to_screen(self, norm_pos: tuple[float, float]) -> tuple[float, float]:
        """Map frame-normalized coordinates (0..1) onto screen pixels."""
        cfg = self.config
        x = min(max(norm_pos[0], cfg.active_box_left), cfg.active_box_right)
        y = min(max(norm_pos[1], cfg.active_box_top), cfg.active_box_bottom)

        x = (x - cfg.active_box_left) / (cfg.active_box_right - cfg.active_box_left)
        y = (y - cfg.active_box_top) / (cfg.active_box_bottom - cfg.active_box_top)

        x = 0.5 + (x - 0.5) * cfg.gain
        y = 0.5 + (y - 0.5) * cfg.gain

        x = min(max(x, 0.0), 1.0)
        y = min(max(y, 0.0), 1.0)

        return (x * self.screen_size[0], y * self.screen_size[1])

    def update(self, norm_pos: tuple[float, float], ts_s: float, ts_ms: float) -> tuple[int, int]:
        target = self.map_to_screen(norm_pos)
        smoothed = self._filter(target, ts_s)
        self._velocity(smoothed, ts_s)

        if not self.is_frozen(ts_ms):
            self._pos = smoothed
        return self.position
