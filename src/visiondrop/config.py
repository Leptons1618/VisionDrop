"""Configuration for VisionDrop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

Point = tuple[int, int]
Color = tuple[int, int, int]


@dataclass(frozen=True)
class DropZone:
    """A rectangular screen region that objects can be dropped into."""

    x1: int
    y1: int
    x2: int
    y2: int
    label: str = "zone"

    def contains(self, point: Point) -> bool:
        x, y = point
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


@dataclass(frozen=True)
class HandTrackingConfig:
    num_hands: int = 2
    min_detection_confidence: float = 0.5
    min_hand_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


@dataclass
class ColorDetectionConfig:
    """Settings for the HSV fallback detector."""

    min_area: float = 500
    blur_kernel: tuple[int, int] = (5, 5)
    color_ranges: list[dict] = field(
        default_factory=lambda: [
            {
                "name": "yellow",
                "lower": np.array([20, 100, 100]),
                "upper": np.array([30, 255, 255]),
            }
        ]
    )


@dataclass
class YoloConfig:
    """Settings for the YOLO11 detector with ByteTrack tracking."""

    model: str = "yolo11n.pt"
    confidence: float = 0.35
    iou: float = 0.5
    image_size: int = 640
    device: str | None = None
    classes: tuple[str, ...] | None = None  # None = all COCO classes
    track: bool = True


@dataclass
class InteractionConfig:
    """Thresholds for the grab/drag/drop state machine.

    Ratios are pinch distance over hand span, so they are independent of
    camera distance. Grab and release use separate thresholds (hysteresis) to
    prevent flicker at the boundary. Calibration knobs: tune per camera.
    """

    grab_ratio: float = 0.25
    release_ratio: float = 0.45
    debounce_frames: int = 3
    lost_tolerance_frames: int = 15  # ~0.5 s at 30 FPS
    cooldown_frames: int = 10
    filter_min_cutoff: float = 1.0
    filter_beta: float = 0.007
    grab_mode: str = "pinch"  # "pinch" or "dwell"
    dwell_s: float = 0.5
    dwell_exit_px: float = 80.0


DEFAULT_COLORS: dict[str, Color] = {
    "red": (0, 0, 255),
    "green": (0, 255, 0),
    "blue": (255, 0, 0),
    "yellow": (0, 255, 255),
    "white": (255, 255, 255),
}

DEFAULT_DROP_ZONES: tuple[DropZone, ...] = (
    DropZone(100, 100, 420, 420, label="A"),
    DropZone(500, 100, 820, 420, label="B"),
)


@dataclass
class AppConfig:
    """Runtime configuration for the application."""

    source: int | str = 0
    frame_width: int = 1280
    frame_height: int = 720
    model_dir: str | None = None
    log_path: str | None = None  # JSONL session log when set
    detector: str = "yolo"  # "yolo" or "color"
    hand: HandTrackingConfig = field(default_factory=HandTrackingConfig)
    yolo: YoloConfig = field(default_factory=YoloConfig)
    color: ColorDetectionConfig = field(default_factory=ColorDetectionConfig)
    interaction: InteractionConfig = field(default_factory=InteractionConfig)
    grab_radius_ratio: float = 0.75  # fraction of the hand span
    min_grab_radius: float = 24.0  # pixels
    drop_zones: Sequence[DropZone] = DEFAULT_DROP_ZONES
    colors: dict[str, Color] = field(default_factory=lambda: dict(DEFAULT_COLORS))


def find_zone(point: Point, zones: Iterable[DropZone]) -> DropZone | None:
    """Return the first zone containing the point, if any."""
    for zone in zones:
        if zone.contains(point):
            return zone
    return None


def is_in_any_zone(point: Point, zones: Iterable[DropZone]) -> bool:
    return find_zone(point, zones) is not None
