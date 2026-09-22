"""Tunable constants for the interaction engine.

All spatial thresholds are expressed as ratios (multiples of hand size) rather
than pixels so that they are invariant to camera distance and hand size, per
the findings in PLAN.md section 3.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PinchConfig:
    """Hysteresis thresholds and debounce timings for pinch detection."""

    enter_ratio: float = 0.45
    exit_ratio: float = 0.65
    min_frames_closed: int = 2
    min_frames_open: int = 2
    cooldown_ms: float = 120.0
    drag_move_px: float = 10.0
    double_click_ms: float = 350.0
    middle_enter_ratio: float = 0.42
    middle_exit_ratio: float = 0.60


@dataclass(frozen=True)
class FilterConfig:
    """One Euro filter tuning for the pointer."""

    min_cutoff: float = 1.4
    beta: float = 0.007
    d_cutoff: float = 1.0


@dataclass(frozen=True)
class CursorConfig:
    """Pointer mapping configuration.

    ``active_box`` is the normalized region of the camera frame that maps to the
    full screen. Only mapping the center of the frame avoids forcing users to
    stretch to reach screen edges (see air-touch design notes, PLAN.md 3.5).
    """

    active_box_left: float = 0.20
    active_box_top: float = 0.15
    active_box_right: float = 0.80
    active_box_bottom: float = 0.90
    gain: float = 1.0
    area_radius_px: float = 28.0
    click_freeze_ms: float = 220.0


@dataclass(frozen=True)
class EngineConfig:
    pinch: PinchConfig = field(default_factory=PinchConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    min_detection_confidence: float = 0.6
    min_tracking_confidence: float = 0.6
    max_num_hands: int = 2
    model_complexity: int = 1
    camera_index: int = 0
    frame_width: int = 960
    frame_height: int = 540


DEFAULT_CONFIG = EngineConfig()
